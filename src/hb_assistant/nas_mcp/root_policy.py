"""Root access policy for NAS MCP filesystem tools."""

from __future__ import annotations

from .config import NasMcpConfig, RootSpec

READ_ONLY_ROOTS = frozenset({"home", "work"})
READ_WRITE_ROOTS = frozenset({"vault", "outputs"})
ALLOWED_ROOT_KEYS = READ_ONLY_ROOTS | READ_WRITE_ROOTS


class RootPolicyError(Exception):
    """Root access denied."""


def get_root_spec(config: NasMcpConfig, root_key: str) -> RootSpec:
    spec = config.roots.get(root_key)
    if spec is None:
        raise RootPolicyError(f"unknown root_key: {root_key}")
    return spec


def assert_read(config: NasMcpConfig, root_key: str) -> RootSpec:
    return get_root_spec(config, root_key)


def assert_write(config: NasMcpConfig, root_key: str) -> RootSpec:
    spec = get_root_spec(config, root_key)
    if spec.mode != "read_write":
        raise RootPolicyError(f"root_key not writable: {root_key}")
    if root_key not in READ_WRITE_ROOTS:
        raise RootPolicyError(f"writes not permitted for root_key: {root_key}")
    return spec


def is_writable_root(root_key: str) -> bool:
    return root_key in READ_WRITE_ROOTS
