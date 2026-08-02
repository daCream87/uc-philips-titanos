from __future__ import annotations

import inspect
import logging
import re
from typing import Any

from haphilipsjs import PhilipsTV
from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from intg_philips_titanos.config import PhilipsConfig

_LOG = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> Any:
    """Support both asynchronous and older synchronous ha-philipsjs releases."""
    return await value if inspect.isawaitable(value) else value


class PhilipsSetupFlow(BaseSetupFlow[PhilipsConfig]):
    """Two-stage setup using the exact pairing sequence proven on Windows."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._temp_host: str | None = None
        self._temp_mac: str = ""
        self._temp_name: str = "Philips TV"
        self._temp_tv: PhilipsTV | None = None
        self._temp_pair_state: dict[str, Any] | None = None

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Philips TV Setup", "de": "Philips-TV einrichten"},
            [
                {
                    "id": "name",
                    "label": {"en": "Device name", "de": "Gerätename"},
                    "field": {"text": {"value": "Philips 77OLED759/12"}},
                },
                {
                    "id": "host",
                    "label": {"en": "TV IP address", "de": "TV-IP-Adresse"},
                    "field": {"text": {"value": "192.168.178.58"}},
                },
                {
                    "id": "mac",
                    "label": {"en": "MAC address", "de": "MAC-Adresse"},
                    "field": {"text": {"value": "38:1B:9E:DF:6F:CA"}},
                },
            ],
        )

    def _pin_form(self, message: str | None = None) -> RequestUserInput:
        fields: list[dict[str, Any]] = []
        if message:
            fields.append(
                {
                    "id": "info",
                    "label": {"en": "Pairing", "de": "Kopplung"},
                    "field": {"label": {"value": {"en": message, "de": message}}},
                }
            )
        fields.append(
            {
                "id": "pin",
                "label": {"en": "PIN shown on TV", "de": "Am TV angezeigte PIN"},
                "field": {"text": {"value": ""}},
            }
        )
        return RequestUserInput(
            {"en": "Enter PIN from Philips TV", "de": "PIN vom Philips-TV eingeben"},
            fields,
        )

    async def query_device(self, input_values: dict[str, Any]) -> PhilipsConfig | RequestUserInput:
        if "pin" in input_values:
            if not self._temp_host or self._temp_tv is None or self._temp_pair_state is None:
                raise ValueError("Pairing session expired. Restart setup and request a new PIN.")
            return await self._verify_pin(input_values)
        return await self._request_pairing(input_values)

    async def _close_temp_tv(self) -> None:
        tv = self._temp_tv
        self._temp_tv = None
        if tv is not None:
            try:
                close = getattr(tv, "aclose", None)
                if close:
                    await _maybe_await(close())
            except Exception:
                _LOG.debug("Could not close temporary Philips client", exc_info=True)

    async def _request_pairing(self, input_values: dict[str, Any]) -> RequestUserInput:
        host = str(input_values.get("host", "")).strip()
        mac = str(input_values.get("mac", "")).strip()
        name = str(input_values.get("name", "Philips TV")).strip() or "Philips TV"

        if not host:
            raise ValueError("TV IP address is required")
        if mac and not re.fullmatch(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", mac):
            raise ValueError("Invalid MAC address")

        await self._close_temp_tv()
        self._temp_host = host
        self._temp_mac = mac
        self._temp_name = name
        self._temp_pair_state = None

        tv = PhilipsTV(host, 6)
        self._temp_tv = tv

        try:
            _LOG.info("Connecting to Philips TV %s using JointSpace API 6", host)
            system = await _maybe_await(tv.getSystem())
            secured = getattr(tv, "secured_transport", None)
            _LOG.info(
                "Philips TV detected: api=%s secured=%s pairing=%s",
                getattr(tv, "api_version_detected", 6),
                secured,
                getattr(tv, "pairing_type", None),
            )

            # Exact transport logic from the successful Windows test.
            await _maybe_await(tv.setTransport(secured_transport=True if secured is None else secured))

            async def request_pairing() -> dict[str, Any]:
                return await _maybe_await(
                    tv.pairRequest(
                        "unfolded_circle",
                        "Unfolded Circle Remote 3",
                        "remote3",
                        "Linux",
                        "native",
                    )
                )

            try:
                pair_state = await request_pairing()
            except Exception as first_error:
                # Some firmware advertises the wrong transport. Repeat the proven
                # Windows fallback once via the opposite port/protocol.
                current = getattr(tv, "protocol", "http")
                alternative_secure = current != "https"
                _LOG.warning(
                    "First pairing request failed via %s: %s. Retrying via %s",
                    current,
                    first_error,
                    "https" if alternative_secure else "http",
                )
                await _maybe_await(tv.setTransport(secured_transport=alternative_secure))
                pair_state = await request_pairing()

            if not isinstance(pair_state, dict):
                raise RuntimeError(f"Unexpected pairing state: {pair_state!r}")

            self._temp_pair_state = pair_state
            return self._pin_form()
        except Exception as err:
            _LOG.exception("Philips pairing request failed")
            await self._reset_temp()
            raise ValueError(
                f"TV at {host} could not be paired: {err}. "
                "Switch the TV on and make sure it is in the same network."
            ) from err

    async def _verify_pin(self, input_values: dict[str, Any]) -> PhilipsConfig:
        pin = str(input_values.get("pin", "")).strip()
        if not pin or not pin.isdigit():
            raise ValueError("The PIN must contain digits only")

        assert self._temp_tv is not None
        assert self._temp_host is not None
        assert self._temp_pair_state is not None

        try:
            # Exact call that succeeded in pair_tv.py on the user's Windows PC.
            result = await _maybe_await(self._temp_tv.pairGrant(self._temp_pair_state, pin))
            if not isinstance(result, (tuple, list)) or len(result) != 2:
                raise RuntimeError(f"Unexpected pairing response: {result!r}")

            username, password = str(result[0]), str(result[1])
            protocol = getattr(self._temp_tv, "protocol", "https")

            # Verify the newly issued Digest credentials before returning the config.
            verifier = PhilipsTV(
                self._temp_host,
                6,
                secured_transport=(protocol == "https"),
                username=username,
                password=password,
                verify=False,
            )
            try:
                await _maybe_await(verifier.getPowerState())
                await _maybe_await(verifier.getAudiodata())
            finally:
                close = getattr(verifier, "aclose", None)
                if close:
                    await _maybe_await(close())

            config = PhilipsConfig(
                identifier=f"philips_{self._temp_host.replace('.', '_')}",
                name=self._temp_name,
                host=self._temp_host,
                mac=self._temp_mac,
                api_version=6,
                username=username,
                password=password,
                secured_transport=(protocol == "https"),
                poll_interval=3,
            )
            _LOG.info("Philips pairing completed and credentials verified for %s", self._temp_host)
            await self._reset_temp()
            return config
        except Exception as err:
            # Keep host and pair state for another PIN attempt. Do not throw away
            # the setup page and force the user into the broken Retry loop.
            _LOG.exception("Philips PIN verification failed")
            raise ValueError(f"PIN verification failed: {err}") from err

    async def _reset_temp(self) -> None:
        await self._close_temp_tv()
        self._temp_host = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_pair_state = None
