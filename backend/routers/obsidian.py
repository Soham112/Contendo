"""Obsidian vault ingestion: from a local folder path (opt-in, local development
only) or an uploaded zip. Each note goes through extractors/obsidian.py."""
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents.ingestion_agent import ingest_content
from auth.supabase_jwt import get_user_id_dep
from config import security
from extractors.obsidian import note_original
from tools.obsidian_tool import extract_vault_from_zip, get_vault_stats, get_vault_stats_from_dir, read_vault

router = APIRouter()

MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB
_OBSIDIAN_DISABLED_MSG = (
    "Obsidian vault ingestion from a folder path is disabled on this server. "
    "It reads directly from the server's filesystem, so it only makes sense when "
    "the backend runs on your own machine. Upload the vault as a zip instead."
)


class ObsidianRequest(BaseModel):
    vault_path: str


def _require_local_path_ingest() -> None:
    """Reading a caller-supplied path from the server's disk is opt-in
    (ALLOW_LOCAL_PATH_INGEST=1), whatever ENVIRONMENT says."""
    if not security.current().allow_local_path_ingest:
        raise HTTPException(status_code=403, detail=_OBSIDIAN_DISABLED_MSG)


async def _ingest_notes(notes: list[dict], user_id: str) -> dict:
    total_chunks, processed, all_tags = 0, 0, set()
    for note in notes:
        try:
            result = await run_in_threadpool(
                ingest_content,
                content=note["content"],
                source_type="note",
                source_title=note["filename"],
                user_id=user_id,
                original=note_original(note["raw_content"], note["relative_path"]),
            )
            total_chunks += result["chunks_stored"]
            all_tags.update(result["tags"])
            processed += 1
        except Exception:
            continue
    return {
        "total_files_processed": processed,
        "total_chunks_stored": total_chunks,
        "total_words_processed": sum(n["word_count"] for n in notes),
        "skipped_files": len(notes) - processed,
        "all_tags": sorted(all_tags),
    }


async def _read_zip(file: UploadFile) -> bytes:
    raw = await file.read()
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="Zip file exceeds 50 MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded zip file is empty.")
    return raw


@router.post("/obsidian/preview")
async def obsidian_preview(req: ObsidianRequest, user_id: str = Depends(get_user_id_dep)) -> dict:
    _require_local_path_ingest()
    try:
        return await run_in_threadpool(get_vault_stats, req.vault_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/obsidian/ingest")
async def obsidian_ingest(req: ObsidianRequest, user_id: str = Depends(get_user_id_dep)) -> dict:
    _require_local_path_ingest()
    try:
        notes = await run_in_threadpool(lambda: list(read_vault(req.vault_path)))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _ingest_notes(notes, user_id)


@router.post("/obsidian/preview-zip")
async def obsidian_preview_zip(file: UploadFile = File(...), user_id: str = Depends(get_user_id_dep)) -> dict:
    """Vault stats (name, file count, word count, estimated chunks) from a zip, without ingesting."""
    raw = await _read_zip(file)
    temp_dir = None
    try:
        temp_dir = await run_in_threadpool(extract_vault_from_zip, raw)
        return await run_in_threadpool(get_vault_stats_from_dir, temp_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/obsidian/ingest-zip")
async def obsidian_ingest_zip(file: UploadFile = File(...), user_id: str = Depends(get_user_id_dep)) -> dict:
    """Ingest every note of a vault uploaded as a zip."""
    raw = await _read_zip(file)
    temp_dir = None
    try:
        try:
            temp_dir = await run_in_threadpool(extract_vault_from_zip, raw)
            notes = await run_in_threadpool(lambda: list(read_vault(temp_dir)))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return await _ingest_notes(notes, user_id)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
