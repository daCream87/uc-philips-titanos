from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests.auth import HTTPDigestAuth

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class TvState:
    online: bool = False
    power: str = "UNKNOWN"
    volume: int | None = None
    muted: bool | None = None
    source: str | None = None
    channel: str | None = None
    channel_name: str | None = None
    app: str | None = None


class PhilipsJointSpaceClient:
    """Small tolerant client for Philips JointSpace API v6 / Titan OS.

    Philips firmware versions are inconsistent: some successful POST requests return
    HTML or an empty body. Therefore status code 2xx is treated as success regardless
    of response JSON.
    """

    def __init__(self, host: str, api_version: int = 6, username: str = "", password: str = "",
                 verify_tls: bool = False, timeout: float = 3.5, secured_transport: bool = True) -> None:
        self.host = host
        self.api_version = api_version
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.session = requests.Session()
        if username:
            self.session.auth = HTTPDigestAuth(username, password)
        self.session.verify = verify_tls
        requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
        protocol = "https" if secured_transport else "http"
        port = 1926 if secured_transport else 1925
        self.base = f"{protocol}://{host}:{port}/{api_version}"

    def _request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base}/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            return response.text

    def get(self, endpoint: str) -> Any:
        return self._request("GET", endpoint)

    def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", endpoint, payload)

    def send_key(self, key: str) -> None:
        self.post("input/key", {"key": key})

    def set_volume(self, value: int, muted: bool = False) -> None:
        self.post("audio/volume", {"current": max(0, min(100, int(value))), "muted": bool(muted)})

    def wake_on_lan(self, mac: str) -> None:
        clean = mac.replace(":", "").replace("-", "")
        if len(clean) != 12:
            raise ValueError("Invalid MAC address")
        packet = bytes.fromhex("FF" * 6 + clean * 16)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(packet, ("255.255.255.255", 9))

    def read_state(self) -> TvState:
        state = TvState()
        try:
            power = self.get("powerstate")
            state.online = True
            if isinstance(power, dict):
                state.power = str(power.get("powerstate", "On")).upper()
            else:
                state.power = "ON"
        except requests.RequestException:
            return state

        for endpoint, handler in (
            ("audio/volume", self._parse_audio),
            ("activities/current", self._parse_activity),
            ("activities/tv", self._parse_tv_activity),
        ):
            try:
                data = self.get(endpoint)
                handler(state, data)
            except requests.RequestException:
                _LOG.debug("State endpoint not supported: %s", endpoint)
            except Exception:
                _LOG.exception("Could not parse endpoint %s", endpoint)
        return state

    @staticmethod
    def _parse_audio(state: TvState, data: Any) -> None:
        if isinstance(data, dict):
            current = data.get("current")
            state.volume = int(current) if current is not None else None
            state.muted = bool(data.get("muted", False))

    @staticmethod
    def _parse_activity(state: TvState, data: Any) -> None:
        if not isinstance(data, dict):
            return
        component = data.get("component")
        if isinstance(component, dict):
            state.app = component.get("packageName") or component.get("className")
        state.source = data.get("source") or state.source

    @staticmethod
    def _parse_tv_activity(state: TvState, data: Any) -> None:
        if not isinstance(data, dict):
            return
        channel = data.get("channel")
        if isinstance(channel, dict):
            state.channel = str(channel.get("ccid") or channel.get("preset") or "") or None
            state.channel_name = channel.get("name")
