#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import platform
import pkg_resources
from sense_hat import SenseHat
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, g
from flask import render_template
from flask import send_from_directory
from flask import Flask, render_template, redirect, url_for
from flask_wtf import FlaskForm 
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import InputRequired
from flask_wtf import Form
from wtforms import TextField, BooleanField,IntegerField
from wtforms.validators import Required
from wtforms.validators import DataRequired, Length, Email, EqualTo
from flask_sqlalchemy  import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

SecondInOneHour = 3600

sense = SenseHat()
sense.clear()


app = Flask(__name__)
app.config['SECRET_KEY'] = 'KornelSssie'
dbl = SQLAlchemy(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///login.db'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


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
    return User.query.get(int(user_id))

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

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'baza.db'),
    DEBUG=True
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

#Łączy się z bazą danych.
def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

#Nowe połączenie z bazą danych.
def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

#Zamyka bazę danych ponownie po zakończeniu żądania.
@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

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
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            #flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)
    
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()
    try:
        if form.validate_on_submit():
            hashed_password = generate_password_hash(request.form.get('password'), method='sha256')
            new_user = User(username=request.form.get('username'), email=request.form.get('email'), password=hashed_password)
            dbl.session.add(new_user)
            dbl.session.commit()

            return '<h1>New user has been created!</h1>'
    except:
        return '<h1>już jest taki user</h1>'
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
    selectTime = 'day'
    options = {
        'hour': [SecondInOneHour, 'z ostatniej godziny'],
        'day': [SecondInOneHour * 24, 'z ostatniej doby'],
        'week': [SecondInOneHour * 168, 'z ostatnego tygodnia'],
        'month': [SecondInOneHour * 720, 'z ostatniego miesiąca']}

    if request.method == 'POST':
        selectTime = str(request.form.get('timespan_select'))

    db = get_db()
    query = """
        SELECT strftime('%%Y-%%m-%%d %%H:%%M', epoch, 'unixepoch', 'localtime') as datetime,
               humidity, pressure, temp_hum
        FROM tabela
        WHERE epoch BETWEEN (strftime('%%s','now')-%i)
                    AND strftime('%%s','now');
        """ % options[selectTime][0]

    cur = db.execute(query)

    while True:
        row = cur.fetchone()
        if row == None:
            break
        humidity.append(row["humidity"])
        pressure.append(row["pressure"])
        tempHum.append(row["temp_hum"])
        labels.append(row["datetime"])

    data = {'labels': labels,
            'humidity': humidity,
            'pressure': pressure,
            'tempHum': tempHum}
   
    return render_template('wykres.html',
                           selectTime=selectTime,
                           HeadTime=options[selectTime][1],
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

    db = get_db()
   
#temperatura minimalna
    query = """
        SELECT MIN
            (temp_hum) AS tempSensHumMin
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    tempSensHumMin = str(round(row["tempSensHumMin"], 1)) + " °C"

#temperatura maksymalna
    query = """
        SELECT MAX
            (temp_hum) AS tempSensHumMax
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    tempSensHumMax = str(round(row["tempSensHumMax"], 1)) + " °C"

#temperatura srednia
    query = """
        SELECT AVG
            (temp_hum) AS tempSensHumAvg
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    tempSensHumAvg = str(round(row["tempSensHumAvg"], 1)) + " °C"    

#wilgotnosc minimalna
    query = """
        SELECT MIN
            (humidity) AS humSensMin
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    humSensMin = str(round(row["humSensMin"], 1)) + " %"

#wilgotnosc maksymalna
    query = """
        SELECT MAX
            (humidity) AS humSensMax
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    humSensMax = str(round(row["humSensMax"], 1)) + " %"

#wilgotnosc srednia
    query = """
        SELECT AVG
            (humidity) AS humSensAvg
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    humSensAvg = str(round(row["humSensAvg"], 1)) + " %"   


#cisnienie minimalna
    query = """
        SELECT MIN
            (pressure) AS presSensMin
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    presSensMin = str(round(row["presSensMin"], 1)) + " hPa"

#cisnienie maksymalna
    query = """
        SELECT MAX
            (pressure) AS presSensMax
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    presSensMax = str(round(row["presSensMax"], 1)) + " hPa"

#cisnienie srednia
    query = """
        SELECT AVG
            (pressure) AS presSensAvg
        FROM 
            tabela
       """
    cur = db.execute(query)
    row = cur.fetchone()
    presSensAvg = str(round(row["presSensAvg"], 1)) + " hPa"   




# do wyrzucenia do html
    return render_template('stat.html',
                           tempSensHumMin=tempSensHumMin,
                           tempSensHumMax=tempSensHumMax,
                           tempSensHumAvg=tempSensHumAvg,
                           humSensMin=humSensMin,
                           humSensMax=humSensMax,
                           humSensAvg=humSensAvg,
                           presSensMin=presSensMin,
                           presSensMax=presSensMax,
                           presSensAvg=presSensAvg)


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!strona glowna - odczyt biezacy!!!!!!!!!!!!! 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@app.route('/')
def index():
    humidity = round(sense.humidity, 1)
    pressure = round(sense.get_pressure(), 2)
    temperature= round(sense.get_temperature(), 1)
    

    return render_template('now.html',
                            humidity=humidity,
                            pressure=pressure,
                            temperature=temperature)

#flask start
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
