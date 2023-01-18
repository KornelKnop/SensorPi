#!/usr/bin/python
# -*- coding: utf-8 -*-

import sqlite3
import time
import datetime
from sense_hat import SenseHat

#Czas miedzy pomiarami w sekunadch
SLEEP = 300

sense = SenseHat()
sense.clear()


def init_db():
    #Polaczenie doo bazy danych -> https://docs.python.org/3/library/sqlite3.html
    con = sqlite3.connect("baza.db")
    cur = con.cursor() 
    #Zrob baza.db i tabela jak nie istnieje  z czas,wilgotnosc,cisnienie,tempWilgotnosc,tempCisnienie
    query = """CREATE TABLE IF NOT EXISTS
                    tabela  (epoch INT,
                             humidity REAL,
                             pressure REAL,
                             temp_hum REAL,
                             temp_prs REAL)"""
    cur.execute(query)



init_db()
while 1:
    #Czytaj z czujnika wilgotnosc,cisnienie,tempWilgotnosc,tempCisnienie (wszystkie zaokraglij)
    humidity = round(sense.humidity, 1)
    pressure = round(sense.get_pressure(), 2)
    temperature_from_humidity = round(sense.get_temperature(), 1)
    temperature_from_pressure = round(sense.get_temperature_from_pressure(), 1)

    #Wrzuc do bazy z czujnika czas,wilgotnosc,cisnienie,tempWilgotnosc,tempCisnienie
    con = sqlite3.connect("baza.db")
    with con:
        cur = con.cursor()
        command = "INSERT INTO tabela VALUES(%i,%0.2f,%0.2f,%0.2f,%0.2f)" % (int(
            time.time()), humidity, pressure, temperature_from_humidity, temperature_from_pressure)
        cur.execute(command)


    #Komunikat o powodzeniu i czasie oczekiwania
    print("%s - Wprowadzono dane. Przerwa na %i sekund." % (datetime.datetime.now(), SLEEP))
    time.sleep(SLEEP)
