"""The publish worker: a loop started with the server that sends due jobs.

Why this and not a separate process or a queue service: the backend is one
uvicorn worker on Railway with Postgres and nothing else. The queue is the
publish_jobs table. Jobs survive a restart because they are rows; two loops
(a second instance, a deploy overlap) cannot take the same job because the
claim is one UPDATE ... FOR UPDATE SKIP LOCKED (migration 008). Each tick runs
in the threadpool, so a slow provider never blocks the event loop.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from memory import publish_store
from publishing.jobs import confirm_job, process_job
from publishing.provider import PublishingConfigError, get_provider, provider_name

logger = logging.getLogger(__name__)

POLL_SECONDS = 15
JOBS_PER_TICK = 5
# A job the provider accepted but has not confirmed (no webhook) is checked
# directly once it has been quiet for this long.
CONFIRM_AFTER = timedelta(minutes=2)
CONFIRMS_PER_TICK = 20


def run_once() -> int:
    """Send every due job (up to JOBS_PER_TICK) and confirm quiet ones.
    Returns how many jobs were attempted. One job's failure never stops the rest."""
    provider = get_provider()
    jobs = publish_store.claim_due_jobs(JOBS_PER_TICK)
    for job in jobs:
        try:
            process_job(job, provider)
        except Exception:
            # Left in "publishing" with whatever it reached; claimed again as
            # stale (no provider reference) or confirmed below (it has one).
            logger.exception("publish job %s: unexpected error", job["id"])
    quiet_since = datetime.now(timezone.utc) - CONFIRM_AFTER
    for job in publish_store.list_unconfirmed_jobs(quiet_since, CONFIRMS_PER_TICK):
        if job.get("provider") != provider.name:
            continue
        try:
            confirm_job(job, provider)
        except Exception:
            logger.exception("publish job %s: confirm failed", job["id"])
    return len(jobs)


async def run_forever() -> None:
    while True:
        try:
            await run_in_threadpool(run_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("publish worker tick failed")
        await asyncio.sleep(POLL_SECONDS)


def start() -> asyncio.Task | None:
    """Start the loop if a provider is configured. With none, publishing is
    off and the server still runs; a misconfigured one raises, which stops startup."""
    if not provider_name():
        logger.warning("PUBLISHING: disabled (PUBLISHING_PROVIDER is not set). Publish jobs will not be sent.")
        return None
    provider = get_provider()
    logger.info("PUBLISHING: provider %s, worker polling every %ds.", provider.name, POLL_SECONDS)
    return asyncio.create_task(run_forever(), name="publish-worker")


__all__ = ["PublishingConfigError", "run_once", "start"]
