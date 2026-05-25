"""BodyMentionDetector: deterministic detection of Bobby mentions and simple action/waiting signals.

Input: only the already-redacted and truncated body_preview_redacted from persisted Email.
Output: detection result + confidence + optional signals (for "direct ask" / "waiting-on" classification).
Never receives or logs full body text.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .aliases import AliasResolver, DEFAULT_BOBBY_ALIASES


class BodyMentionDetector:
    """Detects Bobby mentions (and lightweight signals) in redacted preview text only."""

    def __init__(self, resolver: Optional[AliasResolver] = None):
        self.resolver = resolver or AliasResolver(DEFAULT_BOBBY_ALIASES)

    def detect(self, preview_redacted: Optional[str]) -> Dict[str, Any]:
        mentioned = self.resolver.matches(preview_redacted)

        signals: List[str] = []
        if preview_redacted:
            p = preview_redacted.lower()
            # Very conservative heuristics for "direct ask" or "waiting on other" candidates
            if any(phrase in p for phrase in ["can you", "could you", "please ", "waiting on", "waiting for", "review by", "let me know"]):
                signals.append("possible_direct_ask_or_waiting")

        confidence = 0.85 if mentioned else 0.15

        return {
            "body_mention_detected": mentioned,
            "confidence": confidence,
            "signals": signals,
        }
