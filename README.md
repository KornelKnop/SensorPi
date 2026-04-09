# SensorPi

Panel środowiskowy (Flask) pod Raspberry Pi / Sense HAT — dashboard “portal pogodowy” + historia pomiarów w SQLite.

## Uruchomienie (Raspberry Pi)
- **Writer (zapis do bazy)**:

```bash
python3 00PiszDoBazy.py
```

- **Aplikacja web**:

```bash
python3 testSite1.py
```

Po zalogowaniu wejdź na `/dashboard`.

## Konfiguracja (ENV)
- **`SENSORPI_DB_URI`**: URI SQLAlchemy (domyślnie `sqlite:///.../app.db` w katalogu projektu)
- **`SENSORPI_SECRET_KEY`**: sekret sesji Flask (jeśli brak, zostanie wygenerowany w `instance/.secret_key`)
- **`SENSORPI_SENSOR`**: `sense_hat` (domyślnie). Jeśli brak sprzętu lub biblioteki, web przejdzie w tryb “no data”.
- **`SENSORPI_HOST`**: domyślnie `0.0.0.0`
- **`SENSORPI_PORT`**: domyślnie `5000`
- **`FLASK_DEBUG`**: `1/true` żeby włączyć debug lokalnie

## Migracja starych danych
Jeśli masz stare pliki `baza.db` (pomiary) i `login.db` (użytkownicy):

```bash
python3 migrate_to_appdb.py
```

To przeniesie dane do `app.db`.

## Testy i pokrycie kodu

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-report=term-missing --cov-report=html:htmlcov
```

Raport HTML trafia do katalogu `htmlcov/`.

