# KDT 규정집 RAG 챗봇 - team-17-project

Module 14(클라우드 기반 AI 서비스) 실습 방식대로, 기존에 만든 RAG 챗봇을
**frontend / backend / model** 3개 컨테이너로 분리하고 Docker Compose로 묶어서 배포한다.
(Hugging Face Spaces가 유료화되어 이번엔 로컬/서버에서 Docker Compose로 직접 실행하는 방식으로 대체)

## 아키텍처

```
[frontend]  Streamlit UI (8501)
    │  HTTP (/ask, /upload)
    ▼
[backend]   FastAPI 게이트웨이 (8000) - 요청 검증/중계만 담당, RAG 로직 없음
    │  HTTP (/ask, /ingest)
    ▼
[model]     FastAPI 추론 서비스 (8100) - loader/chunker/embedder/retriever/rag_chain 실행
```

- **frontend**: 사용자가 보는 챗봇 화면. backend에만 말을 건다.
- **backend**: 게이트웨이. frontend 요청을 검증하고 model 서비스로 그대로 위임한다.
- **model**: 실제 RAG 파이프라인(PDF 로딩→청킹→임베딩→검색→LLM 생성)을 돌리는 서비스.
  서버 시작 시 한 번 벡터스토어를 준비해두고 재사용한다.

세 개를 분리해둔 이유: model만 GPU/임베딩모델 등 무거운 의존성을 갖고, backend/frontend는
가볍게 유지 → 나중에 model만 별도 서버(GPU 인스턴스)로 옮기거나 스케일링하기 쉬움.

## 폴더 구조

```
team-17-project/
├── docker-compose.yml
├── .env.example              # 복사해서 .env로 만들고 API 키 채우기
├── data/raw/                 # 원본 규정 PDF 6종
├── model/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── loader.py         # PDF 로딩 + OCR 폴백
│       ├── chunker.py        # 조/항/호 경계 기준 청킹
│       ├── embedder.py       # 임베딩 모델 (jhgan/snunlp/minilm/bge_m3)
│       ├── retriever.py      # Chroma/FAISS + 하이브리드(BM25) 검색
│       ├── rag_chain.py      # LCEL RAG 체인 (prompt + LLM)
│       └── service.py        # FastAPI 서버 (/health, /ask, /ingest)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/api.py            # FastAPI 게이트웨이 (/health, /ask, /upload)
└── frontend/
    ├── Dockerfile
    ├── requirements.txt
    └── src/app.py            # Streamlit 챗봇 UI
```

## 실행 방법

```bash
cp .env.example .env
# .env에 UPSTAGE_API_KEY / GOOGLE_API_KEY / GROQ_API_KEY / HF_TOKEN 채우기

docker compose up --build
```

- 챗봇: http://localhost:8501
- backend API 문서: http://localhost:8000/docs
- model API 문서(디버깅용): http://localhost:8100/docs

최종 확정 모델 조합(`model/src/service.py` 상단)은 다음과 같음:

| 항목 | 값 |
|---|---|
| 임베딩 | bge_m3 |
| 벡터DB | FAISS |
| 검색 | 하이브리드 (dense + BM25) |
| LLM | Groq Llama-3.3-70B |
| 프롬프트 | service(간결한 AI 어시스턴트 톤) |

## 협업 방식 (Git/GitHub)

- `main`은 항상 배포 가능한 상태로 유지
- 기능 단위로 `feature/xxx` 브랜치를 파서 작업 → PR → 리뷰 후 머지
  - 예: `feature/frontend-chat`, `feature/backend-gateway`, `feature/model-hybrid-search`
- 배포 중 겪은 문제(예: Groq 무료 티어 TPD 한도, ragas의 vertexai import 이슈 등)는
  PR 설명이나 이슈에 상세히 기록해서 발표 자료로 재활용
