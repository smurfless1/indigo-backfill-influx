from dataclasses import dataclass

from influxdb_client import WriteApi


@dataclass
class Influx20ConnectionState:
    api: WriteApi
    token: str
    org: str
    bucket: str
    host: str = "https://us-west-2-1.aws.cloud2.influxdata.com"


