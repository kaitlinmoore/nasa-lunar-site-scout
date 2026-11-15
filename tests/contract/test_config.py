# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
from pathlib import Path

from lss import config


def test_env_file_override(monkeypatch, tmp_path):
    env = tmp_path / "custom.env"
    env.write_text("LSS_DATA_DIR=" + str(tmp_path / "shared") + "\n")
    monkeypatch.setenv("LSS_ENV_FILE", str(env))
    monkeypatch.delenv("LSS_DATA_DIR", raising=False)
    config.get_settings.cache_clear()
    try:
        s = config.get_settings()
        assert s.env_file == env
        assert s.data_dir == tmp_path / "shared"
        assert s.kernels_dir == tmp_path / "shared" / "kernels"
    finally:
        config.get_settings.cache_clear()


def test_default_env_file_is_repo_root(monkeypatch):
    monkeypatch.delenv("LSS_ENV_FILE", raising=False)
    assert config.env_file_path() == config.REPO_ROOT / ".env"
    assert (config.REPO_ROOT / "pyproject.toml").is_file()


def test_default_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("LSS_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("LSS_DATA_DIR", raising=False)
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().data_dir == Path(r"C:\dev\GitHub\lss-data")
    finally:
        config.get_settings.cache_clear()


def test_empty_values_fall_back_to_defaults(monkeypatch, tmp_path):
    env = tmp_path / "blank.env"
    env.write_text("LSS_DATA_DIR=\nLSS_CORS_ORIGINS=\n")
    monkeypatch.setenv("LSS_ENV_FILE", str(env))
    monkeypatch.delenv("LSS_DATA_DIR", raising=False)
    monkeypatch.delenv("LSS_CORS_ORIGINS", raising=False)
    config.get_settings.cache_clear()
    try:
        s = config.get_settings()
        assert s.data_dir == config.DEFAULT_DATA_DIR
        assert s.cors_origins == ("http://localhost:5173",)
    finally:
        config.get_settings.cache_clear()
