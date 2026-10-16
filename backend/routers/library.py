from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from auth.supabase_jwt import get_user_id_dep
from memory.source_store import delete_source
from memory.vector_store import get_all_sources, get_total_chunks
from memory.retrieval_stats_store import get_retrieval_counts

router = APIRouter()


class DeleteSourceRequest(BaseModel):
    source_id: str = Field(min_length=1)


@router.get("/library")
async def library(user_id: str = Depends(get_user_id_dep)) -> dict:
    sources = get_all_sources(user_id=user_id)
    retrieval_counts = get_retrieval_counts(user_id)
    for source in sources:
        source["retrieval_count"] = retrieval_counts.get(source["source_id"], 0)
    return {
        "sources": sources,
        "total_chunks": get_total_chunks(user_id=user_id),
        "total_sources": len(sources),
    }


@router.get("/library/clusters")
async def library_clusters(user_id: str = Depends(get_user_id_dep)) -> dict:
    sources = get_all_sources(user_id=user_id)

    # Build tag → sources mapping (normalised to lowercase)
    tag_to_sources: dict[str, list[dict]] = {}
    for source in sources:
        for tag in source.get("tags", []):
            normalised = tag.lower().strip()
            if not normalised:
                continue
            if normalised not in tag_to_sources:
                tag_to_sources[normalised] = []
            tag_to_sources[normalised].append(source)

    # Only keep tags that appear in 2+ sources
    clustered_tags = {tag: srcs for tag, srcs in tag_to_sources.items() if len(srcs) >= 2}

    # Build cluster list
    clusters = []
    for tag, srcs in clustered_tags.items():
        total_chunks = sum(s.get("chunk_count", 0) for s in srcs)
        clusters.append({
            "tag": tag,
            "source_count": len(srcs),
            "total_chunks": total_chunks,
            "sources": [
                {
                    "source_id": s["source_id"],
                    "source_title": s["source_title"],
                    "source_type": s["source_type"],
                    "ingested_at": s["ingested_at"],
                }
                for s in srcs
            ],
        })

    # Sort clusters by source_count descending
    clusters.sort(key=lambda c: c["source_count"], reverse=True)

    # Unclustered sources: every tag they have appears in fewer than 2 sources total
    unclustered = []
    for source in sources:
        source_tags = [t.lower().strip() for t in source.get("tags", []) if t.strip()]
        if not any(t in clustered_tags for t in source_tags):
            unclustered.append({
                "source_id": source["source_id"],
                "source_title": source["source_title"],
                "source_type": source["source_type"],
                "ingested_at": source["ingested_at"],
            })

    return {
        "clusters": clusters,
        "unclustered_sources": unclustered,
        "total_sources": len(sources),
        "total_tags": len(clustered_tags),
    }


@router.delete("/library/source")
async def delete_library_source(
    req: DeleteSourceRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    """Delete one source by id, with its chunks and everything derived from them."""
    chunks_removed = await run_in_threadpool(delete_source, req.source_id, user_id)
    if chunks_removed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return {
        "deleted": True,
        "chunks_removed": chunks_removed,
        "message": f"Removed {chunks_removed} chunk{'s' if chunks_removed != 1 else ''}",
    }
