from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory.vector_store import delete_source, get_all_sources, get_total_chunks

router = APIRouter()


class DeleteSourceRequest(BaseModel):
    source_title: str


@router.get("/library")
async def library() -> dict:
    sources = get_all_sources(user_id="default")
    return {
        "sources": sources,
        "total_chunks": get_total_chunks(user_id="default"),
        "total_sources": len(sources),
    }


@router.delete("/library/source")
async def delete_library_source(req: DeleteSourceRequest) -> dict:
    chunks_removed = delete_source(req.source_title, user_id="default")
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
