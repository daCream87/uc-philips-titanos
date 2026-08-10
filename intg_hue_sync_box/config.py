from dataclasses import dataclass


@dataclass
class HueSyncConfig:
    identifier: str
    name: str
    host: str
    unique_id: str
    access_token: str
    registration_id: str
    port: int = 443
    path: str = "/api"
    poll_interval: int = 3
