"""Every API route must require a user token unless it's explicitly listed here.

This test inspects the app's routes, so a new endpoint added without
Depends(get_user_id_dep) fails the suite until it's protected or added to
PUBLIC_ROUTES with a reason.
"""

import pytest

# Routes that intentionally don't use a user token.
PUBLIC_ROUTES = {
    ("GET", "/health"): "health check for Railway",
    ("GET", "/admin/usage"): "admin-only, protected by x-admin-secret",
    ("GET", "/admin/analytics-data"): "admin-only, protected by x-admin-secret",
}

# Known gaps: routes that should have auth but don't yet. Each one is tracked as
# an expected failure so the suite stays green. When auth is added, the test
# starts passing and pytest reports XPASS(strict) as a failure, which is the
# signal to delete the entry from this dict.
KNOWN_UNPROTECTED: dict[tuple[str, str], str] = {}


def _uses_user_auth(dependant) -> bool:
    from auth.clerk import get_user_id_dep

    for dep in dependant.dependencies:
        if dep.call is get_user_id_dep or _uses_user_auth(dep):
            return True
    return False


def _api_routes():
    from fastapi.routing import APIRoute
    from main import app

    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods):
                routes.append((method, route.path, route))
    return routes


def _cases():
    cases = []
    for method, path, route in _api_routes():
        key = (method, path)
        if key in PUBLIC_ROUTES:
            continue
        marks = []
        if key in KNOWN_UNPROTECTED:
            marks.append(pytest.mark.xfail(reason=KNOWN_UNPROTECTED[key], strict=True))
        cases.append(pytest.param(route, id=f"{method} {path}", marks=marks))
    return cases


@pytest.mark.parametrize("route", _cases())
def test_route_requires_user_token(route):
    assert _uses_user_auth(route.dependant), (
        f"{sorted(route.methods)} {route.path} has no Depends(get_user_id_dep). "
        "Protect it, or add it to PUBLIC_ROUTES with a reason."
    )


def test_allowlists_only_name_routes_that_exist():
    existing = {(m, p) for m, p, _ in _api_routes()}
    stale = (set(PUBLIC_ROUTES) | set(KNOWN_UNPROTECTED)) - existing
    assert not stale, f"Remove entries for routes that no longer exist: {stale}"
