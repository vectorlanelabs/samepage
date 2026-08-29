"""Environment-driven application settings (D14/D16/D17 — see docs/PLAN-v2-samepage.md for
the current, superseding architecture; env var prefix renamed DD_ -> SP_ with the SamePage pivot).

Everything is read from the environment once, at import time, with sensible
defaults for local development. The secret key is generated and persisted to
``data/secret.key`` on first use so it survives restarts.
"""

from __future__ import annotations

import os
import secrets
import stat
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _default_db_path() -> Path:
    return REPO_ROOT / "data" / "samepage.db"


def _ensure_private_dir(path: Path) -> None:
    """Create path if missing, and tighten it to 0o700 if it has any group/other bits."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(os.stat(path).st_mode) & 0o077:
        os.chmod(path, 0o700)


def _secret_key() -> str:
    """SP_SECRET if set; otherwise a persisted random key at data/secret.key.

    The key file is private: created with mode 0o600, and an existing file
    with any group/other permission bits is tightened back to 0o600 on load.
    """
    env_secret = os.environ.get("SP_SECRET")
    if env_secret:
        return env_secret
    data_dir = REPO_ROOT / "data"
    _ensure_private_dir(data_dir)
    key_file = data_dir / "secret.key"
    if key_file.exists():
        mode = stat.S_IMODE(os.stat(key_file).st_mode)
        if mode & 0o077:
            os.chmod(key_file, 0o600)
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("SP_DB_PATH", str(_default_db_path())))
    secret_key: str = field(default_factory=_secret_key)
    api_key: str = field(default_factory=lambda: os.environ.get("SP_API_KEY", ""))
    port: int = field(default_factory=lambda: int(os.environ.get("SP_PORT", "8000")))
    env: str = field(default_factory=lambda: os.environ.get("SP_ENV", "development"))
    google_client_id: str = field(default_factory=lambda: os.environ.get("SP_GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.environ.get("SP_GOOGLE_CLIENT_SECRET", ""))
    base_url: str = field(default_factory=lambda: os.environ.get("SP_BASE_URL", ""))

    def __post_init__(self) -> None:
        # SP_BASE_URL wins when set; otherwise derive from the port. Computed
        # here (after all fields) so the default can reference `port`.
        if not self.base_url:
            self.base_url = f"http://localhost:{self.port}"

    @property
    def https_only(self) -> bool:
        return self.env == "production"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()
