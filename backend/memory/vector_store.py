import os
import uuid
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "contendo"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RELEVANCE_THRESHOLD = 0.3

_client: Optional[chromadb.PersistentClient] = None
_collection = None
_embedder: Optional[SentenceTransformer] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    embedder = _get_embedder()
    return embedder.encode(texts, show_progress_bar=False).tolist()


def upsert_chunks(
    chunks: list[str],
    source_type: str,
    tags: list[str],
    source_id: Optional[str] = None,
) -> int:
    collection = _get_collection()
    if not chunks:
        return 0

    source_id = source_id or str(uuid.uuid4())
    embeddings = embed_texts(chunks)

    ids = [f"{source_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_type": source_type,
            "tags": ",".join(tags),
            "source_id": source_id,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)


def query_similar(query: str, top_k: int = 8) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_texts([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite.
        # Convert to similarity: 1 - (dist / 2) so threshold works as 0..1
        similarity = 1.0 - (dist / 2.0)
        if similarity >= RELEVANCE_THRESHOLD:
            chunks.append(
                {
                    "text": doc,
                    "source_type": meta.get("source_type", "unknown"),
                    "tags": meta.get("tags", "").split(","),
                    "similarity": round(similarity, 4),
                }
            )

    return chunks


def get_total_chunks() -> int:
    collection = _get_collection()
    return collection.count()


def get_all_tags() -> list[str]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    results = collection.get(include=["metadatas"])
    tag_set: set[str] = set()
    for meta in results["metadatas"]:
        raw = meta.get("tags", "")
        if raw:
            for tag in raw.split(","):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)
    return sorted(tag_set)
