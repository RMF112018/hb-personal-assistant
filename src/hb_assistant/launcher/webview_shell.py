"""Optional pywebview desktop shell — lazy-imported, never a hard dependency.

If ``pywebview`` is installed, ``open_shell`` opens the frontend URL in a managed
window and wires the window ``closing`` event to the close policy (Quit vs
Run-in-Background). If absent, callers fall back to the browser/CLI lifecycle.
Nothing in this module is imported at package import time.
"""

from __future__ import annotations

from typing import Callable

from hb_assistant.launcher.models import CloseAction


def pywebview_available() -> bool:
    try:
        import webview  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def open_shell(url: str, *, on_close: Callable[[CloseAction], None]) -> bool:
    """Open a managed pywebview window. Returns False if pywebview is unavailable.

    The window ``closing`` event presents Quit vs Run-in-Background and routes the
    operator's choice to ``on_close``. This function blocks until the window closes.
    """
    if not pywebview_available():
        return False
    import webview  # type: ignore

    window = webview.create_window("HB Assistant", url)

    def _on_closing() -> bool:
        # A real shell would prompt; default to background to avoid accidental quit.
        action: CloseAction = "background"
        try:
            confirmed = webview.windows[0].create_confirmation_dialog(  # type: ignore[attr-defined]
                "Close HB Assistant", "Quit fully? (Cancel = run in background)"
            )
            action = "quit" if confirmed else "background"
        except Exception:
            action = "background"
        on_close(action)
        return True

    window.events.closing += _on_closing  # type: ignore[attr-defined]
    webview.start()
    return True
