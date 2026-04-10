import json
import logging
import os
import re

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from auth.clerk import get_user_id_dep
from memory.profile_store import load_profile, profile_exists, save_profile
from utils.file_extractor import extract_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter()

_anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@router.get("/profile")
async def get_profile(user_id: str = Depends(get_user_id_dep)) -> dict:
    logger.info(f"GET /profile for user_id={user_id}")
    exists = profile_exists(user_id)
    profile = load_profile(user_id=user_id)
    logger.info(f"GET /profile: has_profile={exists}, name={profile.get('name', '')!r} for user_id={user_id}")
    return {"profile": profile, "has_profile": exists}


@router.post("/profile")
async def post_profile(
    profile: dict,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    name = profile.get("name", "").strip()
    logger.info(f"POST /profile: saving for user_id={user_id}, name={name!r}")

    try:
        save_profile(profile, user_id=user_id)
        data_dir = os.environ.get("DATA_DIR", "data")
        profile_path = f"{data_dir}/profiles/profile_{user_id}.json"
        logger.info(f"POST /profile: saved successfully at {profile_path} for user_id={user_id}")
    except Exception as e:
        logger.error(f"POST /profile: save failed for user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Profile save failed")

    # Read back immediately to verify the write landed on disk
    saved = load_profile(user_id=user_id)
    if not saved.get("name", "").strip() == profile.get("name", "").strip():
        logger.error(
            f"POST /profile: save verification FAILED for user_id={user_id} "
            f"(wrote name={profile.get('name')!r}, read back name={saved.get('name')!r})"
        )
        raise HTTPException(status_code=500, detail="Profile save verification failed")

    logger.info(f"POST /profile: saved and verified for user_id={user_id}")
    return {"saved": True, "user_id": user_id}


@router.post("/extract-resume")
async def extract_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    """
    Accept a PDF resume, extract text via PyMuPDF, pass to Claude Sonnet to
    extract structured profile fields, and return the parsed dict.
    Does NOT save to profile — the frontend merges and saves via POST /profile.
    """
    logger.info(f"POST /extract-resume for user_id={user_id}, filename={file.filename!r}")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported.")

    file_bytes = await file.read()

    try:
        resume_text = extract_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if len(resume_text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this PDF. Please try a different file.",
        )

    prompt = f"""You are extracting structured profile information from a resume to populate a personal content generation platform. The goal is to capture how this person thinks and works, not just their job titles.

Extract the following fields. For fields you cannot find, return null. Do not invent information that is not in the resume.

Return ONLY valid JSON with exactly these fields, no preamble, no markdown:
{{
  "name": "full name",
  "role": "current or most recent job title",
  "bio": "2-3 sentence professional summary in first person, human-sounding, not corporate. Based only on what is in the resume.",
  "location": "city and state or country if present, otherwise null",
  "topics_of_expertise": ["3-6 specific topic areas derived from their actual work, skills, and projects — not generic labels"],
  "voice_descriptors": ["2-3 phrases reflecting how someone in their specific role and domain naturally speaks — infer from their domain and seniority"],
  "opinions": ["1-2 professional opinions they likely hold based on their work — write these as general beliefs, never as specific incidents or stories. Example: 'Feature engineering matters more than model selection in most production ML work' not 'At my last job we improved AUC by switching approaches'"],
  "writing_samples": []
}}

IMPORTANT: The opinions field must contain general professional beliefs only. Never write opinions as personal anecdotes, specific incidents, or stories with numbers. Those will be fabricated since you are only reading a resume, not the person's actual experience notes.

Resume text:
{resume_text}"""

    logger.info(f"POST /extract-resume: extracted text preview for user_id={user_id}: {resume_text[:200]!r}")

    try:
        message = _anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        logger.info(f"POST /extract-resume: raw response length={len(raw)}, stop_reason={message.stop_reason!r}, preview={raw[:200]!r}")
    except Exception as e:
        logger.error(f"POST /extract-resume: Anthropic API error for user_id={user_id}: {e}")
        raise HTTPException(
            status_code=422,
            detail="Resume extraction failed. Please try again or skip.",
        )

    # 3-attempt JSON parse — same pattern as scorer_agent.py
    extracted = None

    # Attempt 1: direct parse
    try:
        extracted = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: strip markdown code fences
    if extracted is None:
        code_block = re.search(r'```(?:json)?\s*(\{.*\})\s*```', raw, re.DOTALL)
        if code_block:
            try:
                extracted = json.loads(code_block.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

    # Attempt 3: extract any embedded JSON object
    if extracted is None:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                extracted = json.loads(json_match.group())
            except (json.JSONDecodeError, ValueError):
                pass

    if extracted is None:
        logger.error(f"POST /extract-resume: all parse attempts failed for user_id={user_id}. raw response: {raw!r}")
        raise HTTPException(
            status_code=422,
            detail="Resume extraction failed — could not parse Claude response. Please try again or skip.",
        )

    logger.info(f"POST /extract-resume: success for user_id={user_id}, name={extracted.get('name')!r}")
    return extracted
