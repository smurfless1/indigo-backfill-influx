import os
import json
import re
import time as time_
from log import IndigoLog, IndigoRecord, ReceivedEvent
from influxdb import InfluxDBClient

def temp(note):
    return note.split()[-1]

connection = InfluxDBClient( \
    host=os.getenv('INHOST', 'localhost'), \
    port=int(os.getenv('INPORT', 8086)), \
    username=os.getenv('INUSER', 'indigo'), \
    password=os.getenv('INPASS', 'indigo'), \
    database=os.getenv('INDB', 'indigo'))

il = IndigoLog()

def send(record):
    # get an IndigoRecord, make up some json that mostly looks like an Indigo Device flattened to json
    try:
        event = record.readevent()
        if event == None:
            return

        newjson = {'name': event.name}
        newtags = {'name': event.name}

        # everyone gets a date/time
        ut = time_.mktime(record.readtime().timetuple())
        #'time' : int(ut),

        # NOAA weather doesn't log on my box. Bummer!
        # updates - thermostat
        if 'temperature changed to' in event.what:
            newjson['state.temperatureInput1'] = float(temp(event.what))
            newjson['state.temperatureString'] = str(temp(event.what))
        elif 'humidity changed to' in event.what:
            newjson['state.humidityInput1'] = float(temp(event.what))
            newjson['state.humidityString'] = str(temp(event.what))
        elif 'INSTEON' in record.event:
            # lights on off dim: set state
            if (event.what == "on to"):
                newjson['onState'] = True
                newjson['state.onOffState'] = True
            if (event.what == "on"):
                newjson['onState'] = True
                newjson['state.onOffState'] = True
            if (event.what == "off"):
                newjson['onState'] = False
                newjson['state.onOffState'] = False
        # uh... more.

        json_body=[
            {
                'measurement': 'device_changes',
                'time': record.readtime().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'tags' : newtags,
                'fields':  newjson
            }
        ]

        # TODO keep an eye on this 2 thing
        if len(newjson.keys()) > 2:
            print(json.dumps(json_body))
            connection.write_points(json_body, time_precision='s')
    except Exception as e:
        print("Error doing something. Anything. Continuing!")
        print(str(e))

for x in il.records():
    try:
        send(x)
    except:
        print("skipping a line")
        pass

