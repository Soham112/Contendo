"""Read-only schema readiness probes. No customer rows are read or written."""
import logging
from db.supabase_client import supabase

logger = logging.getLogger(__name__)
# Columns establish the migration contract even when all tables are empty.
REQUIRED_TABLES = {
    "user_events": "user_id,event_type,metadata",
    "source_nodes": "user_id,source_id,source_summary,topic_id,total_chunks,created_at",
    "topic_nodes": "user_id,topic_id,topic_label,topic_summary,representative_tags,child_source_ids,created_at",
    "accounts": "user_id,segment,business_niche,business_profile,publishing_provider,publishing_ref",
    "connected_accounts": "id,user_id,provider,platform,status",
    "publish_jobs": "id,user_id,approval_id,status,content,media",
    "subscriptions": "user_id,status,stripe_customer_id,stripe_subscription_id",
    "stripe_events": "event_id,type",
    "generation_usage": "user_id,period,count",
    "publish_approvals": "id,user_id,flags,accepted_flag_ids,approved_at",
}


def verify_schema() -> None:
    for table, columns in REQUIRED_TABLES.items():
        try:
            supabase.table(table).select(columns).limit(0).execute()
        except Exception as exc:
            logger.exception("Startup schema probe failed for %s", table)
            raise RuntimeError(
                f"Backend startup blocked: database schema unavailable at {table}. "
                "Apply migrations 007–012 in order to this deployment's Supabase project; "
                "check database access and reload the PostgREST schema cache, then redeploy."
            ) from exc
