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
    ids_by_source,
    build_scoped_hybrid_retriever,
)
from rag_chain import get_answer_chain, format_docs, generate_faq_questions

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
# 그대로 재사용된다. UPSTAGE_API_KEY / GROQ_API_KEY가 .env에 있어야 한다.
#
# 무료/유료 버전 데모용 - 실제 과금 로직은 없고, tier에 따라 그냥 다른 LLM으로 답변하게만
# 나눠둔 것 (시각화/데모 목적). AskRequest.tier로 받아서 아래 chains 중 하나를 고른다.
TIER_LLM_KEYS = {"free": "solar", "paid": "groq_llama"}
PROMPT_STYLE = "service"
USE_HYBRID_RETRIEVAL = True
TOP_K = 5
# 관리자 테스트용 챗봇의 검색 대상(업로드 PDF)이 무한정 늘어나지 않도록 제한.
MAX_UPLOADED_FILES = 5

# 기수 -> 모집공고 PDF 파일명. cohorts.py(frontend)의 COHORT_LIST와 맞춰뒀다 - 새 기수가
# 열리면 여기도 같이 추가해야 그 기수 전용 검색이 적용된다.
COHORT_PDF_FILES = {
    "13기": "KDT_13기_모집공고.pdf",
    "14기": "KDT_14기_아진산업_모집공고.pdf",
    "15기": "KDT_15기_티에이치엔_모집공고.pdf",
    "17기": "KDT_17기_피엔티_모집공고.pdf",
}
# 지금 서비스 중인 기수가 아닌 모집공고 - 특정 기수 것으로 배정돼있지 않으니 아무한테도
# 안 보이게 모든 기수 검색에서 공통으로 제외한다.
_OTHER_COHORT_FILES = {"KDT_HD건설기계_HiCEED_모집공고.pdf"}
_ALL_COHORT_FILES = set(COHORT_PDF_FILES.values()) | _OTHER_COHORT_FILES

state = {
    "vectorstore": None,
    "chunks": None,
    "retriever": None,
    "retriever_uploaded": None,
    "common_retriever": None,
    "cohort_own_docs": {},
    "chains": {},
}
gpu_lock = threading.Lock()  # 임베딩/LLM 인스턴스 1개 -> 동시 요청을 직렬화해서 안전하게 처리


def _build_retriever():
    if USE_HYBRID_RETRIEVAL:
        return get_hybrid_retriever(state["vectorstore"], state["chunks"], k=TOP_K)
    return get_retriever(state["vectorstore"], k=TOP_K)


def _build_common_retriever():
    """모든 기수 모집공고를 제외한 공통 문서(규정집 등)만 검색하는 리트리버. 기수가 없는
    요청(관리자 등)의 기본값이자, 기수가 있는 요청에서도 "그 기수 자신의 문서"에 얹어서 함께
    검색하는 공통 지식 베이스로 쓰인다. 하이브리드가 아니면(USE_HYBRID_RETRIEVAL=False) 필터를
    지원하지 않는 get_retriever로 폴백 - 이 경우는 기수 구분 없이 전체 문서를 검색한다."""
    if not USE_HYBRID_RETRIEVAL:
        return get_retriever(state["vectorstore"], k=TOP_K)
    common_sources = {c.source for c in state["chunks"] if c.source not in _ALL_COHORT_FILES}
    return get_hybrid_retriever(state["vectorstore"], state["chunks"], k=TOP_K, allowed_sources=common_sources)


def _build_cohort_own_docs():
    """기수별 모집공고 자체는 chunk 수가 2~3개로 너무 적어서, 일반적인 질문("교육장이 어디야?")
    과의 검색 랭킹 경쟁에서 규정집의 서식/양식 페이지 같은 문서에 밀려 top-k 밖으로 밀려나는
    문제가 실측으로 확인됨(랭킹에만 맡기면 기수 정보가 아예 컨텍스트에 안 들어감). 그래서 검색
    랭킹에 맡기지 않고, 그 기수 문서 전체 chunk를 항상 컨텍스트에 포함시킨다 - 문서 자체가
    작아서(기수당 2~3 chunk) 매 요청마다 넣어도 컨텍스트 길이 부담이 거의 없다."""
    return {
        cohort: chunks_to_documents([c for c in state["chunks"] if c.source == pdf_filename])
        for cohort, pdf_filename in COHORT_PDF_FILES.items()
    }


def _uploaded_filenames() -> set[str]:
    """관리자가 업로드해서 UPLOAD_DIR에 남아있는 PDF 파일명 집합 (기본 제공 규정집과 구분)."""
    return {p.name for p in UPLOAD_DIR.glob("*.pdf")}


def _all_pdf_paths() -> list[Path]:
    return sorted(Path(DATA_DIR).glob("*.pdf")) + sorted(UPLOAD_DIR.glob("*.pdf"))


def _rebuild_uploaded_retriever():
    """관리자 테스트용 챗봇(scope="uploaded")이 쓰는, 업로드된 파일만으로 이뤄진 리트리버를
    현재 상태 기준으로 다시 만든다. 업로드된 파일이 하나도 없으면 None(검색 불가)이 된다."""
    uploaded = _uploaded_filenames()
    uploaded_chunks = [c for c in state["chunks"] if c.source in uploaded]
    state["retriever_uploaded"] = build_scoped_hybrid_retriever(
        uploaded_chunks, EMBEDDING_MODEL_KEY, embedding_device=EMBEDDING_DEVICE, k=TOP_K
    )


def _rebuild_derived_retrievers():
    """state["chunks"]가 바뀔 때마다(업로드/삭제) 그로부터 파생되는 리트리버들을 전부
    다시 만든다 - 하나라도 빠뜨리면 방금 반영한 변경이 일부 검색 경로에는 안 보이는
    불일치가 생긴다."""
    state["retriever"] = _build_retriever()
    _rebuild_uploaded_retriever()
    state["common_retriever"] = _build_common_retriever()
    state["cohort_own_docs"] = _build_cohort_own_docs()


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
    _rebuild_derived_retrievers()
    state["chains"] = {
        tier: get_answer_chain(llm_key=llm_key, prompt_style=PROMPT_STYLE)
        for tier, llm_key in TIER_LLM_KEYS.items()
    }
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
    tier: str = "free"
    # "all": 기본 규정집 + 업로드 파일 전체(일반 사용자용, 기수별 모집공고 우선참조 포함).
    # "uploaded": 관리자가 업로드한 파일만(관리자 테스트용 챗봇).
    scope: str = "all"
    cohort: str | None = None  # scope="all"일 때, 주어지면 그 기수의 모집공고를 항상 포함


class IngestResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int
    faq_questions: list[str] = []


class FileInfo(BaseModel):
    filename: str
    origin: str  # "base"(기본 제공 규정집) | "uploaded"(관리자 업로드)
    size_bytes: int
    chunk_count: int


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


def _stream_answer(question: str, tier: str, scope: str = "all", cohort: str | None = None):
    """검색 -> LLM 스트리밍 -> 마지막에 근거 문서(sources) 순서로 SSE 이벤트를 흘려보낸다.
    generate가 끝나기 전에 다음 요청이 GPU를 밟지 않도록, 스트림 소비가 끝날 때까지 gpu_lock을 쥔다.

    scope="uploaded"(관리자 테스트용 챗봇)면 관리자가 업로드한 파일만으로 검색한다.
    그 외(scope="all", 일반 사용자)에는 cohort가 주어지면 그 기수의 모집공고 전체(chunk 수가
    적어 검색 랭킹에 안 맡기고 항상 포함)를 공통 검색 결과 앞에 붙인다 - 다른 기수 모집공고는
    공통 리트리버에서 아예 제외돼 있으므로 섞여 들어올 일이 없다."""
    chain = state["chains"].get(tier) or state["chains"]["free"]

    if scope == "uploaded":
        retriever = state["retriever_uploaded"]
        if retriever is None:
            yield _sse({"error": "테스트할 업로드된 PDF가 없습니다. 먼저 PDF를 업로드해주세요."})
            yield "data: [DONE]\n\n"
            return
        own_docs = []
    else:
        retriever = state["common_retriever"] or state["retriever"]
        own_docs = state["cohort_own_docs"].get(cohort, [])

    answer_parts = []
    with gpu_lock:
        docs = own_docs + retriever.invoke(question)
        context = format_docs(docs)
        for token in chain.stream({"context": context, "question": question}):
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

    return StreamingResponse(
        _stream_answer(req.question, req.tier, req.scope, req.cohort), media_type="text/event-stream"
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(file: UploadFile = File(...)):
    """PDF 파일을 받아 청킹 후 기존 벡터스토어 + BM25 코퍼스에 추가하고, 관리자가 업로드
    직후 바로 테스트해볼 수 있도록 문서 내용 기반 추천 질문을 같이 만들어 돌려준다."""
    filename = file.filename
    try:
        # 브라우저는 파일명을 UTF-8로 보내지만, multipart Content-Disposition 헤더를
        # latin-1로만 디코딩하는 경로를 타면 한글 파일명이 mojibake로 깨짐
        # (예: "한글.pdf" -> "ÇÑ±Û.pdf")가 실측으로 확인됨. latin-1로 되돌려 원래
        # UTF-8 바이트를 복원한다 - 이미 정상 디코딩된 경우는 여기서 예외가 나서 그냥 통과.
        filename = filename.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    existing_uploads = _uploaded_filenames()
    if filename not in existing_uploads and len(existing_uploads) >= MAX_UPLOADED_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"업로드 가능한 PDF는 최대 {MAX_UPLOADED_FILES}개까지입니다. 기존 파일을 삭제한 후 다시 시도해주세요.",
        )

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
        _rebuild_derived_retrievers()
        state["chains"] = {
            tier: get_answer_chain(llm_key=llm_key, prompt_style=PROMPT_STYLE)
            for tier, llm_key in TIER_LLM_KEYS.items()
        }

        try:
            faq_text = "\n\n".join(c.text for c in new_chunks[:8])
            faq_questions = generate_faq_questions(faq_text, llm_key=TIER_LLM_KEYS["free"], n=4)
        except Exception as e:
            # FAQ 생성은 부가 기능이라, 실패해도 업로드 자체(반영)는 성공으로 처리한다.
            print(f"[model] FAQ 질문 생성 실패: {e}")
            faq_questions = []

    return IngestResponse(
        message="업로드 및 벡터DB 반영 완료",
        filename=filename,
        chunks_added=len(new_chunks),
        faq_questions=faq_questions,
    )


@app.get("/files", response_model=list[FileInfo])
def list_files():
    """현재 검색에 반영된 모든 PDF(기본 제공 규정집 + 관리자 업로드분) 목록을 돌려준다."""
    uploaded = _uploaded_filenames()
    counts: dict[str, int] = {}
    for c in state["chunks"]:
        counts[c.source] = counts.get(c.source, 0) + 1

    return [
        FileInfo(
            filename=path.name,
            origin="uploaded" if path.name in uploaded else "base",
            size_bytes=path.stat().st_size,
            chunk_count=counts.get(path.name, 0),
        )
        for path in _all_pdf_paths()
    ]


@app.delete("/files/{filename}")
def delete_file(filename: str):
    """PDF 파일을 벡터DB/BM25 코퍼스/디스크에서 모두 제거한다. 기본 제공 규정집도 예외
    없이 삭제 가능 - 관리자가 직접 요청한 관리 기능이므로 별도 보호를 두지 않는다."""
    path = next((p for p in _all_pdf_paths() if p.name == filename), None)
    if path is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    with gpu_lock:
        source_ids = ids_by_source(state["vectorstore"]).get(filename, [])
        if source_ids:
            state["vectorstore"].delete(ids=source_ids)
            persist_store(state["vectorstore"], VECTORSTORE_BACKEND, EMBEDDING_MODEL_KEY, base_dir=VECTORSTORE_DIR)
        state["chunks"] = [c for c in state["chunks"] if c.source != filename]
        _rebuild_derived_retrievers()

    path.unlink()

    return {"message": "삭제 완료", "filename": filename}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=8100, reload=True)
