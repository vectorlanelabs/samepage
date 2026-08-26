"""Settings directory-permission hygiene (fix B): data/ is tightened to 0o700."""

import os

from app.settings import _ensure_private_dir


def test_ensure_private_dir_tightens_existing(tmp_path):
    tmp = tmp_path / "existing"
    tmp.mkdir()
    os.chmod(tmp, 0o755)
    _ensure_private_dir(tmp)
    mode = os.stat(tmp).st_mode
    assert mode & 0o077 == 0
    assert mode & 0o700 == 0o700


def test_ensure_private_dir_creates(tmp_path):
    new = tmp_path / "new"
    _ensure_private_dir(new)
    assert new.exists()
    assert os.stat(new).st_mode & 0o077 == 0
