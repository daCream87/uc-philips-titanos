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


class PhilipsConnectionError(RuntimeError):
    pass


class PhilipsJointSpaceClient:
    """Direct Philips JointSpace API 6 client.

    This keeps the same requests + HTTP Digest approach that was successfully
    tested on Windows against the user's 77OLED759/12.
    """

    def __init__(
        self,
        host: str,
        api_version: int = 6,
        username: str = "",
        password: str = "",
        verify_tls: bool = False,
        timeout: float = 4.0,
        secured_transport: bool = True,
    ) -> None:
        self.host = host
        self.api_version = api_version
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.secured_transport = secured_transport
        self.session = requests.Session()
        if username:
            self.session.auth = HTTPDigestAuth(username, password)
        self.session.verify = verify_tls
        requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
        self._rebuild_base()

    def _rebuild_base(self) -> None:
        protocol = "https" if self.secured_transport else "http"
        port = 1926 if self.secured_transport else 1925
        self.base = f"{protocol}://{self.host}:{port}/{self.api_version}"

    @property
    def port(self) -> int:
        return 1926 if self.secured_transport else 1925

    def tcp_reachable(self, timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        retries: int = 2,
    ) -> Any:
        url = f"{self.base}/{endpoint.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    json=payload,
                    timeout=self.timeout,
                )
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
            except requests.RequestException as err:
                last_error = err
                if attempt < retries:
                    time.sleep(0.35 * (attempt + 1))
                    continue

        raise PhilipsConnectionError(
            f"Philips TV {self.host}:{self.port} is not reachable for "
            f"{method} /{self.api_version}/{endpoint.lstrip('/')}: {last_error}"
        ) from last_error

    def get(self, endpoint: str) -> Any:
        return self._request("GET", endpoint)

    def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", endpoint, payload)

    def send_key(self, key: str) -> None:
        self.post("input/key", {"key": key})

    def restart_tv(self) -> str:
        errors: list[str] = []
        for endpoint in ("system/reboot", "system/restart"):
            try:
                self.post(endpoint, {})
                return endpoint
            except Exception as err:
                errors.append(f"{endpoint}: {err}")
        raise RuntimeError(
            "TV firmware rejected network restart endpoints: " + " | ".join(errors)
        )

    def set_volume(self, value: int, muted: bool = False) -> None:
        self.post(
            "audio/volume",
            {"current": max(0, min(60, int(value))), "muted": bool(muted)},
        )

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
            state.power = (
                str(power.get("powerstate", "On")).upper()
                if isinstance(power, dict)
                else "ON"
            )
        except Exception:
            return state

        for endpoint, handler in (
            ("audio/volume", self._parse_audio),
            ("activities/current", self._parse_activity),
            ("activities/tv", self._parse_tv_activity),
        ):
            try:
                handler(state, self.get(endpoint))
            except Exception:
                _LOG.debug("State endpoint unavailable: %s", endpoint, exc_info=True)
        return state

    @staticmethod
    def _parse_audio(state: TvState, data: Any) -> None:
        if isinstance(data, dict):
            current = data.get("current")
            state.volume = int(current) if current is not None else None
            state.muted = bool(data.get("muted", False))

    @staticmethod
    def _parse_activity(state: TvState, data: Any) -> None:
        if isinstance(data, dict):
            component = data.get("component")
            if isinstance(component, dict):
                state.app = component.get("packageName") or component.get("className")
            state.source = data.get("source") or state.source

    @staticmethod
    def _parse_tv_activity(state: TvState, data: Any) -> None:
        if isinstance(data, dict):
            channel = data.get("channel")
            if isinstance(channel, dict):
                state.channel = str(channel.get("ccid") or channel.get("preset") or "") or None
                state.channel_name = channel.get("name")
