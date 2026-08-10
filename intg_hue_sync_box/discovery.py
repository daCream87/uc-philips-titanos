from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

SERVICE_TYPE = "_huesync._tcp.local."


@dataclass(frozen=True)
class DiscoveredHueSyncBox:
    host: str
    unique_id: str
    name: str
    port: int = 443
    path: str = "/api"


class _Listener(ServiceListener):
    def __init__(self, zc: Zeroconf):
        self._zc = zc
        self.devices: list[DiscoveredHueSyncBox] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name, timeout=1500)
        if info is None:
            return
        props = {
            (k.decode("utf-8", "ignore") if isinstance(k, bytes) else str(k)).lower():
            (v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v))
            for k, v in info.properties.items()
        }
        addresses = info.parsed_addresses()
        if not addresses:
            return
        unique_id = props.get("uniqueid", "").strip()
        if not unique_id:
            return
        self.devices.append(
            DiscoveredHueSyncBox(
                host=addresses[0],
                unique_id=unique_id,
                name=props.get("name", "Hue Sync Box") or "Hue Sync Box",
                port=info.port or 443,
                path=props.get("path", "/api") or "/api",
            )
        )

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        return


def _discover_sync(timeout: float) -> list[DiscoveredHueSyncBox]:
    zc = Zeroconf()
    listener = _Listener(zc)
    browser = ServiceBrowser(zc, SERVICE_TYPE, listener)
    try:
        time.sleep(timeout)
        unique: dict[str, DiscoveredHueSyncBox] = {}
        for device in listener.devices:
            unique[device.unique_id] = device
        return list(unique.values())
    finally:
        browser.cancel()
        zc.close()


async def discover(timeout: float = 3.0) -> list[DiscoveredHueSyncBox]:
    return await asyncio.to_thread(_discover_sync, timeout)
