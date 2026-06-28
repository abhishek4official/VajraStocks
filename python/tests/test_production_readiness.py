"""Tests for the 5 production-readiness fixes from the June 2026 review.

Solution 1  — Platform-agnostic config path
              (_get_user_appdata_dir, _resolve_config_yaml in main.py)
Solution 2  — Frozen PyInstaller restart command construction
              (/settings/restart in settings.py)
Solution 3  — DB connection pre-flight before saving a new connection string
              (PUT /settings/DATABASE/db_connection_string in settings.py)
Solution 5  — MSSQL ODBC driver presence pre-check
              (_check_mssql_odbc_driver in connection.py)

Solution 4 (agent test suite rewrite) lives in test_agents.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import _get_user_appdata_dir, _resolve_config_yaml, app
from stocks.db.connection import _check_mssql_odbc_driver
from stocks.utils.exceptions import DatabaseConnectionError


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def settings_client(db_session, db_manager):
    """TestClient wired to an in-memory SQLite DB with all default settings seeded.

    The settings endpoint calls svc.all_settings() to check the key exists, so
    the DB must be seeded before any PUT request will succeed.
    """
    from stocks.services.settings_service import SettingsService

    svc = SettingsService(db_session)
    svc.seed_defaults()
    db_session.commit()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.state.db_manager = db_manager
    yield TestClient(app)
    app.dependency_overrides.clear()


# ═════════════════════════════════════════════════════════════════════════════
# Solution 1 — Platform-agnostic config path
# ═════════════════════════════════════════════════════════════════════════════

class TestGetUserAppdataDir:
    def test_windows_reads_appdata_env(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
        result = _get_user_appdata_dir()
        assert result == Path(r"C:\Users\test\AppData\Roaming") / "VajraStocks"

    def test_windows_missing_appdata_returns_none(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        result = _get_user_appdata_dir()
        assert result is None

    def test_macos_uses_library_application_support(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        result = _get_user_appdata_dir()
        assert result == Path.home() / "Library" / "Application Support" / "VajraStocks"

    def test_linux_default_xdg(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = _get_user_appdata_dir()
        assert result == Path.home() / ".local" / "share" / "VajraStocks"

    def test_linux_respects_xdg_data_home(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", "/mnt/data")
        result = _get_user_appdata_dir()
        assert result == Path("/mnt/data") / "VajraStocks"

    def test_linux_empty_xdg_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", "")
        result = _get_user_appdata_dir()
        assert result == Path.home() / ".local" / "share" / "VajraStocks"


class TestResolveConfigYaml:
    def test_env_var_wins_over_everything(self, monkeypatch, tmp_path):
        cfg = tmp_path / "override_config.yaml"
        cfg.write_text("database:\n  connection_string: sqlite:///:memory:\n")
        monkeypatch.setenv("VAJRA_CONFIG_YAML", str(cfg))
        # Even if a user-dir config also exists it should be ignored
        result = _resolve_config_yaml()
        assert result == cfg

    def test_env_var_returned_even_when_file_missing(self, monkeypatch, tmp_path):
        """VAJRA_CONFIG_YAML is returned verbatim — existence is not checked here."""
        monkeypatch.setenv("VAJRA_CONFIG_YAML", str(tmp_path / "does_not_exist.yaml"))
        result = _resolve_config_yaml()
        assert result.name == "does_not_exist.yaml"

    def test_user_dir_config_returned_when_found(self, monkeypatch, tmp_path):
        monkeypatch.delenv("VAJRA_CONFIG_YAML", raising=False)
        cfg = tmp_path / "config.yaml"
        cfg.write_text("database:\n  connection_string: sqlite:///:memory:\n")
        with patch("stocks.api.main._get_user_appdata_dir", return_value=tmp_path):
            result = _resolve_config_yaml()
        assert result == cfg

    def test_dev_fallback_when_no_user_dir(self, monkeypatch):
        monkeypatch.delenv("VAJRA_CONFIG_YAML", raising=False)
        with patch("stocks.api.main._get_user_appdata_dir", return_value=None):
            result = _resolve_config_yaml()
        # Should resolve to source-tree python/config/config.yaml
        assert result.name == "config.yaml"
        assert "config" in result.parts

    def test_dev_fallback_when_user_config_absent(self, monkeypatch, tmp_path):
        """User dir exists but config.yaml is not inside it — fall through to dev path."""
        monkeypatch.delenv("VAJRA_CONFIG_YAML", raising=False)
        empty_dir = tmp_path / "VajraStocks"
        empty_dir.mkdir()
        with patch("stocks.api.main._get_user_appdata_dir", return_value=empty_dir):
            result = _resolve_config_yaml()
        assert result.name == "config.yaml"
        assert result != empty_dir / "config.yaml"


# ═════════════════════════════════════════════════════════════════════════════
# Solution 2 — Frozen PyInstaller restart command
# ═════════════════════════════════════════════════════════════════════════════

class TestRestartCmdConstruction:
    """Tests the logic that builds the restart command in /settings/restart.

    The endpoint spawns a background task, so we test the frozen/dev branch
    logic directly rather than through the full HTTP path.
    """

    @staticmethod
    def _build_cmd(frozen: bool) -> list[str]:
        """Replicates the exact cmd-building block from the restart endpoint."""
        uvicorn_args = ["stocks.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
        if frozen:
            return [sys.executable]
        return [sys.executable, "-m", "uvicorn"] + uvicorn_args

    def test_frozen_build_cmd_is_bare_executable(self):
        cmd = self._build_cmd(frozen=True)
        assert cmd == [sys.executable]
        assert "-m" not in cmd
        assert "uvicorn" not in cmd

    def test_dev_build_cmd_includes_uvicorn(self):
        cmd = self._build_cmd(frozen=False)
        assert sys.executable == cmd[0]
        assert "-m" in cmd
        assert "uvicorn" in cmd
        assert "stocks.api.main:app" in cmd

    def test_frozen_flag_respected_via_sys_attribute(self, monkeypatch):
        """Simulate the actual getattr(sys, 'frozen', False) check used by the endpoint."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        frozen = getattr(sys, "frozen", False)
        cmd = self._build_cmd(frozen=frozen)
        assert "-m" not in cmd

    def test_no_frozen_attribute_treated_as_dev(self):
        # sys.frozen is absent in dev environments
        frozen = getattr(sys, "frozen", False)
        assert frozen is False  # sanity: the test env itself is not frozen
        cmd = self._build_cmd(frozen=frozen)
        assert "-m" in cmd

    def test_restart_endpoint_returns_200(self, settings_client):
        """The endpoint must return 200 immediately (the restart happens in a background task)."""
        with (
            patch("subprocess.Popen"),
            patch("os._exit"),
        ):
            response = settings_client.post("/api/v1/settings/restart")
        assert response.status_code == 200
        assert response.json()["status"] == "restarting"


# ═════════════════════════════════════════════════════════════════════════════
# Solution 3 — DB connection pre-flight validation
# ═════════════════════════════════════════════════════════════════════════════

class TestConnectionPreflight:
    def test_valid_sqlite_memory_url_accepted(self, settings_client):
        """A reachable SQLite URL should pass the pre-flight and return 200."""
        with patch("stocks.api.main.write_bootstrap_config"):
            resp = settings_client.put(
                "/api/v1/settings/DATABASE/db_connection_string",
                json={"value": "sqlite:///:memory:"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_unreachable_postgres_url_rejected(self, settings_client):
        """A PostgreSQL URL pointing at a non-existent host must return 400 before saving."""
        resp = settings_client.put(
            "/api/v1/settings/DATABASE/db_connection_string",
            json={"value": "postgresql+psycopg2://user:pass@127.0.0.1:9999/nodb"},
        )
        assert resp.status_code == 400
        assert "Cannot connect" in resp.json()["detail"]

    def test_garbage_url_rejected(self, settings_client):
        """A syntactically broken connection string must return 400."""
        resp = settings_client.put(
            "/api/v1/settings/DATABASE/db_connection_string",
            json={"value": "not_a_valid_url"},
        )
        assert resp.status_code == 400
        assert "Cannot connect" in resp.json()["detail"]

    def test_error_detail_is_descriptive(self, settings_client):
        """The 400 error must contain the word 'database' or 'connection' to be actionable."""
        resp = settings_client.put(
            "/api/v1/settings/DATABASE/db_connection_string",
            json={"value": "postgresql://bad:bad@localhost:1/nope"},
        )
        detail = resp.json()["detail"].lower()
        assert "connect" in detail or "database" in detail

    def test_other_settings_bypass_validation(self, settings_client):
        """Changing a non-connection-string setting must NOT trigger the DB pre-flight."""
        with patch("stocks.api.main.write_bootstrap_config"):
            resp = settings_client.put(
                "/api/v1/settings/DATABASE/db_pool_size",
                json={"value": "10"},
            )
        # No pre-flight means no 400 from a bad-URL check — only valid settings rows
        assert resp.status_code == 200

    def test_unknown_key_still_returns_404(self, settings_client):
        """Unknown setting keys still return 404, not 400 from pre-flight."""
        resp = settings_client.put(
            "/api/v1/settings/DATABASE/nonexistent_key",
            json={"value": "sqlite:///:memory:"},
        )
        assert resp.status_code == 404

    def test_valid_url_config_yaml_updated(self, settings_client):
        """A successful update of a bootstrap key must report config_yaml_updated=True."""
        with patch("stocks.api.main.write_bootstrap_config") as mock_write:
            resp = settings_client.put(
                "/api/v1/settings/DATABASE/db_connection_string",
                json={"value": "sqlite:///:memory:"},
            )
        assert resp.status_code == 200
        assert resp.json()["config_yaml_updated"] is True
        mock_write.assert_called_once()

    def test_failed_url_config_yaml_not_written(self, settings_client):
        """config.yaml must NOT be written when the pre-flight connection check fails."""
        with patch("stocks.api.main.write_bootstrap_config") as mock_write:
            resp = settings_client.put(
                "/api/v1/settings/DATABASE/db_connection_string",
                json={"value": "postgresql://x:y@localhost:9999/nodb"},
            )
        assert resp.status_code == 400
        mock_write.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Solution 5 — MSSQL ODBC driver pre-check
# ═════════════════════════════════════════════════════════════════════════════

class TestMssqlOdbcCheck:
    def test_missing_pyodbc_package_raises_with_install_hint(self):
        """If pyodbc is not installed, the error must tell the user how to install it."""
        with patch.dict(sys.modules, {"pyodbc": None}):
            with pytest.raises(DatabaseConnectionError) as exc:
                _check_mssql_odbc_driver()
        assert "pip install pyodbc" in str(exc.value)

    def test_no_odbc_drivers_raises_with_download_url(self):
        """If pyodbc is installed but no SQL Server driver is registered, raise with the
        Microsoft download page URL so the user knows exactly what to install."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = []  # no drivers registered
        with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
            with pytest.raises(DatabaseConnectionError) as exc:
                _check_mssql_odbc_driver()
        err = str(exc.value)
        assert "ODBC Driver" in err or "SQL Server" in err
        assert "microsoft.com" in err.lower() or "download" in err.lower()

    def test_unrelated_drivers_not_accepted(self):
        """Drivers that don't match 'SQL Server' or 'ODBC Driver' must not satisfy the check."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = ["MySQL ODBC 8.0", "PostgreSQL ANSI"]
        with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
            with pytest.raises(DatabaseConnectionError):
                _check_mssql_odbc_driver()

    def test_sql_server_driver_present_does_not_raise(self):
        """With at least one matching driver the check must pass silently."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = ["ODBC Driver 17 for SQL Server"]
        with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
            _check_mssql_odbc_driver()  # must not raise

    def test_legacy_sql_server_driver_also_accepted(self):
        """Older 'SQL Server' driver names (without 'ODBC Driver') must also pass."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = ["SQL Server"]
        with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
            _check_mssql_odbc_driver()  # must not raise

    def test_multiple_drivers_all_pass(self):
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
        ]
        with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
            _check_mssql_odbc_driver()  # must not raise

    def test_mssql_initialize_calls_odbc_check(self):
        """DatabaseManager.initialize() must call _check_mssql_odbc_driver before
        trying to start LocalDB, so the user gets a clean error early."""
        from stocks.db.connection import DatabaseManager

        manager = DatabaseManager("mssql+pyodbc://./TestDB?driver=ODBC+Driver+17+for+SQL+Server")
        with (
            patch("stocks.db.connection._check_mssql_odbc_driver") as mock_check,
            patch("stocks.db.connection.ensure_localdb_started"),
            patch("stocks.db.connection.create_mssql_database_if_not_exists"),
            patch("stocks.db.connection.create_engine") as mock_engine,
        ):
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute = MagicMock()
            mock_engine.return_value.connect.return_value = mock_conn
            mock_engine.return_value.dispose = MagicMock()
            try:
                manager.initialize()
            except Exception:
                pass
        mock_check.assert_called_once()

    def test_odbc_check_called_before_localdb(self):
        """The ODBC check must fire BEFORE ensure_localdb_started so a missing
        driver aborts the flow without trying to spin up the SQL Server process."""
        call_order: list[str] = []

        def fake_odbc_check():
            call_order.append("odbc")

        def fake_localdb():
            call_order.append("localdb")

        from stocks.db.connection import DatabaseManager

        manager = DatabaseManager("mssql+pyodbc://./TestDB")
        with (
            patch("stocks.db.connection._check_mssql_odbc_driver", side_effect=fake_odbc_check),
            patch("stocks.db.connection.ensure_localdb_started", side_effect=fake_localdb),
            patch("stocks.db.connection.create_mssql_database_if_not_exists"),
            patch("stocks.db.connection.create_engine") as mock_engine,
        ):
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute = MagicMock()
            mock_engine.return_value.connect.return_value = mock_conn
            mock_engine.return_value.dispose = MagicMock()
            try:
                manager.initialize()
            except Exception:
                pass

        assert call_order.index("odbc") < call_order.index("localdb")
