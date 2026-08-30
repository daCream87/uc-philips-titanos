
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
        self._source_watch_last: dict[str, str] = {}
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


    async def diagnose_sources(self) -> dict[str, Any]:
        """Log raw responses from likely Titan OS / JointSpace source endpoints.

        Diagnostic-only: GET requests, no source switching and no state changes.
        Uses the already authenticated httpx client and logs HTTP status plus the
        complete response body for every endpoint, including non-2xx responses.
        """
        endpoints = (
            "sources",
            "activities",
            "activities/current",
            "currentactivity",
            "channeldb/tv",
            "menuitems/settings/current",
            # Keep useful candidates from v0.9.4 as well.
            "activities/tv",
            "input/sources",
            "applications",
        )
        await self.start()
        assert self._client is not None
        results: dict[str, Any] = {}
        _LOG.info("SOURCE_DIAG START base=%s", self.base)
        for endpoint in endpoints:
            url = f"{self.base}/{endpoint.lstrip('/')}"
            _LOG.info("SOURCE_DIAG GET /%s/%s", self.api_version, endpoint)
            try:
                response = await self._client.get(url)
                body = response.text
                try:
                    parsed = response.json() if response.content else None
                    rendered = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                except Exception:
                    parsed = body
                    rendered = " ".join(body.split())
                _LOG.info("SOURCE_DIAG HTTP %s endpoint=/%s/%s", response.status_code, self.api_version, endpoint)
                _LOG.info("SOURCE_DIAG RESPONSE endpoint=/%s/%s body=%s", self.api_version, endpoint, rendered)
                results[endpoint] = {"status": response.status_code, "response": parsed}
            except Exception as err:
                results[endpoint] = {"error": f"{type(err).__name__}: {err}"}
                _LOG.exception("SOURCE_DIAG ERROR endpoint=/%s/%s type=%s error=%s",
                               self.api_version, endpoint, type(err).__name__, err)
        _LOG.info("SOURCE_DIAG END")
        return results


    async def watch_source_activity(self) -> None:
        """Log compact source/activity responses only when they change.

        This is diagnostic-only and performs GET requests. It lets a tester switch
        inputs on the TV and later correlate each input with the JointSpace payload.
        """
        await self.start()
        assert self._client is not None
        for endpoint in ("activities/current", "activities/tv"):
            url = f"{self.base}/{endpoint}"
            try:
                response = await self._client.get(url)
                if response.status_code != 200:
                    continue
                try:
                    parsed = response.json() if response.content else None
                    rendered = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                except Exception:
                    rendered = " ".join(response.text.split())
                if self._source_watch_last.get(endpoint) != rendered:
                    self._source_watch_last[endpoint] = rendered
                    _LOG.info("SOURCE_WATCH CHANGE endpoint=/%s/%s body=%s",
                              self.api_version, endpoint, rendered)
            except Exception as err:
                _LOG.debug("SOURCE_WATCH ERROR endpoint=/%s/%s type=%s error=%s",
                           self.api_version, endpoint, type(err).__name__, err)


    async def source_discovery(self) -> dict[str, Any]:
        """Probe known JointSpace/Titan source mechanisms and log all results.

        Uses the existing authenticated Remote 3 connection. It deliberately
        avoids destructive settings calls. Key candidates are sent one at a
        time and activity is sampled after each attempt.
        """
        await self.start()
        assert self._client is not None
        results: dict[str, Any] = {}
        _LOG.warning("HDMI_DISCOVERY START base=%s", self.base)

        # First inventory endpoints. Non-2xx responses are useful evidence.
        gets = (
            "system", "activities/current", "activities/tv", "activities",
            "sources", "sources/current", "input/sources", "currentactivity",
            "applications", "mappings", "menuitems/settings/current",
        )
        for endpoint in gets:
            url = f"{self.base}/{endpoint}"
            try:
                r = await self._client.get(url)
                body = " ".join(r.text.split())[:4000]
                _LOG.warning("HDMI_DISCOVERY GET endpoint=/%s/%s status=%s body=%s",
                             self.api_version, endpoint, r.status_code, body)
                results[f"GET {endpoint}"] = r.status_code
            except Exception as err:
                _LOG.warning("HDMI_DISCOVERY GET endpoint=/%s/%s error=%s",
                             self.api_version, endpoint, err)

        # Raw keys seen across Philips/JointSpace implementations. A 200 alone
        # is NOT considered success; the post-attempt activity is logged.
        keys = (
            "Hdmi1", "HDMI1", "SourceHdmi1", "SourceHDMI1",
            "Hdmi2", "HDMI2", "SourceHdmi2", "SourceHDMI2",
            "Hdmi3", "HDMI3", "SourceHdmi3", "SourceHDMI3",
            "Hdmi4", "HDMI4", "SourceHdmi4", "SourceHDMI4",
            "F1", "F2", "F3", "F4",
        )
        for key in keys:
            try:
                r = await self._client.post(f"{self.base}/input/key", json={"key": key})
                _LOG.warning("HDMI_DISCOVERY KEY key=%s status=%s body=%s",
                             key, r.status_code, " ".join(r.text.split())[:1000])
            except Exception as err:
                _LOG.warning("HDMI_DISCOVERY KEY key=%s error=%s", key, err)
            await asyncio.sleep(0.8)
            try:
                r = await self._client.get(f"{self.base}/activities/current")
                _LOG.warning("HDMI_DISCOVERY AFTER key=%s activity_status=%s activity=%s",
                             key, r.status_code, " ".join(r.text.split())[:2000])
            except Exception as err:
                _LOG.warning("HDMI_DISCOVERY AFTER key=%s error=%s", key, err)

        # Legacy source-current payloads. Modern API 6 often rejects these,
        # but testing them establishes whether this Titan firmware retained it.
        for source_id in ("hdmi1","hdmi2","hdmi3","hdmi4","hdm1","hdm2","hdm3","hdm4"):
            url = f"{self.base}/sources/current"
            try:
                r = await self._client.post(url, json={"id": source_id})
                _LOG.warning("HDMI_DISCOVERY SOURCE_CURRENT id=%s status=%s body=%s",
                             source_id, r.status_code, " ".join(r.text.split())[:1000])
            except Exception as err:
                _LOG.warning("HDMI_DISCOVERY SOURCE_CURRENT id=%s error=%s", source_id, err)
            await asyncio.sleep(0.5)

        _LOG.warning("HDMI_DISCOVERY END")
        return results

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
