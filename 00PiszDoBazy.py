#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import os
import time

from sqlalchemy import Column, Float, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Czas między pomiarami w sekundach
SLEEP = 300

Base = declarative_base()


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    epoch = Column(Integer, index=True, nullable=False)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    temp_hum = Column(Float, nullable=True)
    temp_prs = Column(Float, nullable=True)


def collect_readings_from_sense(sense):
    """Odczyt wilgotności, ciśnienia i temperatur z Sense HAT (odporny na błędy)."""
    try:
        humidity = round(float(sense.humidity), 1)
    except Exception:
        humidity = None
    try:
        pressure = round(float(sense.get_pressure()), 2)
    except Exception:
        pressure = None
    try:
        temperature_from_humidity = round(float(sense.get_temperature()), 1)
    except Exception:
        temperature_from_humidity = None
    try:
        temperature_from_pressure = round(float(sense.get_temperature_from_pressure()), 1)
    except Exception:
        temperature_from_pressure = None
    return {
        "humidity": humidity,
        "pressure": pressure,
        "temp_hum": temperature_from_humidity,
        "temp_prs": temperature_from_pressure,
    }


def default_writer_db_uri() -> str:
    """Domyślna ścieżka `sqlite:///.../app.db` obok tego pliku (testowalna osobno)."""
    root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(root, "app.db").replace("\\", "/")
    return "sqlite:///" + db_path


def build_sensor():
    provider = os.environ.get("SENSORPI_SENSOR", "sense_hat").strip().lower()
    if provider not in {"sensehat", "sense_hat"}:
        raise RuntimeError("SENSORPI_SENSOR must be sense_hat for this writer")

    from sense_hat import SenseHat  # local import for non-Pi environments

    sense = SenseHat()
    try:
        sense.clear()
    except Exception:
        pass
    return sense


def build_session():
    db_uri = os.environ.get("SENSORPI_DB_URI") or default_writer_db_uri()
    engine = create_engine(db_uri, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def insert_reading(session, readings: dict) -> SensorReading:
    """Jeden zapis próbki do bazy (używane w pętli i w testach)."""
    reading = SensorReading(
        epoch=int(time.time()),
        humidity=readings.get("humidity"),
        pressure=readings.get("pressure"),
        temp_hum=readings.get("temp_hum"),
        temp_prs=readings.get("temp_prs"),
    )
    session.add(reading)
    session.commit()
    return reading


def run_once(session, sense) -> SensorReading:
    readings = collect_readings_from_sense(sense)
    return insert_reading(session, readings)


def run_loop(sense, session, sleep_seconds: int = SLEEP) -> None:
    while True:
        run_once(session, sense)
        print(
            "%s - Wprowadzono dane. Przerwa na %i sekund."
            % (datetime.datetime.now(), sleep_seconds)
        )
        time.sleep(sleep_seconds)


def main() -> None:
    sense = build_sensor()
    session = build_session()
    run_loop(sense, session, SLEEP)


if __name__ == "__main__":  # pragma: no cover
    main()
