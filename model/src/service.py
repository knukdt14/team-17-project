"""
service.py
- model 컨테이너의 FastAPI 서버: RAG 파이프라인(loader/chunker/embedder/retriever/rag_chain)을
  실제로 실행하는 추론 서비스. frontend(Streamlit)가 이 서비스를 직접 HTTP로 호출한다.
- 서버 시작 시(lifespan) PDF 로딩 + 벡터스토어 준비 + LLM 체인 구성을 한 번만 수행한다.
"""

import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from loader import load_pdf, load_pdf_directory
from chunker import chunk_pages
from retriever import get_or_build_store, get_retriever, get_hybrid_retriever, chunks_to_documents
from rag_chain import get_rag_chain

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
LLM_KEY = "hf_local"
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
    pages = load_pdf_directory(DATA_DIR)
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
    state["chain"] = get_rag_chain(state["retriever"], llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)
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


def _stream_answer(question: str):
    """RAG 체인을 토큰 단위로 스트리밍하며 SSE 이벤트로 흘려보낸다.
    generate가 끝나기 전에 다음 요청이 GPU를 밟지 않도록, 스트림 소비가 끝날 때까지 gpu_lock을 쥔다."""
    with gpu_lock:
        for token in state["chain"].stream(question):
            yield _sse({"token": token})
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
        state["chunks"].extend(new_chunks)
        state["retriever"] = _build_retriever()
        state["chain"] = get_rag_chain(state["retriever"], llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)

    return IngestResponse(
        message="업로드 및 벡터DB 반영 완료",
        filename=filename,
        chunks_added=len(new_chunks),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=8100, reload=True)
