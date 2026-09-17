"""
CSP compliance regression suite.

These tests exist to catch the exact failure mode described in the audit:
someone adds a Google Fonts <link>, a CDN <script>, or an onclick="" during
a future UI tweak, and it silently ships because nothing failed loudly.

Run with: pytest tests/test_csp_compliance.py -v
"""
import re
import os
from pathlib import Path

import pytest

from app import app  # adjust import to match your actual app factory

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

BANNED_DOMAINS = [
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.tailwindcss.com",
    "unsplash.com",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
]

# Matches <style ...> ... </style> blocks
INLINE_STYLE_BLOCK_RE = re.compile(r"<style[\s>]", re.IGNORECASE)

# Matches style="..." attributes
INLINE_STYLE_ATTR_RE = re.compile(r'style\s*=\s*"', re.IGNORECASE)

# Matches <script> blocks that are NOT <script src="...">
# i.e. a script tag whose opening tag has no src attribute before the closing >
INLINE_SCRIPT_RE = re.compile(
    r"<script(?![^>]*\bsrc\s*=)[^>]*>(?!\s*</script>)", re.IGNORECASE
)

# Matches inline event handler attributes like onclick=, onsubmit=, onload=
INLINE_EVENT_HANDLER_RE = re.compile(r'\son[a-z]+\s*=\s*"', re.IGNORECASE)

INERT_SCRIPT_TYPES = {"application/json", "application/ld+json"}

def is_inert_script_tag(tag_text: str) -> bool:
    match = re.search(r'type\s*=\s*"([^"]+)"', tag_text, re.IGNORECASE)
    return bool(match) and match.group(1).lower() in INERT_SCRIPT_TYPES

# Catches src= or srcset= containing http://, https://, or // (protocol-relative)
EXTERNAL_IMG_PATTERN = re.compile(r'<img[^>]+(?:src|srcset)=["\'][^"\']*(?:https?://|//)[^"\']*["\']', re.IGNORECASE)


def all_template_files():
    return sorted(TEMPLATES_DIR.rglob("*.html"))


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


# --------------------------------------------------------------------- #
# 1. Runtime header assertions — hits real routes, not just static scan.
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("route", ["/", "/assessment", "/about", "/print"])
def test_csp_header_present_and_strict(client, route):
    resp = client.get(route)
    csp = resp.headers.get("Content-Security-Policy")
    assert csp is not None, f"No CSP header on {route}"

    assert "'unsafe-inline'" not in csp, f"unsafe-inline present on {route}"
    assert "'unsafe-eval'" not in csp, f"unsafe-eval present on {route}"

    # Every directive we depend on for lockdown should resolve to 'self'
    # or a tightly scoped equivalent — not '*' or left unset (which some
    # browsers treat as falling back to default-src, but don't rely on that).
    for directive in ["script-src", "style-src", "font-src", "connect-src"]:
        assert directive in csp, f"{directive} missing from CSP on {route}"


def test_no_external_domains_in_csp_header(client):
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    for domain in BANNED_DOMAINS:
        assert domain not in csp, f"{domain} referenced directly in CSP header"

@pytest.mark.parametrize("route", ["/print/test-uuid", "/history", "/result/test-uuid"])
def test_sensitive_routes_no_store_get(client, route):
    resp = client.get(route)
    cache_control = resp.headers.get("Cache-Control", "")
    assert "no-store" in cache_control.lower(), f"Cache-Control: no-store missing on GET {route}"
    assert "no-cache" in cache_control.lower(), f"Cache-Control: no-cache missing on GET {route}"
    assert resp.headers.get("Pragma", "").lower() == "no-cache", f"Pragma: no-cache missing on GET {route}"

def test_sensitive_routes_no_store_predict_post(client):
    # Send a POST request to /predict with minimal data.
    # Even if it returns 400 due to validation or CSRF, the after_request hook adds Cache-Control.
    resp = client.post("/predict", data={"BMI": "25"})
    cache_control = resp.headers.get("Cache-Control", "")
    assert "no-store" in cache_control.lower(), "Cache-Control: no-store missing on POST /predict"
    assert "no-cache" in cache_control.lower(), "Cache-Control: no-cache missing on POST /predict"
    assert resp.headers.get("Pragma", "").lower() == "no-cache", "Pragma: no-cache missing on POST /predict"


# --------------------------------------------------------------------- #
# 2. Static template scans — catches violations even on routes/templates
#    not exercised by the route parametrization above.
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_external_domains(template_path):
    content = template_path.read_text(encoding="utf-8")
    for domain in BANNED_DOMAINS:
        assert domain not in content, (
            f"{template_path.name} references external domain '{domain}'"
        )


@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_inline_style_blocks(template_path):
    content = template_path.read_text(encoding="utf-8")
    assert not INLINE_STYLE_BLOCK_RE.search(content), (
        f"{template_path.name} contains an inline <style> block"
    )


@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_inline_style_attributes(template_path):
    content = template_path.read_text(encoding="utf-8")
    match = INLINE_STYLE_ATTR_RE.search(content)
    assert not match, (
        f'{template_path.name} contains an inline style="" attribute '
        f"near: ...{content[max(0, match.start()-30):match.start()+30]}..."
        if match else ""
    )


@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_inline_scripts(template_path):
    content = template_path.read_text(encoding="utf-8")
    # Extract all <script...> opening tags that lack a src attribute
    matches = INLINE_SCRIPT_RE.findall(content)
    for tag_text in matches:
        assert is_inert_script_tag(tag_text), (
            f"{template_path.name} contains an executable inline <script> block: {tag_text}\n"
            f"(script tags must use src=... or have an inert type like application/json)"
        )


@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_inline_event_handlers(template_path):
    content = template_path.read_text(encoding="utf-8")
    match = INLINE_EVENT_HANDLER_RE.search(content)
    assert not match, (
        f"{template_path.name} contains an inline event handler attribute "
        f"(onclick=, onsubmit=, etc.)"
    )

@pytest.mark.parametrize("template_path", all_template_files())
def test_template_has_no_external_images(template_path):
    content = template_path.read_text(encoding="utf-8")
    matches = EXTERNAL_IMG_PATTERN.findall(content)
    assert not matches, (
        f"{template_path.name} contains external images: {matches}"
    )


# --------------------------------------------------------------------- #
# 3. Static asset sanity — the compiled CSS/JS actually exist, so the
#    <link>/<script> tags in base.html don't 404 in production.
# --------------------------------------------------------------------- #

def test_compiled_css_exists():

    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "tailwind.min.css"
    assert css_path.exists(), (
        "static/css/tailwind.min.css missing — run the Tailwind build step"
    )

def test_app_js_exists():
    js_path = Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"
    assert js_path.exists(), "static/js/app.js missing"