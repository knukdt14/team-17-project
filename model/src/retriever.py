"""
retriever.py
- chunker.py의 Chunk 리스트를 LangChain Document로 변환해 Chroma/FAISS에 저장
- get_retriever()로 LangChain 표준 리트리버 객체를 반환 -> rag_chain.py의 LCEL 체인에서 그대로 사용

폴더 이름 규칙: chroma_db_<model_key>, faiss_db_<model_key>

※ 기존 chroma_db_*는 raw chromadb로 이미 만들어져 있어 그대로 재사용됩니다(컬렉션명 kdt_<key> 동일).
   기존 faiss_db_*는 예전 방식(docstore.pkl)이라 LangChain 포맷(index.pkl)이 아니라서 처음 한 번은
   다시 임베딩해서 새로 만듭니다(이후부터는 재사용). 예전 docstore.pkl은 이제 안 쓰는 파일이니 지워도 됩니다.
"""

import os
from typing import List, Literal

import chromadb
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document

from chunker import Chunk
from embedder import get_embedding_model


def _db_dir(backend: Literal["chroma", "faiss"], model_key: str, base_dir: str = ".") -> str:
    prefix = "chroma_db" if backend == "chroma" else "faiss_db"
    return os.path.join(base_dir, f"{prefix}_{model_key}")


def chunks_to_documents(chunks: List[Chunk]) -> List[Document]:
    return [
        Document(
            page_content=c.text,
            metadata={"source": c.source, "page_num": c.page_num, "chunk_id": c.chunk_id},
        )
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# Chroma
# ---------------------------------------------------------------------------
def build_chroma(model_key: str, chunks: List[Chunk], base_dir: str = ".") -> Chroma:
    embeddings = get_embedding_model(model_key)
    persist_dir = _db_dir("chroma", model_key, base_dir)
    docs = chunks_to_documents(chunks)
    return Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
        collection_name=f"kdt_{model_key}",
        collection_metadata={"hnsw:space": "cosine"},
    )


def load_chroma(model_key: str, base_dir: str = ".") -> Chroma:
    embeddings = get_embedding_model(model_key)
    persist_dir = _db_dir("chroma", model_key, base_dir)
    return Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
        collection_name=f"kdt_{model_key}",
    )


def _chroma_has_data(model_key: str, base_dir: str = ".") -> bool:
    persist_dir = _db_dir("chroma", model_key, base_dir)
    if not os.path.exists(os.path.join(persist_dir, "chroma.sqlite3")):
        return False
    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name=f"kdt_{model_key}")
        return collection.count() > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FAISS
# ---------------------------------------------------------------------------
def build_faiss(model_key: str, chunks: List[Chunk], base_dir: str = ".") -> FAISS:
    embeddings = get_embedding_model(model_key)
    persist_dir = _db_dir("faiss", model_key, base_dir)
    docs = chunks_to_documents(chunks)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(persist_dir)
    return vectorstore


def load_faiss(model_key: str, base_dir: str = ".") -> FAISS:
    embeddings = get_embedding_model(model_key)
    persist_dir = _db_dir("faiss", model_key, base_dir)
    return FAISS.load_local(persist_dir, embeddings, allow_dangerous_deserialization=True)


def _faiss_has_data(model_key: str, base_dir: str = ".") -> bool:
    # LangChain FAISS.save_local()이 만드는 파일은 index.faiss + index.pkl.
    # (예전 코드가 만든 docstore.pkl과는 다른 파일이라 index.pkl 존재 여부로 판단)
    persist_dir = _db_dir("faiss", model_key, base_dir)
    return os.path.exists(os.path.join(persist_dir, "index.faiss")) and os.path.exists(
        os.path.join(persist_dir, "index.pkl")
    )


# ---------------------------------------------------------------------------
# 통합 헬퍼
# ---------------------------------------------------------------------------
def get_or_build_store(
    backend: Literal["chroma", "faiss"], model_key: str, chunks: List[Chunk], base_dir: str = "."
):
    """이미 만들어진 벡터DB가 있으면 재사용하고, 없을 때만 새로 임베딩해서 구축."""
    if backend == "chroma":
        if _chroma_has_data(model_key, base_dir):
            print(f"  (기존 chroma_db_{model_key} 재사용)")
            return load_chroma(model_key, base_dir)
        return build_chroma(model_key, chunks, base_dir)
    else:
        if _faiss_has_data(model_key, base_dir):
            print(f"  (기존 faiss_db_{model_key} 재사용)")
            return load_faiss(model_key, base_dir)
        return build_faiss(model_key, chunks, base_dir)


def get_retriever(vectorstore, search_type: str = "similarity", k: int = 5):
    return vectorstore.as_retriever(search_type=search_type, search_kwargs={"k": k})


def get_hybrid_retriever(vectorstore, chunks: List[Chunk], k: int = 5, dense_weight: float = 0.5):
    """임베딩(dense) 검색 + BM25(키워드) 검색을 Reciprocal Rank Fusion으로 합친 하이브리드 리트리버.
    "만 75세 이상" 같이 숫자/고유명사 하나로 정답이 갈리는 질문은, 그 항목이 문서 안에서
    비슷한 다른 항목들과 섞여 있으면 임베딩 유사도만으로는 순위가 크게 밀리는 문제가 실측으로
    확인됨 - BM25는 정확한 단어 일치를 보므로 이런 경우를 보완해줌."""
    dense_retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    bm25_retriever = BM25Retriever.from_documents(chunks_to_documents(chunks))
    bm25_retriever.k = k
    return EnsembleRetriever(
        retrievers=[dense_retriever, bm25_retriever],
        weights=[dense_weight, 1 - dense_weight],
    )


if __name__ == "__main__":
    from chunker import chunk_pages
    from loader import load_pdf_directory

    pages = load_pdf_directory("data/raw")
    chunks = chunk_pages(pages)
    print(f"총 {len(chunks)}개 청크 로드")

    query = "국민내일배움카드 훈련장려금은 얼마까지 받을 수 있나요?"

    for backend in ("chroma", "faiss"):
        for model_key in ("jhgan", "snunlp"):
            print(f"\n=== {backend} / {model_key} ===")
            store = get_or_build_store(backend, model_key, chunks)
            retriever = get_retriever(store, k=3)
            results = retriever.invoke(query)
            for doc in results:
                preview = doc.page_content[:80].replace("\n", " ")
                print(f"  [{doc.metadata['source']} p{doc.metadata['page_num']}] {preview}...")
