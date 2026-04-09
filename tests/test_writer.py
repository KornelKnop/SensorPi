import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import modułu writer bez uruchamiania pętli (main jest pod if __name__).
# Ścieżka repo jest dodawana w conftest.py.
_REPO = Path(__file__).resolve().parents[1]

import importlib.util

_spec = importlib.util.spec_from_file_location("writer_mod", _REPO / "00PiszDoBazy.py")
writer = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(writer)


class FakeSense:
    humidity = 60.0

    def get_pressure(self):
        return 1000.0

    def get_temperature(self):
        return 21.0

    def get_temperature_from_pressure(self):
        return 20.5


def test_collect_readings_from_sense():
    r = writer.collect_readings_from_sense(FakeSense())
    assert r["humidity"] == 60.0
    assert r["pressure"] == 1000.0
    assert r["temp_hum"] == 21.0
    assert r["temp_prs"] == 20.5


def test_collect_readings_handles_bad_sense():
    class Bad:
        @property
        def humidity(self):
            raise RuntimeError("x")

        def get_pressure(self):
            raise RuntimeError("x")

        def get_temperature(self):
            raise RuntimeError("x")

        def get_temperature_from_pressure(self):
            raise RuntimeError("x")

    r = writer.collect_readings_from_sense(Bad())
    assert r["humidity"] is None
    assert r["pressure"] is None
    assert r["temp_hum"] is None
    assert r["temp_prs"] is None


def test_default_writer_db_uri_uses_forward_slashes():
    u = writer.default_writer_db_uri()
    assert u.startswith("sqlite:///")
    assert "\\" not in u


def test_build_sensor_with_mock_sense_hat_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SENSORPI_SENSOR", "sense_hat")

    class F:
        def clear(self):
            raise OSError("no led")

    mod = types.ModuleType("sense_hat")
    mod.SenseHat = lambda: F()
    monkeypatch.setitem(sys.modules, "sense_hat", mod)
    s = writer.build_sensor()
    assert isinstance(s, F)


def test_run_once_delegates_to_collect_and_insert(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    uri = "sqlite:///" + str(db).replace("\\", "/")
    monkeypatch.setenv("SENSORPI_DB_URI", uri)
    session = writer.build_session()
    r = writer.run_once(session, FakeSense())
    assert r.temp_hum == 21.0


def test_insert_reading_in_memory(tmp_path, monkeypatch):
    db = tmp_path / "w.db"
    uri = "sqlite:///" + str(db).replace("\\", "/")
    monkeypatch.setenv("SENSORPI_DB_URI", uri)

    engine = create_engine(uri, future=True)
    writer.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    rec = writer.insert_reading(
        session,
        {"humidity": 1.0, "pressure": 2.0, "temp_hum": 3.0, "temp_prs": 4.0},
    )
    assert rec.id is not None
    assert rec.epoch > 0


def test_build_sensor_wrong_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SENSORPI_SENSOR", "none")
    with pytest.raises(RuntimeError, match="sense_hat"):
        writer.build_sensor()


def test_run_loop_one_iteration(monkeypatch: pytest.MonkeyPatch):
    calls = {"n": 0}

    def fake_run_once(session, sense):
        calls["n"] += 1
        return object()

    monkeypatch.setattr(writer, "run_once", fake_run_once)
    monkeypatch.setattr(
        writer.time,
        "sleep",
        lambda _s: (_ for _ in ()).throw(RuntimeError("stop_test")),
    )
    with pytest.raises(RuntimeError, match="stop_test"):
        writer.run_loop(object(), object(), sleep_seconds=1)
    assert calls["n"] == 1


def test_main_wires_build_and_run_loop(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(writer, "build_sensor", lambda: FakeSense())
    monkeypatch.setattr(writer, "build_session", lambda: object())
    called = []

    def capture_loop(sense, session, sleep_seconds=writer.SLEEP):
        called.append((sense, session, sleep_seconds))

    monkeypatch.setattr(writer, "run_loop", capture_loop)
    writer.main()
    assert len(called) == 1
    assert isinstance(called[0][0], FakeSense)
