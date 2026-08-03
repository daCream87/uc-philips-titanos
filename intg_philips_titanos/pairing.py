
from __future__ import annotations

import base64
import json
import logging
from secrets import token_hex
from typing import Any

import httpx
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.hmac import HMAC

_LOG = logging.getLogger(__name__)

AUTH_SHARED_KEY = base64.b64decode(
    "ZmVay1EQVFOaZhwQ4Kv81ypLAZNczV9sG4KkseXWn1NEk6cXmPKO/MCa9sryslvLCFMnNe4Z4CPXzToowvhHvA=="
)


class PhilipsPairingError(RuntimeError):
    pass


def hmac_signature(timestamp: str, pin: str) -> str:
    hmac = HMAC(AUTH_SHARED_KEY, SHA1())
    hmac.update(timestamp.encode("utf-8"))
    hmac.update(pin.encode("utf-8"))
    return base64.b64encode(hmac.finalize()).decode("utf-8")


class PhilipsPairingClient:
    """Direct Philips API 6 pairing client without haphilipsjs."""

    def __init__(self, host: str, timeout: float = 8.0) -> None:
        self.host = host
        self.timeout = timeout
        self.protocol = "https"
        self.system: dict[str, Any] = {}
        self._client = httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(timeout, connect=5.0),
            follow_redirects=True,
            trust_env=False,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _url(self, path: str, protocol: str | None = None) -> str:
        protocol = protocol or self.protocol
        port = 1926 if protocol == "https" else 1925
        return f"{protocol}://{self.host}:{port}/6/{path.lstrip('/')}"

    async def discover(self) -> dict[str, Any]:
        errors: list[str] = []

        # Titan OS models commonly expose /system on HTTPS first.
        for protocol in ("https", "http"):
            url = self._url("system", protocol)
            try:
                _LOG.info("Philips discovery request: GET %s", url)
                response = await self._client.get(url)
                _LOG.info(
                    "Philips discovery response: protocol=%s status=%s content_type=%s",
                    protocol,
                    response.status_code,
                    response.headers.get("content-type", ""),
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise PhilipsPairingError(
                        f"Unexpected /system response type: {type(data).__name__}"
                    )

                self.system = data
                system_features = (
                    data.get("featuring", {})
                    .get("systemfeatures", {})
                )
                secured = system_features.get("secured_transport") in (True, "true")
                self.protocol = "https" if secured else protocol

                _LOG.info(
                    "Philips TV discovered: name=%s api=%s secured_transport=%s pairing_type=%s selected_protocol=%s",
                    data.get("name"),
                    data.get("api_version"),
                    secured,
                    system_features.get("pairing_type"),
                    self.protocol,
                )
                return data
            except Exception as err:
                errors.append(f"{protocol}: {type(err).__name__}: {err}")
                _LOG.warning(
                    "Philips discovery failed: protocol=%s url=%s type=%s error=%s",
                    protocol,
                    url,
                    type(err).__name__,
                    err,
                )

        raise PhilipsPairingError(
            "Philips /system could not be reached. " + " | ".join(errors)
        )

    async def pair_request(
        self,
        app_id: str = "unfolded_circle",
        app_name: str = "Unfolded Circle Remote 3",
        device_name: str = "remote3",
        device_os: str = "Linux",
        device_type: str = "native",
    ) -> dict[str, Any]:
        device = {
            "device_name": device_name,
            "device_os": device_os,
            "type": device_type,
            "id": token_hex(16),
            "app_id": app_id,
            "app_name": app_name,
        }

        access: dict[str, Any] = {
            "scope": ["read", "write", "control"]
        }
        featuring = self.system.get("featuring")
        if featuring:
            access["featuring"] = featuring

        payload = {
            "access": access,
            "device": device,
        }
        url = self._url("pair/request")

        _LOG.info("Philips pair request: POST %s", url)
        _LOG.debug("Philips pair request payload: %s", payload)

        response = await self._client.post(url, json=payload)
        _LOG.info(
            "Philips pair request response: status=%s content_type=%s",
            response.status_code,
            response.headers.get("content-type", ""),
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError as err:
            raise PhilipsPairingError(
                f"Pair request returned non-JSON data: {response.text[:300]}"
            ) from err

        _LOG.debug("Philips pair request response payload: %s", data)

        if data.get("error_id") != "SUCCESS":
            raise PhilipsPairingError(f"Pair request rejected: {data}")

        return {
            "device": device,
            "timestamp": data["timestamp"],
            "auth_key": data["auth_key"],
            "protocol": self.protocol,
        }

    async def pair_grant(
        self,
        state: dict[str, Any],
        pin: str,
    ) -> tuple[str, str]:
        username = str(state["device"]["id"])
        password = str(state["auth_key"])
        timestamp = str(state["timestamp"])

        auth = {
            "auth_appId": "1",
            "auth_timestamp": state["timestamp"],
            "auth_signature": hmac_signature(timestamp, pin),
            "pin": pin,
        }
        payload = {
            "auth": auth,
            "device": state["device"],
        }

        url = self._url("pair/grant", str(state.get("protocol") or self.protocol))
        digest_auth = httpx.DigestAuth(username, password)

        _LOG.info("Philips pair grant: POST %s", url)
        _LOG.debug(
            "Philips pair grant payload: device_id=%s timestamp=%s",
            username,
            timestamp,
        )

        response = await self._client.post(
            url,
            json=payload,
            auth=digest_auth,
        )
        _LOG.info(
            "Philips pair grant response: status=%s content_type=%s",
            response.status_code,
            response.headers.get("content-type", ""),
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError as err:
            raise PhilipsPairingError(
                f"Pair grant returned non-JSON data: {response.text[:300]}"
            ) from err

        _LOG.debug("Philips pair grant response payload: %s", data)

        if data.get("error_id") != "SUCCESS":
            raise PhilipsPairingError(f"Pair grant rejected: {data}")

        return username, password
