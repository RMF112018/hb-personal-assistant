"""Cross-container contact matching guards."""

from __future__ import annotations


def same_container(a: str, b: str) -> bool:
    return a == b


def allow_cross_container_link(*, left_container: str, right_container: str, policy_allow: bool) -> bool:
    if left_container == right_container:
        return True
    return policy_allow
