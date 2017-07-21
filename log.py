from pathlib import Path, PosixPath
from datetime import datetime
from itertools import chain
import re

logdir = Path('/Library/Application Support/Perceptive Automation/Indigo 7/Logs')

class ReceivedEvent:
    def __init__(self, record):
        try:
            str_list = list(filter(None, [x.strip() for x in re.split('"|\(|\)', record.notes)]))
            if len(str_list) < 2:
                self.name = ''
                self.what = ''
                self.button = ''
                return
            self.name = str_list[0]
            self.what = str_list[1]
            if (len(str_list) == 2):
                self.button = ""
            if (len(str_list) == 3):
                self.button = str_list[2]
            if (len(str_list) == 4):
                self.button = str_list[3]
        except:
            print("Error constructing a ReceivedEvent")
            print(record.notes)

class IndigoRecord:
    def readtime(self):
        return datetime.strptime(self.time.split('.')[0], '%Y-%m-%d %H:%M:%S')

    def readevent(self):
        if self.event != '':
            evt = ReceivedEvent(self)
            if evt.name != '':
                return evt
        return None

    def __init__(self):
        self.time = ''
        self.event = ''
        self.notes = ''

    def __init__(self, line):
        try:
            (self.time, self.event, self.notes) = line.split('\t')
        except:
            self.time = ''
            self.event = ''
            self.notes = ''

    def __str__(self):
        return 'IndigoRecord'

class IndigoLogFile:
    def __init__(self, inpath):
        self.path_ = inpath

    def __str__(self):
        return str(self.path_)

    def lines(self):
        with open(self.path_, 'r') as ff:
            return [x.rstrip() for x in ff]

    def records(self):
        return [IndigoRecord(x) for x in self.lines()]

class IndigoLog:
    def __init__(self):
        self.files_ = [IndigoLogFile(x) for x in logdir.iterdir() if 'Events.txt' in x.name]

    def lines(self):
        return [ff.lines() for ff in self.files_]

    def records(self):
        lines = [ff.records() for ff in self.files_]
        return [i for i in chain.from_iterable(lines)]


