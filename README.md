# indigo-backfill-influx

This fills the influxdb (created by the indigo-influx project) with entries that are culled from the logs of Indigo 7, instead of live device changes. A lot less information is available, but it's enough to show on/off changes and temperature changes on thermostats. 

This is a python3 script and module. 

# Quickstart for your Mac

```
brew install python3
pip3 install indigodb

# make sure backfill.py and log.py are in your current directory

python3 ./backfill.py
```

## Options:

Environment vars set InfluxDB connection settings. Defaults are set for the brew install of InfluxDB and the indigo user/pass/database, but you can override these with INHOST, INPORT, INUSER, INPASS, INDB like this:

```
INHOST=192.168.1.19 INPORT=8085 python3 ./backfill.py
```


