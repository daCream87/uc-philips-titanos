from dataclasses import dataclass


@dataclass
class PhilipsConfig:
    identifier: str
    name: str
    host: str
    mac: str
    api_version: int = 6
    username: str = ""
    password: str = ""
    secured_transport: bool = True
    poll_interval: int = 3
