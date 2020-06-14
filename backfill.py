"""
Copyright Dave Brown, 2020

Full disclaimer - This was not meant to survive the weekend, and I just keep coming
back to it. So here it is. I'm refactoring it to be just a little bit more predictable.

This takes the Indigo logs from my local folder and sends them to my InfluxDB VMware instance
but it makes pretty graphs, and might be useful to someone other than me some day.
"""
import time

import click
import json
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, WriteApi

from typing import Any, Dict, List

from influx_connection_state import Influx20ConnectionState
from log import IndigoLog, IndigoRecord, ReceivedEvent
from indigo import InfluxEvent

ON_OFF_STATE = "state.onOffState"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

FLOAT_KEYS = "lastSuccessfulComm id lastChanged buttonGroupCount folderId brightness pressureMillibars".split()
STRING_KEYS = (
    "PanicState.ambulance PanicState.duress LEDBypass hvacFanMode hvacFanModeIsAlwaysOn LEDMemory KeypadChime.enabled "
    "hvacFanIsOn hvacDehumidifierIsOn KeypadChime.disabled state.tripped humidityInputsAll state.open state.closed "
    "hvacCoolerIsOn hvacHeaterIsOn KeypadChime ArmedState.stay LastChangedTimer ArmedState ArmedState.away "
    "ArmedState.disarmed bypass.bypassed bypass.nobypass humidityInput1".replace(".", "_").split()
)
INT_KEYS = "configured onOffState".split()
BOOL_KEYS = "notbool enabled".split()
influx_state: Influx20ConnectionState


def temp(note: str):
    """Honestly I don't remember why I needed this."""
    return note.split()[-1]


def value_of(kk: str, vv: str) -> Any:
    """Dynamically cast a type to its intended in-memory type."""
    if vv is None:
        raise ValueError("nope")
    elif isinstance(vv, bool):
        return bool(vv)
    elif isinstance(vv, dict):
        raise ValueError("nope")
    if kk in FLOAT_KEYS:
        return float(vv)
    if kk in STRING_KEYS:
        return str(vv)
    if kk in INT_KEYS:
        return int(vv)
    if kk in BOOL_KEYS:
        return bool(vv)
    if ".num" in kk:
        return float(vv)
    return vv


def json_for_list(record: IndigoRecord) -> List[Dict]:
    """Refactor - return a list of objects."""
    newjson = []
    # Write existing debug info back - more data available.
    oldjson = json.loads(record.notes)

    for elt in oldjson:
        for key in elt["fields"].keys():
            key: str
            newkey = key.replace(".", "_")
            if key != newkey:
                elt["fields"][newkey] = elt["fields"][key]
                del elt["fields"][key]
        ie = InfluxEvent().from_dict(value=dict(time=record.read_time().strftime(DATE_FORMAT), **elt))
        newjson = [ie.to_dict()]
        break

    return newjson


def json_for_object(record: IndigoRecord) -> List[Dict]:
    """Refactor - return a list of objects."""
    raise ValueError("Nope!")
    '''
    oldjson = json.loads(record.notes)
    newjson = {}
    ie = InfluxEvent().from_dict(value=dict(time=record.read_time().strftime(DATE_FORMAT), **oldjson))
    if "name" not in oldjson.keys():
        return [{}]
    for kk in oldjson.keys():
        vv = oldjson[kk]
        try:
            newjson[kk.replace(".", "_")] = value_of(kk, vv)
        except ValueError:
            pass
    newtags = {"name": newjson["name"]}
    measurement = "device_changes"
    if "thermostat" in newjson["name"]:
        measurement = "thermostat_changes"
    if "temperatureC" in newjson.keys():
        measurement = "weather_changes"
    json_body = [{"measurement": measurement, "time": record.read_time().strftime(DATE_FORMAT), "tags": newtags,
                  "fields": newjson}]
    return json_body
    '''


def send_new_json_with_retry(newjson: List[Dict]):
    """
    So there's this thing with Influx DB, where it pisses you off.
    It rejects your write if someone already wrote a point with another format.
    So you retry sending your point writes over and over after converting them.

    This does that whole disaster.

    :param newjson: The new json to send
    :return:
    """
    global influx_state
    print(newjson)
    time.sleep(2)
    influx_state.api.write(influx_state.bucket, influx_state.org, newjson, time_precision="s")


def send_record(record: IndigoRecord) -> None:
    """
    Send the current record to influxdb.

    Device updates come in one of two flavors - lists of objects, or just objects.

    Weather gets a special path.
    """

    # Write existing debug info back - more data available.
    # Things that are already JSON lists:
    if record.notes.startswith("["):
        newjson = json_for_list(record)
        if not newjson or len(newjson[0]["fields"].keys()) < 1:
            return
        return send_new_json_with_retry(newjson)

    # things that are already JSON objects:
    elif record.notes.startswith("{"):
        newjson = json_for_object(record)
        return send_new_json_with_retry(newjson)

    # for the general case - like Insteon on off events, thermostat changes, etc.
    try:
        newjson = record.json_for_insteon_events()
        if not newjson or len(newjson["fields"].keys()) == 0:
            return
        send_new_json_with_retry([newjson])

    except Exception as e:
        print("Error doing something. Anything. Continuing!")
        print(record.notes)
        print(str(e))


@click.command()
@click.option("--token", type=str, envvar="INFLUX_TOKEN", required=True)
@click.option("--org", type=str, envvar="INFLUX_ORG", required=True)
@click.option("--bucket", type=str, envvar="INFLUX_BUCKET", required=True)
@click.option("--host", type=str, envvar="INFLUX_HOST", required=True)
def main(token, org, bucket, host):
    global influx_state
    client = InfluxDBClient(url=host, token=token)
    write_api: WriteApi = client.write_api(write_options=SYNCHRONOUS)
    influx_state = Influx20ConnectionState(token=token, org=org, bucket=bucket, api=write_api)
    il = IndigoLog()

    for x in il.records():
        try:
            send_record(x)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print("skipping a line")
            print(str(e))


if __name__ == "__main__":
    main()