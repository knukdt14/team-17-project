"""
service.py
- model 컨테이너의 FastAPI 서버: RAG 파이프라인(loader/chunker/embedder/retriever/rag_chain)을
  실제로 실행하는 추론 서비스. backend가 이 서비스를 HTTP로 호출한다.
- 서버 시작 시(lifespan) PDF 로딩 + 벡터스토어 준비 + LLM 체인 구성을 한 번만 수행한다.
"""

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
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
        VECTORSTORE_BACKEND, EMBEDDING_MODEL_KEY, chunks, base_dir=VECTORSTORE_DIR
    )
    state["retriever"] = _build_retriever()
    state["chain"] = get_rag_chain(state["retriever"], llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)
    print("[model] 준비 완료 - 서버 시작")
    yield
    print("[model] 서버 종료")


app = FastAPI(title="KDT 규정집 RAG 모델 서비스", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class IngestResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """질문을 받아 RAG 체인을 호출하고 답변을 반환한다."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    with gpu_lock:
        answer = state["chain"].invoke(req.question)

    return AskResponse(answer=answer)


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
