from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from memory.vector_store import delete_source, get_all_sources, get_total_chunks
from memory.retrieval_stats_store import get_retrieval_counts

router = APIRouter()


class DeleteSourceRequest(BaseModel):
    source_title: str


@router.get("/library")
async def library(user_id: str = Depends(get_user_id_dep)) -> dict:
    sources = get_all_sources(user_id=user_id)
    retrieval_counts = get_retrieval_counts(user_id)
    for source in sources:
        source["retrieval_count"] = retrieval_counts.get(source["source_title"], 0)
    return {
        "sources": sources,
        "total_chunks": get_total_chunks(user_id=user_id),
        "total_sources": len(sources),
    }


@router.delete("/library/source")
async def delete_library_source(
    req: DeleteSourceRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    chunks_removed = delete_source(req.source_title, user_id=user_id)
    if chunks_removed == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Source not found: {req.source_title}",
        )
    return {
        "deleted": True,
        "chunks_removed": chunks_removed,
        "message": f"Removed {chunks_removed} chunk{'s' if chunks_removed != 1 else ''}",
    }
