"""Validate deployment configuration before clients and routes are imported."""
import os
from urllib.parse import urlsplit


class StartupConfigError(RuntimeError):
    pass


def validate_environment() -> None:
    required = ["ENVIRONMENT", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY"]
    production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    billing = ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID_PRO"]
    billing_set = any(os.environ.get(key, "").strip() for key in billing)
    # BILLING_DISABLED=1 is the one way to run production without Stripe: it is
    # explicit, so a deploy that merely lost its Stripe keys still refuses to start.
    billing_off = os.environ.get("BILLING_DISABLED", "").strip() == "1"
    if billing_off and billing_set:
        raise StartupConfigError("BILLING_DISABLED=1 is set together with Stripe settings: remove one or the other.")
    if production:
        required += ["FRONTEND_ORIGIN", "PUBLISHING_PROVIDER", *([] if billing_off else billing)]
    elif billing_set:
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
    if (production and not billing_off) or billing_set:
        from billing.stripe_gateway import config
        try:
            config()
        except ValueError as exc:
            raise StartupConfigError("STRIPE_TRIAL_DAYS must be a valid integer.") from exc
