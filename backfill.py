"""
Copyright Dave Brown, 2020

Full disclaimer - This was not meant to survive the weekend, and I just keep coming
back to it. So here it is. I'm refactoring it to be just a little bit more predictable.

This takes the Indigo logs from my local folder and sends them to my InfluxDB VMware instance
but it makes pretty graphs, and might be useful to someone other than me some day.
"""
import json
from typing import Any, Dict, List, Tuple

import click
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

from .log import IndigoLog, IndigoRecord, ReceivedEvent

ON_OFF_STATE = "state.onOffState"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

FLOAT_KEYS = "lastSuccessfulComm id lastChanged buttonGroupCount folderId brightness pressureMillibars".split()
STRING_KEYS = (
    "PanicState.ambulance PanicState.duress LEDBypass hvacFanMode hvacFanModeIsAlwaysOn LEDMemory KeypadChime.enabled "
    "hvacFanIsOn hvacDehumidifierIsOn KeypadChime.disabled state.tripped humidityInputsAll state.open state.closed "
    "hvacCoolerIsOn hvacHeaterIsOn KeypadChime ArmedState.stay LastChangedTimer ArmedState ArmedState.away ArmedState.disarmed "
    "bypass.bypassed bypass.nobypass humidityInput1".split()
)
INT_KEYS = "configured onOffState".split()
BOOL_KEYS = "notbool enabled".split()


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
    newjson = {}
    # Write existing debug info back - more data available.
    if record.notes.startswith("["):
        oldjson = json.loads(record.notes)
        newjson = {}
        if "name" not in oldjson[0].keys():
            return []
        for kk in oldjson[0].keys():
            vv = oldjson[0][kk]
            try:
                newjson[kk] = value_of(kk, vv)
            except ValueError:
                pass
        newjson["time"] = record.read_time().strftime(DATE_FORMAT)
        newjson = [newjson]

    return newjson


def json_for_object(record: IndigoRecord) -> List[Dict]:
    """Refactor - return a list of objects."""
    oldjson = json.loads(record.notes)
    newjson = {}
    if "name" not in oldjson.keys():
        return [{}]
    for kk in oldjson.keys():
        vv = oldjson[kk]
        try:
            newjson[kk] = value_of(kk, vv)
        except ValueError:
            pass
    newtags = {"name": newjson["name"]}
    measurement = "device_changes"
    if "thermostat" in newjson["name"]:
        measurement = "thermostat_changes"
    if "temperatureC" in newjson.keys():
        measurement = "weather_changes"
    json_body = [{"measurement": measurement, "time": record.read_time().strftime(DATE_FORMAT), "tags": newtags, "fields": newjson}]
    return json_body


def send_new_json_with_retry(newjson: List[Dict], connection: InfluxDBClient):
    """
    So there's this thing with Influx DB, where it pisses you off.
    It rejects your write if someone already wrote a point with another format.
    So you retry sending your point writes over and over after converting them.

    This does that whole disaster.

    :param newjson: The new json to send
    :param connection: The client to send to
    :return:
    """
    unsent = True
    while unsent:
        try:
            connection.write_points(newjson, time_precision="s")
            unsent = False
        except InfluxDBClientError as e:
            # print(str(e))
            field = json.loads(e.content)["error"].split('"')[1]
            # json.loads(e.content)["error"].split('"')[3]
            retry = json.loads(e.content)["error"].split('"')[4].split()[7]
            if retry == "integer":
                retry = "int"
            if retry == "string":
                retry = "str"
            newcode = "%s(%s)" % (retry, str(newjson[0]["fields"][field]))
            # print(newcode)
            newjson[0]["fields"][field] = eval(newcode)  # nosec B307


def json_for_insteon_events(record: IndigoRecord) -> Tuple[Dict, List[Dict]]:
    event = record.read_event()
    if event is None:
        return {}, []

    newjson = {"name": event.name}
    newtags = {"name": event.name}

    # NOAA weather doesn't log on my box. Bummer!
    # updates - thermostat
    measurement = "device_changes"
    if "INSTEON" in record.event:
        # lights on off dim: set state
        if event.what == "on to":
            newjson["onState"] = True
            newjson[ON_OFF_STATE] = True
        if event.what == "on":
            newjson["onState"] = True
            newjson[ON_OFF_STATE] = True
        if event.what == "off":
            newjson["onState"] = False
            newjson[ON_OFF_STATE] = False
        # TODO this works for things with "thermostat" in the name, which is kind of specific to my house
        if "thermostat" in event.name:
            measurement = "thermostat_changes"
            modify_json_for_thermostat_event(event, newjson)

    json_body = [{"measurement": measurement, "time": record.read_time().strftime(DATE_FORMAT), "tags": newtags, "fields": newjson}]
    return newjson, json_body


def modify_json_for_thermostat_event(event: ReceivedEvent, newjson: Dict):
    """
    Form a useful json event from thermostat log entries.

    Pass by reference means we're operating on the newjson dict directly, no return required.
    :param event: The event to get interesting stuff from.
    :param newjson: The new json to be written to InfluxDB
    """
    if "set cool setpoint" in event.what or "cool setpoint changed to" in event.what:
        try:
            newjson["coolSetpoint"] = float(event.what.split()[:-1])
            newjson["state.setpointCool"] = float(event.what.split()[:-1])
        except KeyError:
            pass
    elif "set heat setpoint" in event.what or "heat setpoint changed to" in event.what:
        try:
            newjson["heatSetpoint"] = float(event.what.split()[:-1])
            newjson["state.setpointHeat"] = float(event.what.split()[:-1])
        except KeyError:
            pass
    elif "temperature changed to" in event.what:
        newjson["state.temperatureInput1"] = float(temp(event.what))
        newjson["state.temperatureString"] = str(temp(event.what))
    elif "humidity changed to" in event.what:
        newjson["state.humidityInput1"] = float(temp(event.what))
        newjson["state.humidityString"] = str(temp(event.what))

    try:
        # not sure if its heating or cooling season, so:
        newjson["coolIsOn"] = newjson["onState"]
        newjson["state.hvacCoolIsOn"] = newjson["onState"]
        newjson["heatIsOn"] = newjson["onState"]
        newjson["state.hvacHeatIsOn"] = newjson["onState"]
    except KeyError:
        pass
    try:
        del newjson["onState"]
    except KeyError:
        pass
    try:
        del newjson[ON_OFF_STATE]
    except KeyError:
        pass
    # remember pass by reference means we're operating on the newjson dict directly, no return.


def send_record(record: IndigoRecord, connection: InfluxDBClient) -> None:
    """
    Send the current record to influxdb.

    Device updates come in one of two flavors - lists of objects, or just objects.

    Weather gets a special path.
    """

    # Write existing debug info back - more data available.
    # Things that are already JSON lists:
    if record.notes.startswith("["):
        newjson = json_for_list(record)
        if not newjson:
            return
        send_new_json_with_retry(newjson, connection)

    # things that are already JSON objects:
    elif record.notes.startswith("{"):
        newjson = json_for_object(record)
        send_new_json_with_retry(newjson, connection)

    # for the general case - like Insteon on off events, thermostat changes, etc.
    try:
        newjson, json_body = json_for_insteon_events(record)
        # TODO keep an eye on this 2 thing, why did I need this again?
        if len(newjson.keys()) > 2:
            print(json.dumps(json_body))
            connection.write_points(json_body, time_precision="s")

    except Exception as e:
        print("Error doing something. Anything. Continuing!")
        print(str(e))


@click.command()
@click.option("--influxdb-host", type=str, default="localhost", show_default=True, env="INHOST", help="The influxdb host to connect to.")
@click.option("--influxdb-port", type=int, default=8086, show_default=True, env="INPORT", help="The influxdb port to connect to.")
@click.option("--influxdb-user", type=int, default="indigo", show_default=True, env="INUSER", help="The influxdb user to connect as.")
@click.option("--influxdb-pass", type=str, default="indigo", show_default=True, env="INPASS", help="The influxdb password.")
@click.option("--influxdb-database", type=str, default="indigo", show_default=True, env="INDB", help="The influxdb database.")
def main(influxdb_host, influxdb_port, influxdb_user, influxdb_pass, influxdb_database):
    connection = InfluxDBClient(
        host=influxdb_host, port=influxdb_port, username=influxdb_user, password=influxdb_pass, database=influxdb_database
    )

    il = IndigoLog()

    for x in il.records():
        try:
            send_record(x, connection)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print("skipping a line")
            print(str(e))


if __name__ == "__main__":
    main()
