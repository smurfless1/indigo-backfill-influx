import json
import re
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import List, Optional
from indigo import InfluxEvent, InfluxFields, InfluxTag

logdir = Path("/Library/Application Support/Perceptive Automation/Indigo 7.4/Logs")

ON_OFF_STATE = "state.onOffState"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def last_member(note: str):
    """Honestly I don't remember why I needed this."""
    return note.split()[-1]


class ReceivedEvent:
    """Describe an event received by indigo."""

    def __init__(self, notes: str):
        """Construct from a note in the IndigoRecord."""
        try:
            str_list = list(filter(None, [x.strip() for x in re.split('["()]', notes)]))
            if len(str_list) < 2:
                self.name = ""
                self.what = ""
                self.button = ""
                return
            self.name = str_list[0]
            self.what = str_list[1]
            if len(str_list) == 2:
                self.button = ""
            if len(str_list) == 3:
                self.button = str_list[2]
            if len(str_list) == 4:
                self.button = str_list[3]
        except IndexError:
            print("Error constructing a ReceivedEvent")
            print(notes)


class IndigoRecord:
    """An indigo log record."""

    def read_time(self) -> datetime.timestamp:
        """Form a datetime from the string."""
        return datetime.strptime(self.time.split(".")[0], "%Y-%m-%d %H:%M:%S")

    def read_event(self) -> Optional[ReceivedEvent]:
        """Read an event from the indigo record."""
        if self.event != "":
            evt = ReceivedEvent(self.notes)
            if evt.name != "":
                return evt
        return None

    def __init__(self, line):
        """Constructor."""
        try:
            (self.time, self.event, self.notes) = line.split("\t")
        except (ValueError, IndexError):
            self.time = ""
            self.event = ""
            self.notes = ""

    def __str__(self) -> str:
        """String representation."""
        return "IndigoRecord"

    def json_for_insteon_events(self):
        event = self.read_event()
        if event is None:
            return None

        on: Optional[bool] = None
        measurement: str = "device_changes"
        cool: Optional[float] = None
        heat: Optional[float] = None
        temperature: Optional[float] = None
        humidity: Optional[float] = None
        brightness: Optional[float] = None

        # NOAA weather doesn't log on my box. Bummer!
        # updates - thermostat
        if "INSTEON" in self.event:
            # lights on off dim: set state
            if "on to" in event.what:
                brightness = float(last_member(event.what))
                if brightness == 0.0:
                    on = False
                else:
                    on = True
            elif event.what == "on":
                on = True
            elif event.what == "off":
                on = False

            elif "set cool setpoint" in event.what or "cool setpoint changed to" in event.what:
                cool = float(event.what.split()[-1])
                measurement = "thermostat_changes"
            elif "set heat setpoint" in event.what or "heat setpoint changed to" in event.what:
                heat = float(event.what.split()[-1])
                measurement = "thermostat_changes"
            elif "temperature changed to" in event.what:
                temperature = float(last_member(event.what))
                measurement = "thermostat_changes"
            elif "humidity changed to" in event.what:
                humidity = float(last_member(event.what))
                measurement = "thermostat_changes"

        ie = InfluxEvent(measurement=measurement, time=self.time, tags=InfluxTag(name=event.name),
                         fields=InfluxFields(
                             cool_setpoint=cool,
                             heat_setpoint=heat,
                             temperature=temperature,
                             humidity=humidity,
                             on=on,
                             brightness=brightness
                         ))

        return ie.to_dict()


class IndigoLogFile:
    """An individual log file as part of the indigo log."""

    def __init__(self, inpath: str):
        """Constructor."""
        self.path_ = inpath

    def __str__(self) -> str:
        """My path as a string."""
        return str(self.path_)

    def lines(self) -> List[str]:
        """All the lines of this log."""
        with open(self.path_, "r") as ff:
            return [x.rstrip() for x in ff]

    def records(self) -> List[IndigoRecord]:
        """Records for each line of this log."""
        return [IndigoRecord(x) for x in self.lines()]


class IndigoLog:
    """The entire log directory as a set."""

    def __init__(self):
        """Constructor."""
        self.files_ = [IndigoLogFile(str(x)) for x in logdir.iterdir() if "Events.txt" in x.name]

    def lines(self) -> List[List[str]]:
        """Lines for all files together."""
        return [ff.lines() for ff in self.files_]

    def records(self) -> List[IndigoRecord]:
        """Records for all files together."""
        lines = [ff.records() for ff in self.files_]
        return [i for i in chain.from_iterable(lines)]
