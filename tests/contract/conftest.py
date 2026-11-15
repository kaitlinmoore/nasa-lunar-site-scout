# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
import os

import pytest

from lss import config


@pytest.fixture(autouse=True)
def _isolate_environment():
    """Restore os.environ and the settings cache after each test.

    `load_env()` (python-dotenv) writes variables straight into os.environ, which monkeypatch
    cannot undo, so a test that loads a temporary .env would otherwise leak e.g. LSS_DATA_DIR
    into every later test.
    """
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    config.get_settings.cache_clear()
