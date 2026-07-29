from pathlib import Path
from hb_assistant.apple_mcc.ops.locks import FileLock, LockError
import pytest

def test_lock(tmp_path):
    p = tmp_path / "l.lock"
    a = FileLock(p)
    a.acquire()
    b = FileLock(p)
    with pytest.raises(LockError):
        b.acquire()
    a.release()
