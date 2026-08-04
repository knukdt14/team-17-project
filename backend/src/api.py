"""
api.py
- backend 컨테이너의 FastAPI 게이트웨이: frontend(Streamlit)로부터 질문/PDF 업로드를 받아
  model 컨테이너(RAG 추론 서비스)에 HTTP로 위임하고 결과를 그대로 반환한다.
- RAG 로직(임베딩/검색/LLM)은 전혀 갖지 않는다 - 오직 요청 중계 + 검증/로깅 담당.
"""

import os

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MODEL_SERVICE_URL = os.environ.get("MODEL_SERVICE_URL", "http://model:8100")
REQUEST_TIMEOUT = float(os.environ.get("MODEL_REQUEST_TIMEOUT", "120"))

app = FastAPI(title="KDT 규정집 RAG 챗봇 - Backend Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend(8501) <-> backend(8000) 간 크로스 오리진 허용 (데모용)
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """질문을 받아 model 서비스의 /ask로 위임한다."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    try:
        resp = httpx.post(
            f"{MODEL_SERVICE_URL}/ask", json={"question": req.question}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"model 서비스에 연결할 수 없습니다: {e}") from e

    return AskResponse(**resp.json())


@app.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...)):
    """PDF 파일을 받아 model 서비스의 /ingest로 위임한다."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        resp = httpx.post(
            f"{MODEL_SERVICE_URL}/ingest",
            files={"file": (file.filename, file.file, "application/pdf")},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"model 서비스에 연결할 수 없습니다: {e}") from e

    return UploadResponse(**resp.json())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
