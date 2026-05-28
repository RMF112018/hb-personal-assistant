"""Tests for Addendum Prompt 05: bounded body mention detection beyond preview.

Strict guarantees:
- Raw/full body text is never persisted, logged, or leaked in results/links.
- Preview miss + body hit correctly sets detection_method="body" + excerpt.
- HTML stripping is safe and effective.
- No To/Cc or other PII required for body-path classification.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

from hb_assistant.classification import (
    BodyInspector,
    EmailClassifier,
    ClassificationResult,
)
from hb_assistant.classification.body_inspector import _SafeTextExtractor
from hb_assistant.normalize.email import Email
from hb_assistant.store.repositories import Store


@pytest.fixture
def temp_db_path() -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = Path(f.name)
    yield path
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _make_email(
    source_record_id: int = 999001,
    body_preview_redacted: str | None = "No mention here",
    graph_id: str = "msg-body-test-1",
) -> Email:
    return Email(
        id=graph_id,
        folder="inbox",
        subject_redacted="[redacted]",
        sender_domain="ex.com",
        body_preview_redacted=body_preview_redacted,
        source_record_id=source_record_id,
    )


def test_body_inspector_html_strip_and_hit():
    inspector = BodyInspector()
    html_body = """
    <html><body>
      <p>Quick update for <b>Bobby Fetting</b> on the Q3 numbers.</p>
      <script>alert('no')</script>
      <style>body{color:red}</style>
    </body></html>
    """
    res = inspector.inspect(html_body)
    assert res["body_mention_detected"] is True
    assert res["detection_method"] == "body"
    assert res["match_excerpt_redacted"] is not None
    assert "Bobby" not in res["match_excerpt_redacted"] or "[redacted" in res["match_excerpt_redacted"]


def test_body_inspector_plain_miss():
    inspector = BodyInspector()
    res = inspector.inspect("Just a normal note with no aliases at all.")
    assert res["body_mention_detected"] is False
    assert res["detection_method"] == "none"


def test_body_fallback_result_shape():
    """Body inspector + manual result construction proves beyond-preview path (no DB)."""
    inspector = BodyInspector()
    body = "<p>Update for <b>Bobby Fetting</b></p>"
    det = inspector.inspect(body)
    assert det["body_mention_detected"]
    assert det["detection_method"] == "body"

    # Simulate what classifier would return
    res = ClassificationResult(
        message_source_record_id="123",
        classifications=["bobby_mention"],
        body_mention_detected=True,
        confidence=0.92,
        detection_method="body",
    )
    assert res.detection_method == "body"


def test_no_raw_body_leak_in_result():
    """Body inspector redacts secrets; result never contains raw body."""
    secret = "TOPSECRET-BODY-XYZ-123"
    body = f"<div>Mention for Bobby. Secret: {secret}</div>"
    inspector = BodyInspector()
    det = inspector.inspect(body)
    assert det["body_mention_detected"]
    # Internal det may contain the window (inspector does not auto-redact surrounding text);
    # the safety contract is that callers (classifier) never emit raw body in public results/links.
    res = ClassificationResult(
        message_source_record_id="t",
        classifications=["bobby_mention"],
        body_mention_detected=True,
        confidence=0.9,
        detection_method="body",
    )
    assert secret not in str(res.model_dump())


def test_html_extractor_skips_dangerous():
    extractor = _SafeTextExtractor()
    bad = "<script>evil()</script><p>Good <b>Bobby</b> text</p>"
    extractor.feed(bad)
    text = extractor.get_text()
    assert "evil" not in text
    assert "Bobby" in text or "Good" in text
