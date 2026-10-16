"""Account endpoints: the segment question, and the lists it chooses from."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from starlette.concurrency import run_in_threadpool

from agents.ingestion_agent import ingest_content
from auth.supabase_jwt import get_user_id_dep
from config import niches
from memory import source_store
from memory.account_store import get_account, mark_segment_skipped, save_segment, should_ask_segment
from memory.profile_store import DEFAULT_PROFILE, profile_exists, save_profile
from memory.vector_store import delete_source, invalidate_bm25_cache
from utils.business_notes import PROFILE_NOTE_EXTRACTOR, PROFILE_NOTE_TITLE, niche_label, profile_note
from utils.frames import BUSINESS_PROFILE_SOURCE_TYPE

logger = logging.getLogger(__name__)

router = APIRouter()


def _stripped(value: str) -> str:
    return value.strip()


class BusinessProfile(BaseModel):
    business_name: str = Field(min_length=1, max_length=120)
    service_area: str = Field(min_length=1, max_length=120)
    website: HttpUrl | None = None
    services: str = Field(min_length=1, max_length=600)
    differentiators: str = Field(default="", max_length=400)
    typical_customer: str = Field(default="", max_length=400)
    current_offers: str = Field(default="", max_length=400)
    tone: str
    tone_notes: str = Field(default="", max_length=300)

    _strip = field_validator(
        "business_name", "service_area", "services", "differentiators", "typical_customer",
        "current_offers", "tone_notes", mode="before",
    )(_stripped)

    @field_validator("website", mode="before")
    @classmethod
    def _blank_website_is_none(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("tone")
    @classmethod
    def _known_tone(cls, value: str) -> str:
        if value not in niches.TONES_BY_KEY:
            raise ValueError("tone must be one of the listed tones")
        return value


class SegmentRequest(BaseModel):
    segment: Literal["business", "individual"]
    business_niche: str | None = None
    business_niche_other: str | None = Field(default=None, max_length=80)
    business_profile: BusinessProfile | None = None

    @model_validator(mode="after")
    def _business_fields(self) -> "SegmentRequest":
        if self.segment == niches.SEGMENT_INDIVIDUAL:
            self.business_niche = self.business_niche_other = self.business_profile = None
            return self
        if niches.get_niche(self.business_niche) is None:
            raise ValueError("business_niche must be one of the listed niches")
        other = (self.business_niche_other or "").strip()
        if self.business_niche == niches.OTHER_NICHE:
            if not other:
                raise ValueError("business_niche_other is required when the niche is 'other'")
            self.business_niche_other = other
        else:
            self.business_niche_other = None
        if self.business_profile is None:
            raise ValueError("business_profile is required for a business")
        return self


class AccountResponse(BaseModel):
    segment: str | None
    business_niche: str | None
    business_niche_other: str | None
    business_profile: dict | None
    # Whether to show the segment question now (decided here, never by the client).
    ask_segment: bool
    # PUT /account/segment for a business only: whether the business profile
    # reached the user's memory as a source. False means the answer is saved but
    # posts cannot draw on it until it is saved again. None everywhere else.
    memory_saved: bool | None = None


def _response(account: dict, memory_saved: bool | None = None) -> AccountResponse:
    return AccountResponse(
        memory_saved=memory_saved,
        segment=account.get("segment"),
        business_niche=account.get("business_niche"),
        business_niche_other=account.get("business_niche_other"),
        business_profile=account.get("business_profile"),
        ask_segment=should_ask_segment(account),
    )


def _ensure_voice_profile(account: dict, user_id: str) -> None:
    """Give a business user with no voice profile one named after the business,
    so they can generate without the individual first-post flow. A profile that
    already exists is never touched."""
    if profile_exists(user_id):
        return
    business = account["business_profile"]
    save_profile({
        **DEFAULT_PROFILE,
        "name": business["business_name"],
        "role": niche_label(niches.get_niche(account["business_niche"]), account.get("business_niche_other")),
        "location": business["service_area"],
    }, user_id)


def _save_profile_to_memory(account: dict, user_id: str) -> None:
    """Replace the user's business profile note with one built from the account.
    Stored through the normal ingestion path, as the user's own work. The note
    keeps one `sources` row, updated in place on every save."""
    note = profile_note(
        account["business_profile"],
        niches.get_niche(account["business_niche"]),
        account.get("business_niche_other"),
    )
    existing = source_store.find_source_id(user_id, "business_profile")
    if existing is None:
        # A note stored before `sources` existed has chunks but no row.
        delete_source(PROFILE_NOTE_TITLE, user_id=user_id)
    invalidate_bm25_cache(user_id)
    ingest_content(
        note,
        source_type=BUSINESS_PROFILE_SOURCE_TYPE,
        source_title=PROFILE_NOTE_TITLE,
        user_id=user_id,
        memory_context="work",
        replace_source_id=existing,
        original=source_store.SourceOriginal(
            input_type="business_profile",
            extractor=PROFILE_NOTE_EXTRACTOR[0], extractor_version=PROFILE_NOTE_EXTRACTOR[1],
            raw_json={k: account.get(k) for k in ("business_profile", "business_niche", "business_niche_other")},
            title_origin="provided",
            # The form's answers are the user's own statements (rule, not a guess).
            authorship="user_stated", authorship_set_by="rule",
        ),
    )


@router.get("/niches")
async def list_niches() -> dict:
    """Public: the segments, niches (with their content pillars) and tones.
    The landing pages and the onboarding screen both read the list from here."""
    return niches.options()


@router.get("/account", response_model=AccountResponse)
async def read_account(user_id: str = Depends(get_user_id_dep)) -> AccountResponse:
    return _response(get_account(user_id))


@router.put("/account/segment", response_model=AccountResponse)
async def put_segment(req: SegmentRequest, user_id: str = Depends(get_user_id_dep)) -> AccountResponse:
    try:
        account = save_segment(
            user_id,
            req.segment,
            business_niche=req.business_niche,
            business_niche_other=req.business_niche_other,
            business_profile=req.business_profile.model_dump(mode="json") if req.business_profile else None,
        )
    except Exception:
        logger.exception("PUT /account/segment failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="Couldn't save your answer. Please try again.")
    if req.segment != niches.SEGMENT_BUSINESS:
        return _response(account)
    try:
        _ensure_voice_profile(account, user_id)
    except Exception:
        logger.exception("PUT /account/segment: voice profile not created for user %s", user_id)
        raise HTTPException(status_code=500, detail="Couldn't save your answer. Please try again.")
    try:
        await run_in_threadpool(_save_profile_to_memory, account, user_id)
    except Exception:
        logger.exception("PUT /account/segment: business profile note failed for user %s", user_id)
        return _response(account, memory_saved=False)
    return _response(account, memory_saved=True)


@router.post("/account/segment/skip", response_model=AccountResponse)
async def skip_segment(user_id: str = Depends(get_user_id_dep)) -> AccountResponse:
    try:
        account = mark_segment_skipped(user_id)
    except Exception:
        logger.exception("POST /account/segment/skip failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    return _response(account)
