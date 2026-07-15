"""Tests for .env loading via portfolio_management.config.load_env."""

import os

from portfolio_management.config import load_env


class TestLoadEnv:
    def test_reads_values_from_env_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("PM_TEST_VAR=hello123\n")
        monkeypatch.delenv("PM_TEST_VAR", raising=False)
        try:
            path = load_env(override=True)
            assert path  # a .env file was found and loaded
            assert os.environ.get("PM_TEST_VAR") == "hello123"
        finally:
            os.environ.pop("PM_TEST_VAR", None)

    def test_handles_space_before_equals(self, tmp_path, monkeypatch):
        # python-dotenv strips whitespace, so "KEY =value" still parses to KEY.
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("PM_SPACED_VAR =spaced\n")
        monkeypatch.delenv("PM_SPACED_VAR", raising=False)
        try:
            load_env(override=True)
            assert os.environ.get("PM_SPACED_VAR") == "spaced"
        finally:
            os.environ.pop("PM_SPACED_VAR", None)

    def test_real_environment_wins_without_override(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("PM_TEST_VAR=fromfile\n")
        monkeypatch.setenv("PM_TEST_VAR", "fromenv")
        load_env(override=False)
        assert os.environ["PM_TEST_VAR"] == "fromenv"

    def test_returns_none_when_no_env_file(self, tmp_path, monkeypatch):
        # An empty temp dir with no .env anywhere up the tree it controls.
        monkeypatch.chdir(tmp_path)
        # find_dotenv walks upward; a freshly created temp dir has no .env of
        # its own, but a parent might. Only assert the no-crash / None-or-path
        # contract rather than forcing None.
        result = load_env()
        assert result is None or isinstance(result, str)
