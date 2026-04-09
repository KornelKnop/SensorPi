"""Testy jednostkowe czystych funkcji z testSite1 (bez pełnego stacka HTTP)."""

import sys
import types
from pathlib import Path

import pytest


def test_format_stat_value_none():
    from testSite1 import format_stat_value

    assert format_stat_value(None, "°C", 1) == "—"


def test_format_stat_value_rounds():
    from testSite1 import format_stat_value

    assert format_stat_value(22.456, "°C", 1) == "22.5 °C"


def test_normalize_wykres_timespan_valid_and_fallback():
    from testSite1 import _normalize_wykres_timespan

    assert _normalize_wykres_timespan("hour") == "hour"
    assert _normalize_wykres_timespan("bogus") == "day"
    assert _normalize_wykres_timespan(None) == "day"


def test_default_sqlite_uri_backslashes():
    from testSite1 import _default_sqlite_uri

    uri = _default_sqlite_uri(r"C:\data\app.db")
    assert uri.startswith("sqlite:///")
    assert "\\" not in uri


def test_load_or_create_secret_key_reads_existing(tmp_path: Path):
    from testSite1 import _load_or_create_secret_key

    p = tmp_path / "sec.txt"
    p.write_text("already-set", encoding="utf-8")
    assert _load_or_create_secret_key(str(p)) == "already-set"


def test_load_or_create_secret_key_creates_file(tmp_path: Path):
    from testSite1 import _load_or_create_secret_key

    p = tmp_path / "nested" / "sec.txt"
    v = _load_or_create_secret_key(str(p))
    assert len(v) == 64
    assert p.read_text(encoding="utf-8") == v


def test_sensor_provider_base_raises():
    from testSite1 import SensorProvider

    with pytest.raises(NotImplementedError):
        SensorProvider().read_now()


def test_sense_hat_provider_read_now_with_fake_module(monkeypatch: pytest.MonkeyPatch):
    class FakeSense:
        humidity = 55.5

        def clear(self):
            pass

        def get_pressure(self):
            return 1013.25

        def get_temperature(self):
            return 23.4

    fake_mod = types.ModuleType("sense_hat")
    fake_mod.SenseHat = lambda: FakeSense()
    monkeypatch.setitem(sys.modules, "sense_hat", fake_mod)

    from testSite1 import SenseHatProvider

    p = SenseHatProvider()
    n = p.read_now()
    assert n.source == "sense_hat"
    assert n.temperature_c == 23.4
    assert n.humidity_rh == 55.5
    assert n.pressure_hpa == 1013.25


def test_sense_hat_provider_clear_failure_is_ignored(monkeypatch: pytest.MonkeyPatch):
    class FakeSense:
        def clear(self):
            raise RuntimeError("led")

        @property
        def humidity(self):
            return 1.0

        def get_pressure(self):
            return 1000.0

        def get_temperature(self):
            return 20.0

    fake_mod = types.ModuleType("sense_hat")
    fake_mod.SenseHat = lambda: FakeSense()
    monkeypatch.setitem(sys.modules, "sense_hat", fake_mod)

    from testSite1 import SenseHatProvider

    p = SenseHatProvider()
    n = p.read_now()
    assert n.humidity_rh == 1.0


def test_sense_hat_provider_humidity_read_fails(monkeypatch: pytest.MonkeyPatch):
    class FakeSense:
        def clear(self):
            pass

        @property
        def humidity(self):
            raise RuntimeError("bad")

        def get_pressure(self):
            return 1000.0

        def get_temperature(self):
            return 20.0

    fake_mod = types.ModuleType("sense_hat")
    fake_mod.SenseHat = lambda: FakeSense()
    monkeypatch.setitem(sys.modules, "sense_hat", fake_mod)

    from testSite1 import SenseHatProvider

    n = SenseHatProvider().read_now()
    assert n.humidity_rh is None
    assert n.pressure_hpa == 1000.0


def test_sense_hat_provider_partial_sensor_failures(monkeypatch: pytest.MonkeyPatch):
    class FakeSense:
        humidity = 50.0

        def clear(self):
            pass

        def get_pressure(self):
            raise RuntimeError("no pressure")

        def get_temperature(self):
            raise RuntimeError("no temp")

    fake_mod = types.ModuleType("sense_hat")
    fake_mod.SenseHat = lambda: FakeSense()
    monkeypatch.setitem(sys.modules, "sense_hat", fake_mod)

    from testSite1 import SenseHatProvider

    n = SenseHatProvider().read_now()
    assert n.humidity_rh == 50.0
    assert n.pressure_hpa is None
    assert n.temperature_c is None


def test_build_sensor_provider_sense_hat_falls_back_to_null(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SENSORPI_SENSOR", "sense_hat")

    from testSite1 import NullProvider, _build_sensor_provider

    def boom():
        raise OSError("no sense hat")

    monkeypatch.setattr("testSite1.SenseHatProvider", boom)
    assert isinstance(_build_sensor_provider(), NullProvider)


def test_run_dev_server_calls_app_run(monkeypatch: pytest.MonkeyPatch):
    import testSite1

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(testSite1.app, "run", fake_run)
    monkeypatch.setenv("FLASK_DEBUG", "0")
    monkeypatch.setenv("SENSORPI_HOST", "127.0.0.1")
    monkeypatch.setenv("SENSORPI_PORT", "54321")
    testSite1.run_dev_server()
    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 54321
    assert calls[0]["debug"] is False


def test_sensor_reading_from_now(app_module):
    from testSite1 import SensorNow, SensorReading

    now = SensorNow(21.0, 40.0, 1000.0, "test")
    with app_module.app.app_context():
        r = SensorReading.from_now(now)
        assert r.temp_hum == 21.0
        assert r.humidity == 40.0
        assert r.pressure == 1000.0
