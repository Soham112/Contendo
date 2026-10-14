"""What each platform accepts, and the words shown to a user when a publish fails.

The limits are the platforms' own published rules, so they are fixed values
checked in code. They are checked on the server before a job is created
(publishing.service.create_job), whatever the browser has already shown.
"""

from dataclasses import dataclass

from publishing.types import ErrorCode, Platform


@dataclass(frozen=True)
class PlatformRules:
    label: str
    max_characters: int
    # "none": text alone is fine. "image_or_video" / "video": a post needs one.
    media_required: str = "none"
    max_images: int = 0


RULES: dict[Platform, PlatformRules] = {
    Platform.INSTAGRAM: PlatformRules("Instagram", 2200, media_required="image_or_video", max_images=10),
    Platform.FACEBOOK: PlatformRules("Facebook", 63206, max_images=10),
    Platform.LINKEDIN: PlatformRules("LinkedIn", 3000, max_images=9),
    Platform.GOOGLE_BUSINESS: PlatformRules("Google Business Profile", 1500, max_images=1),
    Platform.TIKTOK: PlatformRules("TikTok", 2200, media_required="video"),
    Platform.YOUTUBE: PlatformRules("YouTube", 5000, media_required="video"),
    Platform.X: PlatformRules("X", 280, max_images=4),
}


def label(platform: str) -> str:
    """A platform's display name; the raw value for one we have no rules for."""
    try:
        return RULES[Platform(platform)].label
    except ValueError:
        return platform


def problems(platform: Platform, text: str, media: list[dict]) -> list[str]:
    """Why this post cannot go to this platform, in words for the user. [] when it can."""
    rules = RULES[platform]
    found = []
    length = len(text)
    if length > rules.max_characters:
        found.append(
            f"{rules.label} allows {rules.max_characters:,} characters and this post has {length:,}. "
            "Shorten it, or leave this account out."
        )
    images = sum(1 for item in media if item.get("kind") == "image")
    videos = sum(1 for item in media if item.get("kind") == "video")
    if rules.media_required == "video" and not videos:
        found.append(f"{rules.label} posts need a video. Add one, or leave this account out.")
    elif rules.media_required == "image_or_video" and not (images or videos):
        found.append(f"{rules.label} posts need an image or a video. Add one, or leave this account out.")
    if images > rules.max_images and rules.media_required != "video":
        found.append(f"{rules.label} allows {rules.max_images} image{'s' if rules.max_images != 1 else ''} per post.")
    return found


def preview() -> list[dict]:
    """The rules as the publish screen needs them (GET /publishing/platforms)."""
    return [
        {"platform": platform.value, "label": rules.label, "max_characters": rules.max_characters,
         "media_required": rules.media_required, "max_images": rules.max_images}
        for platform, rules in RULES.items()
    ]


# One sentence per error code, telling the user what to do. {platform} is the
# display name of the account's platform ("your account" when there are several).
_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.RECONNECT_REQUIRED: "Reconnect {platform}, then publish this post again.",
    ErrorCode.CONTENT_REJECTED: "{platform} didn't accept this post. Edit it and try again.",
    ErrorCode.DUPLICATE: "{platform} already has this post, so it wasn't posted twice.",
    ErrorCode.PLATFORM_LIMIT: "{platform} has reached its posting limit for now. Try again later.",
    ErrorCode.ACCOUNT_REMOVED: "This account is no longer connected. Connect it again, then publish.",
    ErrorCode.PAYMENT_REQUIRED: "Publishing is paused because your last payment didn't go through. "
                                "Update your payment method and this post will go out.",
    ErrorCode.SUBSCRIPTION_ENDED: "This post was cancelled because your plan ended. Your posts and accounts are still here.",
    ErrorCode.PROVIDER_UNAVAILABLE: "We couldn't reach {platform}. Nothing was posted. Try again in a few minutes.",
    ErrorCode.UNKNOWN: "This post couldn't be published. Try again, and contact us if it keeps happening.",
}


def user_message(error_code: str | None, platform: str | None = None) -> str:
    """What to tell the user about a failed or paused job. "" when there is no error."""
    if not error_code:
        return ""
    try:
        code = ErrorCode(error_code)
    except ValueError:
        code = ErrorCode.UNKNOWN
    return _MESSAGES[code].format(platform=label(platform) if platform else "Your account")
