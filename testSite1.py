#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, InputRequired, Length
from wtforms.validators import ValidationError
SECONDS_IN_HOUR = 3600

WYKRES_TIME_OPTIONS = {
    "hour": [SECONDS_IN_HOUR, "z ostatniej godziny"],
    "day": [SECONDS_IN_HOUR * 24, "z ostatniej doby"],
    "week": [SECONDS_IN_HOUR * 168, "z ostatniego tygodnia"],
    "month": [SECONDS_IN_HOUR * 720, "z ostatniego miesiąca"],
}


def _normalize_wykres_timespan(raw: str | None) -> str:
    key = (raw or "day").strip().lower()
    return key if key in WYKRES_TIME_OPTIONS else "day"


def format_stat_value(value: float | None, unit: str, ndigits: int) -> str:
    if value is None:
        return "—"
    return f"{round(float(value), ndigits)} {unit}"


def _load_or_create_secret_key(secret_path: str) -> str:
    """
    Keep a stable SECRET_KEY across restarts without hardcoding it in git.
    """
    secret_dir = os.path.dirname(secret_path)
    if secret_dir and not os.path.isdir(secret_dir):
        os.makedirs(secret_dir, exist_ok=True)
    if os.path.isfile(secret_path):
        with open(secret_path, "r", encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return value
    value = os.urandom(32).hex()
    with open(secret_path, "w", encoding="utf-8") as f:
        f.write(value)
    return value


def _default_sqlite_uri(db_path: str) -> str:
    # SQLite URI needs forward slashes even on Windows.
    return "sqlite:///" + db_path.replace("\\", "/")


@dataclass(frozen=True)
class SensorNow:
    temperature_c: float | None
    humidity_rh: float | None
    pressure_hpa: float | None
    source: str


class SensorProvider:
    def read_now(self) -> SensorNow:
        raise NotImplementedError


class SenseHatProvider(SensorProvider):
    def __init__(self) -> None:
        from sense_hat import SenseHat  # local import for non-Pi environments

        self._sense = SenseHat()
        try:
            self._sense.clear()
        except Exception:
            # clearing LED matrix is non-critical
            pass

    def read_now(self) -> SensorNow:
        try:
            humidity = round(float(self._sense.humidity), 1)
        except Exception:
            humidity = None
        try:
            pressure = round(float(self._sense.get_pressure()), 2)
        except Exception:
            pressure = None
        try:
            temperature = round(float(self._sense.get_temperature()), 1)
        except Exception:
            temperature = None
        return SensorNow(
            temperature_c=temperature,
            humidity_rh=humidity,
            pressure_hpa=pressure,
            source="sense_hat",
        )


class NullProvider(SensorProvider):
    def read_now(self) -> SensorNow:
        return SensorNow(
            temperature_c=None, humidity_rh=None, pressure_hpa=None, source="none"
        )


def _build_sensor_provider() -> SensorProvider:
    provider = os.environ.get("SENSORPI_SENSOR", "sense_hat").strip().lower()
    if provider in {"sensehat", "sense_hat"}:
        try:
            return SenseHatProvider()
        except Exception:
            return NullProvider()
    return NullProvider()


def create_app() -> Flask:
    app = Flask(__name__)

    # Config (ENV overrides, safe defaults for Pi dev-server usage)
    app_root = app.root_path
    instance_dir = os.path.join(app_root, "instance")
    secret_file = os.path.join(instance_dir, ".secret_key")

    app.config["SECRET_KEY"] = os.environ.get("SENSORPI_SECRET_KEY") or _load_or_create_secret_key(secret_file)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SENSORPI_DB_URI") or _default_sqlite_uri(
        os.path.join(app_root, "app.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if os.environ.get("SENSORPI_TESTING", "").strip() in {"1", "true", "True", "yes"}:
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

    return app


app = create_app()
dbl = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

sensor = _build_sensor_provider()


####Klasy logowania
class User(UserMixin, dbl.Model):
    id = dbl.Column(dbl.Integer, primary_key=True)
    username = dbl.Column(dbl.String(15), unique=True)
    email = dbl.Column(dbl.String(50), unique=True)
    password = dbl.Column(dbl.String(80))
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

@login_manager.user_loader
def load_user(user_id):
    return dbl.session.get(User, int(user_id))

class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember me')
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=50)])
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('submit')
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')


class SensorReading(dbl.Model):
    __tablename__ = "sensor_readings"

    id = dbl.Column(dbl.Integer, primary_key=True)
    epoch = dbl.Column(dbl.Integer, index=True, nullable=False)
    humidity = dbl.Column(dbl.Float, nullable=True)
    pressure = dbl.Column(dbl.Float, nullable=True)
    temp_hum = dbl.Column(dbl.Float, nullable=True)
    temp_prs = dbl.Column(dbl.Float, nullable=True)

    @staticmethod
    def from_now(now: SensorNow) -> "SensorReading":
        return SensorReading(
            epoch=int(time.time()),
            humidity=now.humidity_rh,
            pressure=now.pressure_hpa,
            temp_hum=now.temperature_c,
            temp_prs=None,
        )


with app.app_context():
    dbl.create_all()

#ikonka
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!strona login + signup!!!!!!!!!!!!!!!!!!!!!!!!! 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            #flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember.data)
        return redirect(url_for('dashboard'))
    return render_template('login.html', title='Sign In', form=form)
    
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data),
        )
        dbl.session.add(new_user)
        try:
            dbl.session.commit()
        except Exception:
            dbl.session.rollback()
            return '<h1>Nie udało się utworzyć użytkownika (login/email już istnieje lub błąd bazy).</h1>'
        return '<h1>New user has been created!</h1>'
    return render_template('signup.html', form=form)

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!strona wykresy!!!!!!!!!!!!!!!!!!!!!!!!! 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@app.route("/wykres", methods=['GET', 'POST'])
@login_required
def show_wykres():
    humidity = []
    pressure = []
    tempHum = []
    labels = []
    selectTime = "day"
    if request.method == "POST":
        selectTime = _normalize_wykres_timespan(str(request.form.get("timespan_select")))

    since_epoch = int(time.time()) - int(WYKRES_TIME_OPTIONS[selectTime][0])
    rows = (
        SensorReading.query.filter(SensorReading.epoch.between(since_epoch, int(time.time())))
        .order_by(SensorReading.epoch.asc())
        .all()
    )

    for r in rows:
        humidity.append(r.humidity if r.humidity is not None else None)
        pressure.append(r.pressure if r.pressure is not None else None)
        tempHum.append(r.temp_hum if r.temp_hum is not None else None)
        labels.append(
            datetime.fromtimestamp(r.epoch, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        )

    data = {'labels': labels,
            'humidity': humidity,
            'pressure': pressure,
            'tempHum': tempHum}
   
    return render_template('wykres.html',
                           selectTime=selectTime,
                           HeadTime=WYKRES_TIME_OPTIONS[selectTime][1],
                           humidity=data['humidity'],
                           pressure=data['pressure'],
                           tempHum=data['tempHum'],
                           labels=data['labels'])

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!strona statystyki!!!!!!!!!!!!!!!!!!!!!! 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@app.route("/stat", methods=['GET', 'POST'])
@login_required
def show_statistics():
    stats = dbl.session.query(
        dbl.func.min(SensorReading.temp_hum).label("temp_min"),
        dbl.func.max(SensorReading.temp_hum).label("temp_max"),
        dbl.func.avg(SensorReading.temp_hum).label("temp_avg"),
        dbl.func.min(SensorReading.humidity).label("hum_min"),
        dbl.func.max(SensorReading.humidity).label("hum_max"),
        dbl.func.avg(SensorReading.humidity).label("hum_avg"),
        dbl.func.min(SensorReading.pressure).label("pres_min"),
        dbl.func.max(SensorReading.pressure).label("pres_max"),
        dbl.func.avg(SensorReading.pressure).label("pres_avg"),
    ).one()

    tempSensHumMin = format_stat_value(stats.temp_min, "°C", 1)
    tempSensHumMax = format_stat_value(stats.temp_max, "°C", 1)
    tempSensHumAvg = format_stat_value(stats.temp_avg, "°C", 1)
    humSensMin = format_stat_value(stats.hum_min, "%", 1)
    humSensMax = format_stat_value(stats.hum_max, "%", 1)
    humSensAvg = format_stat_value(stats.hum_avg, "%", 1)
    presSensMin = format_stat_value(stats.pres_min, "hPa", 1)
    presSensMax = format_stat_value(stats.pres_max, "hPa", 1)
    presSensAvg = format_stat_value(stats.pres_avg, "hPa", 1)

    return render_template(
        "stat.html",
        tempSensHumMin=tempSensHumMin,
        tempSensHumMax=tempSensHumMax,
        tempSensHumAvg=tempSensHumAvg,
        humSensMin=humSensMin,
        humSensMax=humSensMax,
        humSensAvg=humSensAvg,
        presSensMin=presSensMin,
        presSensMax=presSensMax,
        presSensAvg=presSensAvg,
    )


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!strona glowna - odczyt biezacy!!!!!!!!!!!!! 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/api/now")
@login_required
def api_now():
    now = sensor.read_now()
    return jsonify(
        {
            "source": now.source,
            "ts": int(time.time()),
            "temperature_c": now.temperature_c,
            "humidity_rh": now.humidity_rh,
            "pressure_hpa": now.pressure_hpa,
            "available": {
                "temperature": now.temperature_c is not None,
                "humidity": now.humidity_rh is not None,
                "pressure": now.pressure_hpa is not None,
            },
        }
    )


@app.route("/api/history")
@login_required
def api_history():
    span = (request.args.get("span") or "hour").strip().lower()
    spans = {
        "hour": SECONDS_IN_HOUR,
        "day": SECONDS_IN_HOUR * 24,
        "week": SECONDS_IN_HOUR * 168,
        "month": SECONDS_IN_HOUR * 720,
    }
    seconds = spans.get(span, spans["hour"])
    now_ts = int(time.time())
    since_epoch = now_ts - int(seconds)

    rows = (
        SensorReading.query.filter(SensorReading.epoch.between(since_epoch, now_ts))
        .order_by(SensorReading.epoch.asc())
        .all()
    )

    points = []
    for r in rows:
        points.append(
            {
                "ts": int(r.epoch),
                "temperature_c": r.temp_hum,
                "humidity_rh": r.humidity,
                "pressure_hpa": r.pressure,
            }
        )

    return jsonify({"span": span, "since": since_epoch, "until": now_ts, "points": points})


@app.route("/dashboard")
@login_required
def dashboard():
    now = sensor.read_now()
    return render_template(
        "dashboard.html",
        temperature=now.temperature_c,
        humidity=now.humidity_rh,
        pressure=now.pressure_hpa,
        source=now.source,
        has_humidity=now.humidity_rh is not None,
        has_pressure=now.pressure_hpa is not None,
    )

def run_dev_server() -> None:
    """Uruchomienie serwera dev (używane też w testach z mockiem `app.run`)."""
    debug = os.environ.get("FLASK_DEBUG", "").strip() in {"1", "true", "True", "yes"}
    host = os.environ.get("SENSORPI_HOST", "0.0.0.0")
    port = int(os.environ.get("SENSORPI_PORT", "5000"))
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run_dev_server()
