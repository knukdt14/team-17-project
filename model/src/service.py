"""
service.py
- model 컨테이너의 FastAPI 서버: RAG 파이프라인(loader/chunker/embedder/retriever/rag_chain)을
  실제로 실행하는 추론 서비스. frontend(Streamlit)가 이 서비스를 직접 HTTP로 호출한다.
- 서버 시작 시(lifespan) PDF 로딩 + 벡터스토어 준비 + LLM 체인 구성을 한 번만 수행한다.
"""

import json
import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from loader import load_pdf, load_pdf_directory
from chunker import chunk_pages
from retriever import (
    get_or_build_store,
    get_retriever,
    get_hybrid_retriever,
    chunks_to_documents,
    persist_store,
)
from rag_chain import get_answer_chain, format_docs

# 도커 컨테이너 기준 기본 경로. 로컬(비도커)에서 테스트할 때는 DATA_DIR/VECTORSTORE_DIR/UPLOAD_DIR
# 환경변수로 리포지토리 루트 기준 상대경로를 넘겨서 오버라이드한다.
DATA_DIR = os.environ.get("DATA_DIR", "/app/data/raw")
VECTORSTORE_DIR = os.environ.get("VECTORSTORE_DIR", "/app/vectorstore")  # docker-compose가 볼륨을 마운트해서 재빌드 없이 재사용
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 벡터DB 백엔드 / 임베딩 모델 / LLM / 프롬프트 조합 - 최종 확정된 조합을 여기에 반영
VECTORSTORE_BACKEND = "faiss"
EMBEDDING_MODEL_KEY = "bge_m3"
# bge_m3(약 2GB)를 LLM과 같은 GPU에 같이 올리면 8GB급 GPU에서 VRAM이 빠듯해져 로컬 LLM
# 스트리밍(TextIteratorStreamer 60초 타임아웃)이 실패하는 걸 확인함. 질문 1건 임베딩은 CPU로도
# 충분히 빠르므로 CPU로 분리해서 GPU를 전부 LLM에 준다.
EMBEDDING_DEVICE = "cpu"
# 로컬 Qwen2.5-7B(4bit)이 가끔 한자/중국어가 섞여 나오는 언어 드리프트가 있어서, API 기반
# Upstage Solar로 교체함. get_answer_chain이 prompt|llm|StrOutputParser()로 백엔드를
# 추상화해두고 있어서(rag_chain.get_llm) llm_key만 바꾸면 되고, 나머지 스트리밍/검색 로직은
# 그대로 재사용된다. UPSTAGE_API_KEY가 .env에 있어야 한다.
LLM_KEY = "solar"
PROMPT_STYLE = "service"
USE_HYBRID_RETRIEVAL = True
TOP_K = 5

state = {"vectorstore": None, "chunks": None, "retriever": None, "chain": None}
gpu_lock = threading.Lock()  # 임베딩/LLM 인스턴스 1개 -> 동시 요청을 직렬화해서 안전하게 처리


def _build_retriever():
    if USE_HYBRID_RETRIEVAL:
        return get_hybrid_retriever(state["vectorstore"], state["chunks"], k=TOP_K)
    return get_retriever(state["vectorstore"], k=TOP_K)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[model] 문서 로드 및 벡터스토어 준비 중...")
    # data/raw(기본 규정 PDF) + uploads(관리자가 이전에 올려서 반영한 PDF)를 같이 로드해야
    # 재시작 후에도 업로드했던 PDF가 BM25 코퍼스(state["chunks"])에 그대로 남아있음.
    # 벡터DB(FAISS)는 persist_store()로 디스크에 저장해두므로 여기서는 캐시를 그대로 재사용함.
    pages = load_pdf_directory(DATA_DIR) + load_pdf_directory(str(UPLOAD_DIR))
    chunks = chunk_pages(pages)
    state["chunks"] = chunks
    state["vectorstore"] = get_or_build_store(
        VECTORSTORE_BACKEND,
        EMBEDDING_MODEL_KEY,
        chunks,
        base_dir=VECTORSTORE_DIR,
        embedding_device=EMBEDDING_DEVICE,
    )
    state["retriever"] = _build_retriever()
    state["chain"] = get_answer_chain(llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)
    print("[model] 준비 완료 - 서버 시작")
    yield
    print("[model] 서버 종료")


app = FastAPI(title="KDT 규정집 RAG 모델 서비스", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend(8501) <-> model(8100) 간 크로스 오리진 허용 (데모용)
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class IngestResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int


@app.get("/health")
def health():
    return {"status": "ok"}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def _word_overlap(a: str, b: str) -> float:
    """단어 집합 Jaccard 유사도. 검색 순위(하이브리드 리트리버가 매긴 순서)는 질문과 문서의
    관련성만 볼 뿐이라, 실제로 LLM이 생성한 답변과는 동떨어진 문서(예: 서식 첨부 페이지)가
    1등으로 뽑히는 경우가 실측으로 확인됨. 그래서 생성된 답변 자체와 각 후보 문서의 단어가
    얼마나 겹치는지를 다시 봐서, "실제로 답변에 쓰인 것 같은" 문서를 고르는 데 씀."""
    set_a = set(_WORD_RE.findall(a))
    set_b = set(_WORD_RE.findall(b))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


_ARTICLE_HEADER_RE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*\([^)]{0,40}\)")
# "1. ", "5. ", "①", "④" 처럼 상위 항목을 나타내는 줄 - 매칭 라인이 이런 항목 아래 딸려있을 때
# 그 상위 항목 제목을 같이 보여줘야 "어디 소속 내용인지" 문맥이 살아남
_HEADING_LINE_RE = re.compile(r"^\s*(?:[①-⑮]|\d{1,2}\s*[.)]\s*\S)")


def _best_snippet(answer: str, text: str) -> str:
    """청크 전체(최대 chunk_size)를 그대로 보여주는 대신, 답변과 실제 관련 있는 부분만 잘라서
    보여준다. 청크 하나에 여러 조항/서식이 같이 들어있는 경우가 있어(chunk_size 기준 분할이라
    항상 조 단위로 안 끊김) 전체를 보여주면 관련 없는 내용까지 다 나오는 문제가 있었음.

    "제O조(...)" 헤더가 있는 조항형 문서는 그 조 전체 구간만 잘라서 반환하고, 헤더가 없는
    문서(서식 등 조항 구조가 아닌 PDF)는 답변과 가장 겹치는 줄 주변 몇 줄만 잘라서 반환한다."""
    headers = list(_ARTICLE_HEADER_RE.finditer(text))
    if headers:
        spans = []
        for i, h in enumerate(headers):
            start = h.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            spans.append(text[start:end].strip())
        return max(spans, key=lambda s: _word_overlap(answer, s))

    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return text
    best_idx = max(range(len(lines)), key=lambda i: _word_overlap(answer, lines[i]))
    start = max(0, best_idx - 2)
    end = min(len(lines), best_idx + 3)

    # 윈도우 밖(위쪽)에 상위 항목 제목이 있으면 문맥으로 같이 붙인다 (예: 매칭 라인이
    # "●인정 일수: ..."인데 몇 줄 위의 "5. 질병ㆍ입원"이 그 상위 항목인 경우).
    heading_idx = None
    for i in range(start - 1, max(-1, start - 6), -1):
        if _HEADING_LINE_RE.match(lines[i]):
            heading_idx = i
            break

    snippet_lines = ([lines[heading_idx]] if heading_idx is not None else []) + lines[start:end]
    return "\n".join(snippet_lines)


def _stream_answer(question: str):
    """검색 -> LLM 스트리밍 -> 마지막에 근거 문서(sources) 순서로 SSE 이벤트를 흘려보낸다.
    generate가 끝나기 전에 다음 요청이 GPU를 밟지 않도록, 스트림 소비가 끝날 때까지 gpu_lock을 쥔다."""
    answer_parts = []
    with gpu_lock:
        docs = state["retriever"].invoke(question)
        context = format_docs(docs)
        for token in state["chain"].stream({"context": context, "question": question}):
            answer_parts.append(token)
            yield _sse({"token": token})

    # 검색 순위 1등이 아니라, 실제로 생성된 답변과 단어가 가장 많이 겹치는 문서를
    # "답변에 가장 큰 영향을 준 근거" 1건으로 고른다.
    answer = "".join(answer_parts)
    top_doc = max(docs, key=lambda d: _word_overlap(answer, d.page_content)) if docs else None
    sources = (
        [
            {
                "filename": top_doc.metadata.get("source"),
                "page": top_doc.metadata.get("page_num"),
                "text": _best_snippet(answer, top_doc.page_content),
            }
        ]
        if top_doc
        else []
    )
    yield _sse({"sources": sources})
    yield "data: [DONE]\n\n"


@app.post("/ask")
def ask(req: AskRequest):
    """질문을 받아 RAG 체인 답변을 SSE(text/event-stream)로 토큰 단위 스트리밍한다."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    return StreamingResponse(_stream_answer(req.question), media_type="text/event-stream")


@app.post("/ingest", response_model=IngestResponse)
def ingest(file: UploadFile = File(...)):
    """PDF 파일을 받아 청킹 후 기존 벡터스토어 + BM25 코퍼스에 추가한다."""
    filename = file.filename
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    dest = UPLOAD_DIR / filename
    dest.write_bytes(file.file.read())

    pages = load_pdf(str(dest))
    new_chunks = chunk_pages(pages)

    with gpu_lock:
        state["vectorstore"].add_documents(chunks_to_documents(new_chunks))
        # FAISS는 add_documents만으로는 디스크 캐시에 반영이 안 돼서, 명시적으로 저장해야
        # 컨테이너를 재시작해도 방금 추가한 PDF가 검색에 그대로 남아있음.
        persist_store(state["vectorstore"], VECTORSTORE_BACKEND, EMBEDDING_MODEL_KEY, base_dir=VECTORSTORE_DIR)
        state["chunks"].extend(new_chunks)
        state["retriever"] = _build_retriever()
        state["chain"] = get_answer_chain(llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)

    return IngestResponse(
        message="업로드 및 벡터DB 반영 완료",
        filename=filename,
        chunks_added=len(new_chunks),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=8100, reload=True)
