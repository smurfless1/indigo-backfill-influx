import os
import json
import re
import time as time_
from log import IndigoLog, IndigoRecord, ReceivedEvent
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

def temp(note):
    return note.split()[-1]

connection = InfluxDBClient( \
    host=os.getenv('INHOST', 'localhost'), \
    port=int(os.getenv('INPORT', 8086)), \
    username=os.getenv('INUSER', 'indigo'), \
    password=os.getenv('INPASS', 'indigo'), \
    database=os.getenv('INDB', 'indigo'))

il = IndigoLog()

def valueOf(kk, vv):
    if vv is None:
        raise ValueError('nope')
    elif isinstance(vv, bool):
        return bool(vv)
    elif isinstance(vv, dict):
        raise ValueError('nope')
    floatkeys = 'lastSuccessfulComm id lastChanged buttonGroupCount folderId brightness pressureMillibars'.split()
    strkeys = 'PanicState.ambulance PanicState.duress LEDBypass hvacFanMode hvacFanModeIsAlwaysOn LEDMemory KeypadChime.enabled hvacFanIsOn hvacDehumidifierIsOn KeypadChime.disabled state.tripped humidityInputsAll state.open state.closed hvacCoolerIsOn hvacHeaterIsOn KeypadChime ArmedState.stay LastChangedTimer ArmedState ArmedState.away ArmedState.disarmed bypass.bypassed bypass.nobypass humidityInput1'.split()
    intkeys = 'configured onOffState'.split()
    boolkeys = 'notbool enabled'.split()
    if kk in floatkeys:
        return float(vv)
    if kk in strkeys:
        return str(vv)
    if kk in intkeys:
        return int(vv)
    if kk in boolkeys:
        return bool(vv)
    if '.num' in kk:
        return float(vv)
    return vv

def send(record):
    # write existing debug info back - more data available
    if record.notes.startswith('['):
        oldjson = json.loads(record.notes)
        newjson = {}
        if 'name' not in oldjson[0].keys():
            return
        for kk in oldjson[0].keys():
            vv = oldjson[0][kk]
            try:
                newjson[kk] = valueOf(kk, vv)
            except ValueError:
                pass
        newjson['time'] = record.readtime().strftime('%Y-%m-%dT%H:%M:%SZ')

        newjson = [newjson]
        unsent = True
        while unsent:
            try:
                connection.write_points(newjson, time_precision='s')
                unsent = False
            except InfluxDBClientError as e:
                #print(str(e))
                field = json.loads(e.content)['error'].split('"')[1]
                measurement = json.loads(e.content)['error'].split('"')[3]
                retry = json.loads(e.content)['error'].split('"')[4].split()[7]
                if retry == 'integer':
                    retry = 'int'
                if retry == 'string':
                    retry = 'str'
                newcode = '%s(%s)' % (retry, str(newjson[0]['fields'][field]))
                #print(newcode)
                newjson[0]['fields'][field] = eval(newcode)

    elif record.notes.startswith('{'):
        oldjson = json.loads(record.notes)
        newjson = {}
        if 'name' not in oldjson.keys():
            return
        for kk in oldjson.keys():
            vv = oldjson[kk]
            try:
                newjson[kk] = valueOf(kk, vv)
            except ValueError:
                pass
        newtags = { 'name': newjson['name'] }
        measurement = 'device_changes'
        if 'thermostat' in newjson['name']:
            measurement = 'thermostat_changes'
        json_body=[
            {
                'measurement': measurement,
                'time': record.readtime().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'tags' : newtags,
                'fields':  newjson
            }
        ]
        unsent = True
        while unsent:
            try:
                connection.write_points(json_body, time_precision='s')
                unsent = False
            except InfluxDBClientError as e:
                #print(str(e))
                field = json.loads(e.content)['error'].split('"')[1]
                measurement = json.loads(e.content)['error'].split('"')[3]
                retry = json.loads(e.content)['error'].split('"')[4].split()[7]
                if retry == 'integer':
                    retry = 'int'
                if retry == 'string':
                    retry = 'str'
                newcode = '%s(%s)' % (retry, str(json_body[0]['fields'][field]))
                #print(newcode)
                json_body[0]['fields'][field] = eval(newcode)

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
        measurement = 'device_changes'
        if 'INSTEON' in record.event:
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
            # TODO this works for things with "thermostat" in the name, which is kind of not super general
            if ('thermostat' in event.name):
                measurement = 'thermostat_changes'
                if 'turn auto on' in event.what:
                    pass
                elif 'turn fan auto on' in event.what:
                    pass

                elif 'set cool setpoint' in event.what or 'cool setpoint changed to' in event.what:
                    try:
                        newjson['coolSetpoint'] = float(event.what.split()[:-1])
                        newjson['state.setpointCool'] = float(event.what.split()[:-1])
                    except:
                        pass
                elif 'set heat setpoint' in event.what or 'heat setpoint changed to' in event.what:
                    try:
                        newjson['heatSetpoint'] = float(event.what.split()[:-1])
                        newjson['state.setpointHeat'] = float(event.what.split()[:-1])
                    except:
                        pass
                elif 'temperature changed to' in event.what:
                    newjson['state.temperatureInput1'] = float(temp(event.what))
                    newjson['state.temperatureString'] = str(temp(event.what))
                elif 'humidity changed to' in event.what:
                    newjson['state.humidityInput1'] = float(temp(event.what))
                    newjson['state.humidityString'] = str(temp(event.what))

                try:
                    # not sure if its heating or cooling season, so:
                    newjson['coolIsOn'] = newjson['onState']
                    newjson['state.hvacCoolIsOn'] = newjson['onState']
                    newjson['heatIsOn'] = newjson['onState']
                    newjson['state.hvacHeatIsOn'] = newjson['onState']
                except:
                    pass

                try:
                    del newjson['onState']
                except:
                    pass
                try:
                    del newjson['state.onOffState']
                except:
                    pass

        # uh... more.

        json_body=[
            {
                'measurement': measurement,
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
    except json.JSONDecodeError as e:
        pass
    except Exception as e:
        print("skipping a line")
        print(str(e))
        pass

