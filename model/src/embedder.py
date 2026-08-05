"""
embedder.py
- LangChain의 HuggingFaceEmbeddings로 여러 임베딩 모델을 동일한 인터페이스로 비교
- retriever.py / rag_chain.py에서 get_embedding_model(key)만 호출하면 됨

폴더 구조 규칙과 맞추기 위해 모델 key는 chroma_db_<key> / faiss_db_<key> 이름과 동일하게 사용한다.
(예: EMBEDDING_MODELS["jhgan"] -> chroma_db_jhgan, faiss_db_jhgan)

※ requirements.txt에 langchain, langchain-chroma, langchain-huggingface, faiss-cpu가 이미 있어서
   (LangChain 기반 RAG 구현이 과제 필수 요구사항이기도 함) 이번에 LangChain 벡터스토어/임베딩
   래퍼를 쓰도록 정리했습니다. rag_chain.py가 기대하는 get_embedding_model()과 이름을 맞췄습니다.
"""

from typing import Dict

from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODELS: Dict[str, dict] = {
    "jhgan": {
        "model_id": "jhgan/ko-sroberta-multitask",
        "dim": 768,
        "desc": "KorSTS/KorNLI로 파인튜닝된 한국어 SBERT. 한국어 문장 유사도 태스크에서 널리 쓰이는 baseline급 모델.",
    },
    "snunlp": {
        "model_id": "snunlp/KR-SBERT-V40K-klueNLI-augSTS",
        "dim": 768,
        "desc": "KLUE-NLI + STS 증강 데이터로 학습된 한국어 SBERT. jhgan과 함께 한국어 임베딩 비교의 단골 조합.",
    },
    "minilm": {
        "model_id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dim": 384,
        "desc": "다국어 경량 모델. 차원이 작고 속도가 빨라 '가벼운 baseline'으로 비교하기 좋음.",
    },
    "bge_m3": {
        "model_id": "BAAI/bge-m3",
        "dim": 1024,
        "desc": "다국어(한국어 포함) 지원 + 최대 8192 토큰까지 긴 문맥 임베딩 가능. 최신 모델 중 하나로 비교군에 추가할 가치가 큼.",
    },
}

DEFAULT_MODEL_KEY = "jhgan"


def get_embedding_model(model_key: str = DEFAULT_MODEL_KEY, device: str | None = None) -> HuggingFaceEmbeddings:
    """LangChain 호환 임베딩 객체 반환. Chroma.from_documents / FAISS.from_documents에 그대로 넣으면 됨.
    device를 안 넘기면 torch가 CUDA 사용 가능 시 자동으로 GPU에 올림 - LLM과 같은 GPU에서
    VRAM을 다투게 되므로, LLM과 동시에 서빙하는 쪽(service.py)에서는 device="cpu"로 분리해서 쓴다."""
    if model_key not in EMBEDDING_MODELS:
        raise ValueError(
            f"등록되지 않은 모델 key: {model_key} (가능한 값: {list(EMBEDDING_MODELS)})"
        )
    model_id = EMBEDDING_MODELS[model_key]["model_id"]
    return HuggingFaceEmbeddings(
        model_name=model_id,
        model_kwargs={"device": device} if device else {},
        encode_kwargs={"normalize_embeddings": True},  # 정규화 -> 코사인 유사도 = 내적으로 계산
    )


if __name__ == "__main__":
    import time

    sample_docs = [
        "국민내일배움카드 발급 대상은 누구인가요?",
        "훈련장려금은 어떤 기준으로 지급되나요?",
        "출석률이 부족하면 어떻게 되나요?",
    ] * 5

    header = f"{'model_key':<10} {'sec':>8}  model_id"
    print(header)
    print("-" * len(header))
    for key in EMBEDDING_MODELS:
        emb = get_embedding_model(key)
        t0 = time.time()
        _ = emb.embed_documents(sample_docs)
        elapsed = time.time() - t0
        print(f"{key:<10} {elapsed:>8.2f}  {EMBEDDING_MODELS[key]['model_id']}")
