"""Tests for columnar data-plane configuration and BarStore.from_config()."""

from pathlib import Path

from stocks.config import Config
from stocks.data.bar_store import BarStore


def test_default_columnar_data_dir():
    cfg = Config()
    assert cfg.storage.columnar_data_dir == "data/columnar"


def test_config_loads_storage_from_dict():
    cfg = Config(**{"storage": {"columnar_data_dir": "/tmp/somewhere/col"}})
    assert cfg.storage.columnar_data_dir == "/tmp/somewhere/col"


def test_barstore_from_config(tmp_path):
    target = tmp_path / "col"
    cfg = Config()
    cfg.storage.columnar_data_dir = str(target)

    store = BarStore.from_config(cfg)
    assert store.data_dir == Path(target)
    assert target.exists()  # BarStore creates its root dir
