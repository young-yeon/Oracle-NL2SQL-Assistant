from pathlib import Path

from app.config import Settings
from app.services.runtime_settings import RuntimeSettingsStore


def test_runtime_oracle_settings_round_trip(tmp_path: Path):
    settings = Settings(STORAGE_DIR=tmp_path)
    settings.oracle_dsn = "db-host:1521/ORCLPDB1"
    settings.oracle_user = "readonly_user"
    settings.oracle_password = "secret"
    settings.oracle_current_schema = "APP"
    settings.oracle_mode = "thick"
    settings.oracle_client_lib_dir = "/opt/oracle/instantclient"
    settings.sql_max_rows = 250
    settings.sql_timeout_seconds = 45

    store = RuntimeSettingsStore(tmp_path)
    store.save_oracle(settings)

    restored = Settings(STORAGE_DIR=tmp_path)
    store.apply(restored)

    assert restored.oracle_dsn == "db-host:1521/ORCLPDB1"
    assert restored.oracle_user == "readonly_user"
    assert restored.oracle_password == "secret"
    assert restored.oracle_current_schema == "APP"
    assert restored.oracle_mode == "thick"
    assert restored.oracle_client_lib_dir == "/opt/oracle/instantclient"
    assert restored.sql_max_rows == 250
    assert restored.sql_timeout_seconds == 45
