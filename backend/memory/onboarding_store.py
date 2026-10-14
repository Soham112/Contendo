"""User-scoped onboarding analytics and optional personalization state."""
from db.supabase_client import supabase
from memory.feedback_store import get_recent_posts
from memory.profile_store import load_profile


def record_step(user_id: str, step: str, outcome: str, segment: str | None = None) -> None:
    supabase.table('user_events').insert({
        'user_id': user_id, 'event_type': 'onboarding_step', 'page_url': '/first-post',
        'metadata': {'step': step, 'outcome': outcome, 'segment': segment},
    }).execute()


def personalization_status(user_id: str) -> dict:
    profile = load_profile(user_id)
    return {
        'offer_voice': len(get_recent_posts(user_id, limit=3)) >= 3
        and not profile.get('voice_questionnaire_completed')
        and not profile.get('voice_prompt_dismissed'),
    }
