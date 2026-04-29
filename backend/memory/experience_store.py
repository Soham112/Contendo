import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Upsert / save
# ---------------------------------------------------------------------------

def upsert_experience_node(
    user_id: str,
    node_type: str,
    entity_name: str,
    role: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    domain_areas: list[str] | None = None,
    description: str | None = None,
    context_label: str | None = None,
    experience_id: str | None = None,
) -> str:
    """Upsert a single experience node. Returns the experience_id.

    If experience_id is supplied the row is updated in place.
    If omitted a new UUID is generated and a new row is inserted.
    domain_areas is stored as a comma-separated string.
    """
    eid = experience_id or str(uuid.uuid4())
    row: dict[str, Any] = {
        "experience_id": eid,
        "user_id": user_id,
        "node_type": node_type,
        "entity_name": entity_name,
        "role": role,
        "start_date": start_date,
        "end_date": end_date,
        "domain_areas": ",".join(domain_areas) if domain_areas else None,
        "description": description,
        "context_label": context_label or _build_context_label(
            node_type, entity_name, role, start_date, end_date
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"upsert_experience_node: {node_type} '{entity_name}' for user_id={user_id}")
    supabase.table("experience_nodes").upsert(
        row, on_conflict="experience_id"
    ).execute()
    return eid


def save_experience_nodes(user_id: str, nodes: list[dict[str, Any]]) -> list[str]:
    """Bulk-upsert a list of experience node dicts. Returns list of experience_ids.

    Each dict should have the same keys as upsert_experience_node kwargs.
    Existing rows for this user are replaced (delete-then-insert) so the
    confirmed list from the UI is always the source of truth.
    """
    logger.info(f"save_experience_nodes: replacing {len(nodes)} nodes for user_id={user_id}")
    # Delete all existing nodes for this user before reinserting so the
    # confirmed list from the frontend confirmation step is authoritative.
    supabase.table("experience_nodes").delete().eq("user_id", user_id).execute()
    ids: list[str] = []
    for node in nodes:
        eid = upsert_experience_node(
            user_id=user_id,
            node_type=node["node_type"],
            entity_name=node["entity_name"],
            role=node.get("role"),
            start_date=node.get("start_date"),
            end_date=node.get("end_date"),
            domain_areas=node.get("domain_areas"),
            description=node.get("description"),
            context_label=node.get("context_label"),
            experience_id=node.get("experience_id"),
        )
        ids.append(eid)
    return ids


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_experience_nodes(user_id: str) -> list[dict[str, Any]]:
    """Return all experience nodes for a user, ordered by start_date desc."""
    result = (
        supabase.table("experience_nodes")
        .select("*")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .execute()
    )
    return [_deserialize(row) for row in (result.data or [])]


def get_experience_nodes_by_type(
    user_id: str, node_type: str
) -> list[dict[str, Any]]:
    """Return experience nodes filtered by node_type (work/personal_project/education)."""
    result = (
        supabase.table("experience_nodes")
        .select("*")
        .eq("user_id", user_id)
        .eq("node_type", node_type)
        .order("start_date", desc=True)
        .execute()
    )
    return [_deserialize(row) for row in (result.data or [])]


def experience_nodes_exist(user_id: str) -> bool:
    """Return True if the user has at least one experience node saved."""
    result = (
        supabase.table("experience_nodes")
        .select("experience_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_experience_node(experience_id: str, user_id: str) -> None:
    """Delete a single experience node by id (scoped to user for safety)."""
    logger.info(f"delete_experience_node: {experience_id} for user_id={user_id}")
    supabase.table("experience_nodes").delete().eq(
        "experience_id", experience_id
    ).eq("user_id", user_id).execute()


# ---------------------------------------------------------------------------
# Prompt injection helper
# ---------------------------------------------------------------------------

def experience_nodes_to_context_string(nodes: list[dict[str, Any]]) -> str:
    """Format experience nodes as a compact context block for prompt injection.

    Grouped by node_type so the draft agent can easily parse work history,
    personal projects, and education separately.
    """
    if not nodes:
        return ""

    groups: dict[str, list[dict[str, Any]]] = {
        "work": [],
        "personal_project": [],
        "education": [],
    }
    for node in nodes:
        groups.setdefault(node["node_type"], []).append(node)

    sections: list[str] = []

    if groups["work"]:
        lines = ["WORK EXPERIENCE:"]
        for n in groups["work"]:
            lines.append(f"  - {n['context_label']}")
            if n.get("description"):
                lines.append(f"    {n['description']}")
            if n.get("domain_areas"):
                lines.append(f"    Skills: {', '.join(n['domain_areas'])}")
        sections.append("\n".join(lines))

    if groups["personal_project"]:
        lines = ["PERSONAL PROJECTS:"]
        for n in groups["personal_project"]:
            lines.append(f"  - {n['context_label']}")
            if n.get("description"):
                lines.append(f"    {n['description']}")
            if n.get("domain_areas"):
                lines.append(f"    Skills: {', '.join(n['domain_areas'])}")
        sections.append("\n".join(lines))

    if groups["education"]:
        lines = ["EDUCATION:"]
        for n in groups["education"]:
            lines.append(f"  - {n['context_label']}")
            if n.get("description"):
                lines.append(f"    {n['description']}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deserialize(row: dict[str, Any]) -> dict[str, Any]:
    """Convert stored comma-separated domain_areas back to a list."""
    raw = row.get("domain_areas") or ""
    row["domain_areas"] = [a.strip() for a in raw.split(",") if a.strip()]
    return row


def _build_context_label(
    node_type: str,
    entity_name: str,
    role: str | None,
    start_date: str | None,
    end_date: str | None,
) -> str:
    """Generate a human-readable label when one isn't explicitly provided."""
    date_range = ""
    if start_date or end_date:
        end = end_date or "present"
        date_range = f" · {start_date}–{end}" if start_date else f" · until {end}"

    if node_type == "education":
        return f"{role or 'Student'} at {entity_name}{date_range}"
    if role:
        return f"{role} at {entity_name}{date_range}"
    return f"{entity_name}{date_range}"
