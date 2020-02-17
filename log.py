import re
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import List, Optional

logdir = Path("/Library/Application Support/Perceptive Automation/Indigo 7/Logs")


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
        except IndexError:
            self.time = ""
            self.event = ""
            self.notes = ""

    def __str__(self) -> str:
        """String representation."""
        return "IndigoRecord"


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
