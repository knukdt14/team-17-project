# KDT 규정집 RAG 챗봇 - team-17-project

Module 14(클라우드 기반 AI 서비스) 실습 방식대로, 기존에 만든 RAG 챗봇을
**frontend / model** 2개 컨테이너로 분리하고 Docker Compose로 묶어서 배포한다.
(Hugging Face Spaces가 유료화되어 이번엔 로컬/서버에서 Docker Compose로 직접 실행하는 방식으로 대체)

원래는 frontend-model 사이에 요청을 중계만 하는 backend 게이트웨이를 따로 뒀었는데,
model이 이미 FastAPI로 완전한 API 레이어(검증/에러 처리/SSE 스트리밍 포함)를 갖고 있어서
backend가 하는 일과 그대로 겹쳤다. 아무 로직 없이 중계만 하는 계층이라 판단해 걷어내고
frontend가 model을 직접 호출하도록 단순화했다.

## 아키텍처

```
[frontend]  Streamlit UI (8501)
    │  HTTP (/ask - SSE 스트리밍, /ingest)
    ▼
[model]     FastAPI 추론 서비스 (8100) - loader/chunker/embedder/retriever/rag_chain 실행
```

- **frontend**: 사용자가 보는 챗봇 화면. model에 직접 요청하고, 답변은 토큰 단위로
  스트리밍 받아 그대로 렌더링한다(`st.write_stream`).
- **model**: 실제 RAG 파이프라인(PDF 로딩→청킹→임베딩→검색→LLM 생성)을 돌리는 서비스.
  서버 시작 시 한 번 벡터스토어를 준비해두고 재사용하며, 요청 검증/에러 처리도 여기서 담당한다.

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
│       └── service.py        # FastAPI 서버 (/health, /ask(SSE), /ingest)
└── frontend/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── app.py            # Streamlit 진입점 (페이지 라우팅)
        ├── auth.py           # 관리자 로그인
        ├── chat_page.py      # 챗봇 화면
        ├── admin_page.py     # 관리자 - PDF 업로드
        ├── sources.py        # 출처 카드 UI
        └── api_client.py     # model 호출 (요청/스트리밍/에러 처리 공통화)
```

## 실행 방법

```bash
cp .env.example .env
# .env에 UPSTAGE_API_KEY / GOOGLE_API_KEY / GROQ_API_KEY / HF_TOKEN 채우기

docker compose up --build
```

- 챗봇: http://localhost:8501
- model API 문서(디버깅용): http://localhost:8100/docs

최종 확정 모델 조합(`model/src/service.py` 상단)은 다음과 같음:

| 항목 | 값 |
|---|---|
| 임베딩 | bge_m3 |
| 벡터DB | FAISS |
| 검색 | 하이브리드 (dense + BM25) |
| LLM | 로컬 Qwen2.5-7B-Instruct (4bit 양자화, GPU) |
| 프롬프트 | service(간결한 AI 어시스턴트 톤) |

## 협업 방식 (Git/GitHub)

- `main`은 항상 배포 가능한 상태로 유지
- 기능 단위로 `feature/xxx` 브랜치를 파서 작업 → PR → 리뷰 후 머지
  - 예: `feature/frontend-chat`, `feature/model-hybrid-search`
- 배포 중 겪은 문제(예: Groq 무료 티어 TPD 한도, ragas의 vertexai import 이슈 등)는
  PR 설명이나 이슈에 상세히 기록해서 발표 자료로 재활용
