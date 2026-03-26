import os
import uuid
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RELEVANCE_THRESHOLD = 0.3

_client: Optional[chromadb.PersistentClient] = None
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


def get_collection(user_id: str = "default"):
    """Return (or create) the ChromaDB collection for the given user.

    Collection name pattern: contendo_{user_id}
    The default single-user collection is contendo_default.
    When auth is added, user_id becomes the JWT-extracted user ID.
    """
    client = _get_client()
    collection_name = f"contendo_{user_id}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


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
    source_title: str = "",
    ingested_at: str = "",
    user_id: str = "default",
    content_hash: str = "",
) -> int:
    collection = get_collection(user_id)
    if not chunks:
        return 0

    source_id = source_id or str(uuid.uuid4())
    embeddings = embed_texts(chunks)
    total = len(chunks)

    ids = [f"{source_id}_{i}" for i in range(total)]
    metadatas = [
        {
            "source_type": source_type,
            "tags": ",".join(tags),
            "source_id": source_id,
            "chunk_index": i,
            "total_chunks": total,
            "source_title": source_title,
            "ingested_at": ingested_at,
            "content_hash": content_hash,
        }
        for i in range(total)
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return total


def query_by_hash(content_hash: str, user_id: str = "default") -> dict | None:
    """Check if content with this hash already exists in the collection.

    Returns dict with chunk_count and tags if found, None if not.
    """
    collection = get_collection(user_id)
    results = collection.get(
        where={"content_hash": content_hash},
        limit=1,
    )
    if not results or not results["ids"]:
        return None

    # Get all chunks for this hash to count them
    all_chunks = collection.get(where={"content_hash": content_hash})
    chunk_count = len(all_chunks["ids"])

    # Extract tags from first chunk metadata
    tags_raw = all_chunks["metadatas"][0].get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    return {"chunk_count": chunk_count, "tags": tags}


def query_similar(query: str, top_k: int = 8, user_id: str = "default") -> list[dict]:
    collection = get_collection(user_id)
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


def get_total_chunks(user_id: str = "default") -> int:
    collection = get_collection(user_id)
    return collection.count()


def get_all_tags(user_id: str = "default") -> list[str]:
    collection = get_collection(user_id)
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


def delete_source(source_title: str, user_id: str = "default") -> int:
    """Delete all ChromaDB chunks with matching source_title metadata.

    Returns the number of chunks deleted, or 0 if no matching chunks found.
    """
    collection = get_collection(user_id)
    results = collection.get(where={"source_title": source_title})
    if not results["ids"]:
        return 0
    collection.delete(ids=results["ids"])
    return len(results["ids"])


def get_all_sources(user_id: str = "default") -> list[dict]:
    collection = get_collection(user_id)
    if collection.count() == 0:
        return []

    results = collection.get(include=["metadatas"])
    # Group chunks by source_id
    groups: dict[str, dict] = {}
    for meta in results["metadatas"]:
        sid = meta.get("source_id", "unknown")
        if sid not in groups:
            groups[sid] = {
                "source_title": meta.get("source_title", "") or "Untitled",
                "source_type": meta.get("source_type", "unknown"),
                "ingested_at": meta.get("ingested_at", ""),
                "chunk_count": 0,
                "tag_set": set(),
            }
        groups[sid]["chunk_count"] += 1
        raw_tags = meta.get("tags", "")
        if raw_tags:
            for tag in raw_tags.split(","):
                tag = tag.strip()
                if tag:
                    groups[sid]["tag_set"].add(tag)

    sources = []
    for entry in groups.values():
        sources.append({
            "source_title": entry["source_title"],
            "source_type": entry["source_type"],
            "ingested_at": entry["ingested_at"],
            "chunk_count": entry["chunk_count"],
            "tags": sorted(entry["tag_set"]),
        })

    # Sort newest first; entries without ingested_at go last
    sources.sort(key=lambda s: s["ingested_at"] or "", reverse=True)
    return sources
