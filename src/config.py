from __future__ import annotations
import dataclasses, json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

@dataclass(slots=True)
class DeviceConfig:
    id: str
    name: str
    host: str
    mac: str
    api_version: int
    username: str
    password: str
    secured_transport: bool = True
    verify_tls: bool = False
    poll_interval: float = 2.0

class ConfigStore:
    def __init__(self, data_path: str, on_change: Callable[[], None] | None = None):
        self.path = Path(data_path) / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.on_change = on_change
        self.devices: list[DeviceConfig] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists(): return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.devices = [DeviceConfig(**item) for item in raw.get("devices", [])]
        except Exception:
            self.devices = []

    def save(self) -> None:
        self.path.write_text(json.dumps({"devices":[dataclasses.asdict(d) for d in self.devices]}, indent=2), encoding="utf-8")
        if self.on_change: self.on_change()

    def upsert(self, device: DeviceConfig) -> None:
        self.devices = [d for d in self.devices if d.id != device.id and d.host != device.host]
        self.devices.append(device)
        self.save()

    def remove(self, device_id: str) -> None:
        self.devices = [d for d in self.devices if d.id != device_id]
        self.save()
