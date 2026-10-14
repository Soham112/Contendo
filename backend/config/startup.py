"""Validate deployment configuration before clients and routes are imported."""
import os
from urllib.parse import urlsplit


class StartupConfigError(RuntimeError):
    pass


def validate_environment() -> None:
    required = ["ENVIRONMENT", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY"]
    production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    billing = ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID_PRO"]
    if production:
        required += ["FRONTEND_ORIGIN", "PUBLISHING_PROVIDER", *billing]
    elif any(os.environ.get(key, "").strip() for key in billing):
        required += ["FRONTEND_ORIGIN", *billing]
    if os.environ.get("PUBLISHING_PROVIDER", "").strip().lower() == "zernio":
        required += ["FRONTEND_ORIGIN", "ZERNIO_API_KEY", "ZERNIO_WEBHOOK_SECRET"]
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        raise StartupConfigError("Backend startup blocked: missing environment variables: " + ", ".join(missing))
    origin = os.environ.get("FRONTEND_ORIGIN", "").strip()
    if origin:
        url = urlsplit(origin)
        if (url.scheme not in ("http", "https") or not url.netloc or url.path not in ("", "/")
                or url.query or url.fragment or url.username or url.password
                or (production and url.scheme != "https")):
            raise StartupConfigError("FRONTEND_ORIGIN must be an origin such as https://www.contendoai.com, without a path.")
    if production or any(os.environ.get(key, "").strip() for key in billing):
        from billing.stripe_gateway import config
        try:
            config()
        except ValueError as exc:
            raise StartupConfigError("STRIPE_TRIAL_DAYS must be a valid integer.") from exc
