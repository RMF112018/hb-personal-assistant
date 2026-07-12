"""Subprocess-isolated, bounded parser extraction for on-demand *complete reads* (Phase B / B2).

This is the READ-time extraction boundary. It is deliberately a DISTINCT entry point from the
index-time ``obsidian_mcp.source_indexer._extract`` path: index-time parsing stays gated OFF
(``source_index_enable_synchronous_parser_extraction`` default False) so bootstrap can never be turned
into an expensive/hanging parser run by toggling an old flag. A frontier-model client asking to read a
PDF/DOCX/XLSX/EML end-to-end comes through ``extract_for_complete_read`` only.

Isolation contract (the parent process MUST survive a hostile file):

* the parse runs in a **spawned child process** that ``os.setsid()``s into its own process group, so a
  hard timeout can kill the child *and any descendants* it might create (defense in depth — the selected
  parser libs, pypdf/python-docx/openpyxl/stdlib email, are pure-Python and do not spawn subprocesses);
* the child applies ``RLIMIT_AS`` / ``RLIMIT_CPU`` **before importing the parser libraries** (best-effort
  on Darwin, where ``RLIMIT_AS`` enforcement is weak — the hard guarantee is timeout -> terminate ->
  kill -> process-group reap);
* the parent **validates input size before spawning** (oversized -> ``too_large``, no child at all);
* the child **stops at the output byte budget and returns ``parser_output_too_large`` rather than
  truncating and claiming success** — output is bounded before it is serialized onto the pipe, so the
  pipe can never block on an oversized payload;
* the parent drains the pipe with a timed ``poll`` (never a bare ``join``), closes both endpoints
  deterministically, and classifies clean/timeout/signal/malformed outcomes into a fixed vocabulary.

Returned status vocabulary (no generic ``partial``):
``ok | unsupported_format | parser_timeout | parser_failed | parser_resource_exceeded | parser_output_too_large``.
No absolute host path or traceback ever leaves this module — only a short ``failure_code`` token.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Formats this boundary can extract. XER/archives are handled as explicit non-support by the caller and
# never reach here.
ISOLATED_PARSER_EXTS = frozenset({"pdf", "docx", "xlsx", "eml"})

# Status tokens (single source of truth; mirrored by the read-response state matrix in
# obsidian_mcp.source_connector_models).
STATUS_OK = "ok"
STATUS_UNSUPPORTED = "unsupported_format"
STATUS_TIMEOUT = "parser_timeout"
STATUS_FAILED = "parser_failed"
STATUS_RESOURCE_EXCEEDED = "parser_resource_exceeded"
STATUS_OUTPUT_TOO_LARGE = "parser_output_too_large"
STATUS_TOO_LARGE = "too_large"

# Grace given to a signalled child to actually die before we escalate SIGTERM -> SIGKILL.
_JOIN_GRACE_SECONDS = 2.0


@dataclass(frozen=True)
class IsolatedResult:
    """Deterministic, path-free result of one isolated extraction."""

    status: str
    text: str | None = None
    char_count: int = 0
    output_bytes: int = 0
    failure_code: str | None = None
    # Lower bound on the true extracted size when the output budget was exceeded (for client next-steps).
    observed_output_bytes_lower_bound: int | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


# --------------------------------------------------------------------------------------------------
# Child process
# --------------------------------------------------------------------------------------------------

def _apply_child_limits(max_memory_mb: int) -> None:
    """Apply address-space + CPU rlimits BEFORE any parser import. Best-effort; never raises."""
    try:
        import resource
    except Exception:  # pragma: no cover - resource missing (non-posix); parent still bounds by timeout
        return
    if max_memory_mb and max_memory_mb > 0 and hasattr(resource, "RLIMIT_AS"):
        cap = int(max_memory_mb) * 1024 * 1024
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            new_hard = cap if hard == resource.RLIM_INFINITY else min(cap, hard)
            resource.setrlimit(resource.RLIMIT_AS, (min(cap, new_hard), new_hard))
        except (ValueError, OSError):  # pragma: no cover - platform refused the limit
            pass
    if hasattr(resource, "RLIMIT_CPU"):
        # A coarse CPU backstop below the wall-clock timeout; SIGXCPU -> classified resource_exceeded.
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (60, 90))
        except (ValueError, OSError):  # pragma: no cover
            pass


def _run_parser(path: Path, ext: str, max_output_bytes: int) -> dict[str, Any]:
    """Parse one file and enforce the output byte budget. Never truncates-and-succeeds.

    The concrete parsers cap by *characters*; we over-request one extra unit and then enforce the
    authoritative *byte* budget on the UTF-8 encoding, so a document whose extracted text exceeds the
    budget is reported ``parser_output_too_large`` (content withheld) rather than silently clipped.
    """
    char_cap = int(max_output_bytes) + 1  # 1 char >= 1 byte, so this covers the byte budget + sentinel
    if ext == "pdf":
        from hb_assistant.files.parsers.pdf import PDFParser

        raw = PDFParser().parse(path, char_cap)
    elif ext == "docx":
        from hb_assistant.files.parsers.docx import DOCXParser

        raw = DOCXParser().parse(path, char_cap)
    elif ext == "xlsx":
        from hb_assistant.files.parsers.xlsx import XLSXParser

        raw = XLSXParser().parse(path, char_cap)
    elif ext == "eml":
        from hb_assistant.obsidian_mcp.source_email_archive import parse_email_file

        em = parse_email_file(path)
        if em.parse_status == "failed":
            return {"status": STATUS_FAILED, "failure_code": "eml_parse_failed"}
        raw = {"text_excerpt": em.canonical_body_markdown or "", "char_count": 0}
    else:
        return {"status": STATUS_UNSUPPORTED}

    if raw.get("failure_code"):
        return {"status": STATUS_FAILED, "failure_code": str(raw["failure_code"])}

    text = raw.get("text_excerpt")
    if text is None:
        return {"status": STATUS_FAILED, "failure_code": "no_text_extracted"}
    text = str(text)
    encoded_len = len(text.encode("utf-8"))
    if encoded_len > int(max_output_bytes):
        return {
            "status": STATUS_OUTPUT_TOO_LARGE,
            "observed_output_bytes_lower_bound": encoded_len,
        }
    return {"status": STATUS_OK, "text": text, "char_count": len(text), "output_bytes": encoded_len}


def _worker_main(path_str: str, ext: str, max_output_bytes: int, max_memory_mb: int, send: Any) -> None:
    """Child entry point (module-level so ``spawn`` can pickle it). Sends exactly one result dict."""
    try:
        os.setsid()  # own session/process group -> parent can killpg the whole subtree on timeout
    except OSError:  # pragma: no cover - already a session leader
        pass
    _apply_child_limits(max_memory_mb)
    try:
        result = _run_parser(Path(path_str), ext, max_output_bytes)
    except MemoryError:
        result = {"status": STATUS_RESOURCE_EXCEEDED, "failure_code": "memory"}
    except BaseException as exc:  # noqa: BLE001 - never let the child raise past this point
        result = {"status": STATUS_FAILED, "failure_code": type(exc).__name__}
    try:
        send.send(result)
    except Exception:  # pragma: no cover - parent already gone / pipe closed
        pass
    finally:
        try:
            send.close()
        except Exception:  # pragma: no cover
            pass


# --------------------------------------------------------------------------------------------------
# Parent supervisor
# --------------------------------------------------------------------------------------------------

def _signal_group(proc: Any, sig: int) -> None:
    """Signal the child's process group (child == group leader after setsid). Safe: targets the child's
    own pgid (== child pid), never the parent's group. Falls back to signalling the child directly."""
    pid = proc.pid
    if pid is None:
        return
    try:
        # After the child's setsid(), its pgid equals its pid. If setsid hasn't happened yet, no group
        # with id==pid exists -> killpg raises ESRCH and we fall back; we never pass the parent's pgid.
        os.killpg(pid, sig)
        return
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        if sig == signal.SIGKILL:
            proc.kill()
        else:
            proc.terminate()
    except Exception:  # pragma: no cover
        pass


def _reap(proc: Any) -> int | None:
    """Terminate -> (grace) -> kill -> join the child and its group; return its exitcode.

    Reads ``exitcode`` BEFORE ``close()`` (a closed process object refuses ``exitcode``)."""
    if proc.is_alive():
        _signal_group(proc, signal.SIGTERM)
        proc.join(_JOIN_GRACE_SECONDS)
    if proc.is_alive():
        _signal_group(proc, signal.SIGKILL)
        proc.join()
    exitcode = proc.exitcode
    try:
        proc.close()
    except Exception:  # pragma: no cover - already closed
        pass
    return exitcode


def _classify_dead_child(exitcode: int | None) -> IsolatedResult:
    """Child died without sending a payload. Map exit/signal to a resource/crash classification."""
    if exitcode is not None and exitcode < 0:
        sig = -exitcode
        # SIGKILL here is NOT our own timeout kill (that path returns parser_timeout before reaching
        # here) -> an external OOM/limit kill; SIGXCPU is the CPU rlimit. Both are resource exhaustion.
        if sig in (getattr(signal, "SIGKILL", 9), getattr(signal, "SIGXCPU", 24)):
            return IsolatedResult(status=STATUS_RESOURCE_EXCEEDED, failure_code=f"signal_{sig}")
        return IsolatedResult(status=STATUS_FAILED, failure_code=f"signal_{sig}")
    return IsolatedResult(status=STATUS_FAILED, failure_code="no_payload")


def _classify_payload(payload: dict[str, Any]) -> IsolatedResult:
    status = payload.get("status")
    if status == STATUS_OK:
        return IsolatedResult(
            status=STATUS_OK,
            text=payload.get("text"),
            char_count=int(payload.get("char_count", 0)),
            output_bytes=int(payload.get("output_bytes", 0)),
        )
    if status in (STATUS_UNSUPPORTED, STATUS_TIMEOUT, STATUS_FAILED, STATUS_RESOURCE_EXCEEDED,
                  STATUS_OUTPUT_TOO_LARGE):
        return IsolatedResult(
            status=status,
            failure_code=payload.get("failure_code"),
            observed_output_bytes_lower_bound=payload.get("observed_output_bytes_lower_bound"),
        )
    return IsolatedResult(status=STATUS_FAILED, failure_code="malformed_payload")


def extract_for_complete_read(
    path: str | os.PathLike[str],
    ext: str,
    *,
    max_input_bytes: int,
    max_output_bytes: int,
    timeout_s: float,
    max_memory_mb: int,
    _worker: Any = None,
) -> IsolatedResult:
    """Isolated, bounded complete-read extraction for one supported binary/office file.

    ``_worker`` is a test seam (defaults to :func:`_worker_main`) so isolation behaviour — timeout,
    signal death, malformed payload, oversize output — can be exercised deterministically.
    """
    ext = str(ext or "").lower().lstrip(".")
    if ext not in ISOLATED_PARSER_EXTS:
        return IsolatedResult(status=STATUS_UNSUPPORTED)

    # Input-size gate BEFORE spawning anything.
    try:
        size = os.stat(path).st_size
    except OSError as exc:
        return IsolatedResult(status=STATUS_FAILED, failure_code=type(exc).__name__)
    if size > int(max_input_bytes):
        return IsolatedResult(
            status=STATUS_TOO_LARGE, observed_output_bytes_lower_bound=size
        )

    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    target = _worker if _worker is not None else _worker_main
    proc = ctx.Process(
        target=target,
        args=(str(path), ext, int(max_output_bytes), int(max_memory_mb), send),
        daemon=True,
    )
    proc.start()
    send.close()  # parent drops its copy so the pipe reports EOF when the child (and its send) is gone

    payload: dict[str, Any] | None = None
    timed_out = False
    try:
        if recv.poll(timeout_s):
            try:
                payload = recv.recv()
            except EOFError:
                payload = None  # child died before sending
        else:
            timed_out = True
    finally:
        try:
            recv.close()
        except Exception:  # pragma: no cover
            pass

    if timed_out:
        _signal_group(proc, signal.SIGTERM)
    exitcode = _reap(proc)

    if timed_out:
        return IsolatedResult(status=STATUS_TIMEOUT, failure_code="wall_clock")
    if payload is None:
        return _classify_dead_child(exitcode)
    if not isinstance(payload, dict):
        return IsolatedResult(status=STATUS_FAILED, failure_code="malformed_payload")
    return _classify_payload(payload)
