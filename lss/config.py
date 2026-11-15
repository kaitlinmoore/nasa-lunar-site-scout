"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Runtime configuration.

`.env` lookup order:
1. the file named by the `LSS_ENV_FILE` environment variable, if set;
2. otherwise `.env` at the repo root (the directory containing `pyproject.toml`).

Values already present in the process environment win over the file, so a
deployed container can set everything through real environment variables.

`LSS_DATA_DIR` is the shared data folder used by every worktree. It holds
`data/` (DEMs, catalogs), `cache/` (computed results) and `kernels/` (SPICE).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
DEFAULT_DATA_DIR = Path(r"C:\dev\GitHub\lss-data")


def env_file_path() -> Path:
    """Return the `.env` path that `load_env` reads (it may not exist)."""
    override = os.environ.get("LSS_ENV_FILE")
    return Path(override).expanduser() if override else REPO_ROOT / ".env"


def load_env() -> Path | None:
    """Load `.env` into the process environment without overriding set variables.

    Returns the path loaded, or None when no file was found.
    """
    path = env_file_path()
    if path.is_file():
        load_dotenv(path, override=False)
        return path
    return None


@dataclass(frozen=True)
class Settings:
    env_file: Path | None
    data_dir: Path
    cesium_ion_token: str | None
    anthropic_api_key: str | None
    cors_origins: tuple[str, ...]

    @property
    def dem_dir(self) -> Path:
        return self.data_dir / "data"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def kernels_dir(self) -> Path:
        return self.data_dir / "kernels"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env_file = load_env()
    data_dir = Path(os.environ.get("LSS_DATA_DIR") or DEFAULT_DATA_DIR).expanduser()
    origins = os.environ.get("LSS_CORS_ORIGINS") or "http://localhost:5173"
    return Settings(
        env_file=env_file,
        data_dir=data_dir,
        cesium_ion_token=os.environ.get("CESIUM_ION_TOKEN") or None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
