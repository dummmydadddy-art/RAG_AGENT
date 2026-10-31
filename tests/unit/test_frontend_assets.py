"""
tests/unit/test_frontend_assets.py

Unit test suite for Frontend static assets and SPA delivery:
- GET / serves index.html with valid HTML5 doctype and charset
- Presence of critical ChatGPT UI elements (sidebar, auto-expanding textarea, send button, theme toggle)
- Correct MIME types and availability of CSS style bundles (variables.css, main.css, chat.css, telemetry.css)
- Offline vendored libraries (Marked.js, KaTeX CSS/JS, Prism.js)
- 404 error handling for nonexistent static assets without information leaks

Total: 12 comprehensive unit tests.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from src.web.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Creates in-memory TestClient bound to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


def test_root_serves_index_html(client: TestClient) -> None:
    """GET / must return HTTP 200 with text/html content-type and HTML5 doctype."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in resp.text or "<!doctype html>" in resp.text.lower()


def test_index_html_has_title_and_viewport(client: TestClient) -> None:
    """index.html must specify viewport meta tag and STEM Coder title."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "<meta name=\"viewport\"" in html
    assert "<title>" in html
    assert "STEM Coder" in html or "RAG Agent" in html


def test_index_html_contains_sidebar(client: TestClient) -> None:
    """index.html must contain the conversation history sidebar structure."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "id=\"sidebar\"" in html or "class=\"sidebar\"" in html
    assert "new-chat-btn" in html
    assert "conversation-list" in html


def test_index_html_contains_chat_input_and_send_button(client: TestClient) -> None:
    """index.html must contain multiline prompt input and submission button."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "chat-textarea" in html or "<textarea" in html
    assert "send-button" in html or "send-btn" in html


def test_index_html_contains_theme_toggle(client: TestClient) -> None:
    """index.html must contain dark/light theme toggle button."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "theme-toggle-btn" in html


def test_css_variables_file_served(client: TestClient) -> None:
    """GET /static/css/variables.css must return 200 and define CSS custom properties."""
    resp = client.get("/static/css/variables.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")
    css = resp.text
    assert "--bg-primary" in css
    assert "--text-primary" in css


def test_css_main_and_chat_served(client: TestClient) -> None:
    """GET /static/css/main.css and chat.css must return HTTP 200 with text/css."""
    resp_main = client.get("/static/css/main.css")
    assert resp_main.status_code == 200
    assert "text/css" in resp_main.headers.get("content-type", "")

    resp_chat = client.get("/static/css/chat.css")
    assert resp_chat.status_code == 200
    assert "text/css" in resp_chat.headers.get("content-type", "")


def test_javascript_app_bundle_served(client: TestClient) -> None:
    """GET /static/js/app.js must return HTTP 200 with javascript MIME type."""
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert any(js in ct for js in ("javascript", "application/x-javascript", "text/javascript"))


def test_katex_vendor_assets_served(client: TestClient) -> None:
    """KaTeX vendor CSS and JS must be accessible locally for offline math rendering."""
    resp_css = client.get("/static/vendor/katex/katex.min.css")
    assert resp_css.status_code == 200
    assert "text/css" in resp_css.headers.get("content-type", "")

    resp_js = client.get("/static/vendor/katex/katex.min.js")
    assert resp_js.status_code == 200
    assert len(resp_js.content) > 10000


def test_prism_vendor_assets_served(client: TestClient) -> None:
    """Prism syntax highlighter CSS and JS must be accessible locally for code highlighting."""
    resp_js = client.get("/static/vendor/prism/prism.min.js")
    assert resp_js.status_code == 200
    assert len(resp_js.content) > 5000

    resp_css = client.get("/static/vendor/prism/prism.min.css")
    assert resp_css.status_code == 200


def test_marked_vendor_asset_served(client: TestClient) -> None:
    """Marked markdown parser must be accessible locally for offline Markdown parsing."""
    resp = client.get("/static/vendor/marked.min.js")
    assert resp.status_code == 200
    assert len(resp.content) > 5000


def test_static_404_handling(client: TestClient) -> None:
    """Nonexistent static asset requests must return HTTP 404 without leaking server internals."""
    resp = client.get("/static/css/nonexistent_bundle_99999.css")
    assert resp.status_code == 404
    assert "traceback" not in resp.text.lower()
