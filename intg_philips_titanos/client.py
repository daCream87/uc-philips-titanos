
from __future__ import annotations
import asyncio, json, logging, socket
from dataclasses import dataclass
from typing import Any
import httpx
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
    def __init__(self, host: str, api_version: int = 6, username: str = "", password: str = "",
                 verify_tls: bool = False, timeout: float = 5.0, secured_transport: bool = True) -> None:
        self.host, self.api_version = host, api_version
        self.username, self.password = username, password
        self.verify_tls, self.timeout = verify_tls, timeout
        self.secured_transport = secured_transport
        self._client: httpx.AsyncClient | None = None
        self._rebuild_base()

    def _rebuild_base(self) -> None:
        protocol = "https" if self.secured_transport else "http"
        port = 1926 if self.secured_transport else 1925
        self.base = f"{protocol}://{self.host}:{port}/{self.api_version}"

    async def start(self) -> None:
        if self._client is not None:
            return
        auth = httpx.DigestAuth(self.username, self.password) if self.username else None
        self._client = httpx.AsyncClient(auth=auth, verify=self.verify_tls,
            timeout=httpx.Timeout(self.timeout), follow_redirects=True, trust_env=False)
        _LOG.info("Philips HTTP client created: base=%s secured=%s auth=%s",
                  self.base, self.secured_transport, bool(auth))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None,
                       retries: int = 2) -> Any:
        await self.start()
        assert self._client is not None
        url = f"{self.base}/{endpoint.lstrip('/')}"
        last_error = None
        for attempt in range(1, retries + 2):
            try:
                _LOG.debug("Philips request attempt=%s method=%s url=%s", attempt, method, url)
                response = await self._client.request(method, url, json=payload)
                _LOG.debug("Philips response status=%s url=%s", response.status_code, url)
                response.raise_for_status()
                if not response.content:
                    return None
                try:
                    return response.json()
                except Exception:
                    return response.text
            except Exception as err:
                last_error = err
                _LOG.warning("Philips request failed attempt=%s/%s type=%s url=%s error=%s",
                             attempt, retries + 1, type(err).__name__, url, err)
                if attempt <= retries:
                    await asyncio.sleep(0.4 * attempt)
        raise PhilipsConnectionError(
            f"{method} {url} failed after {retries + 1} attempts: "
            f"{type(last_error).__name__}: {last_error}") from last_error

    async def get(self, endpoint: str) -> Any:
        return await self._request("GET", endpoint)

    async def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        return await self._request("POST", endpoint, payload)

    async def send_key(self, key: str) -> None:
        await self.post("input/key", {"key": key})

    async def set_volume(self, value: int, muted: bool = False) -> None:
        await self.post("audio/volume",
                        {"current": max(0, min(60, int(value))), "muted": bool(muted)})

    async def wake_on_lan(self, mac: str) -> None:
        clean = mac.replace(":", "").replace("-", "")
        if len(clean) != 12:
            raise ValueError("Invalid MAC address")
        packet = bytes.fromhex("FF" * 6 + clean * 16)
        def _send():
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(packet, ("255.255.255.255", 9))
        await asyncio.to_thread(_send)

    async def read_state(self) -> TvState:
        state = TvState()
        try:
            power = await self.get("powerstate")
            state.online = True
            state.power = str(power.get("powerstate", "On")).upper() if isinstance(power, dict) else "ON"
        except Exception:
            return state
        try:
            audio = await self.get("audio/volume")
            if isinstance(audio, dict):
                state.volume = int(audio["current"]) if audio.get("current") is not None else None
                state.muted = bool(audio.get("muted", False))
        except Exception:
            _LOG.debug("audio/volume unavailable", exc_info=True)
        return state
