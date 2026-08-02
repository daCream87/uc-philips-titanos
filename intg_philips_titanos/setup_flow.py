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
    return await value if inspect.isawaitable(value) else value

class PhilipsSetupFlow(BaseSetupFlow[PhilipsConfig]):
    """Two-step Remote 3 setup: connection data, then Philips pairing PIN."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._temp_host: str | None = None
        self._temp_mac: str = ""
        self._temp_name: str = "Philips TV"
        self._temp_tv: PhilipsTV | None = None
        self._temp_pair_state: Any = None

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
                    "label": {"en": "MAC address (Wake-on-LAN)", "de": "MAC-Adresse (Wake-on-LAN)"},
                    "field": {"text": {"value": "38:1B:9E:DF:6F:CA"}},
                },
            ],
        )

    async def query_device(self, input_values: dict[str, Any]) -> PhilipsConfig | RequestUserInput:
        if "pin" in input_values and self._temp_host and self._temp_tv is not None:
            return await self._verify_pin(input_values)
        return await self._request_pairing(input_values)

    async def _request_pairing(self, input_values: dict[str, Any]) -> RequestUserInput:
        host = str(input_values.get("host", "")).strip()
        mac = str(input_values.get("mac", "")).strip()
        name = str(input_values.get("name", "Philips TV")).strip() or "Philips TV"

        if not host:
            raise ValueError("TV IP address is required")
        if mac and not re.fullmatch(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", mac):
            raise ValueError("Invalid MAC address")

        self._temp_host = host
        self._temp_mac = mac
        self._temp_name = name

        try:
            tv = PhilipsTV(host, 6)
            await _maybe_await(tv.getSystem())

            # Titan OS API 6.1 requires secure transport on port 1926.
            await _maybe_await(tv.setTransport(secured_transport=True))

            try:
                pair_state = await _maybe_await(
                    tv.pairRequest(
                        "unfolded_circle",
                        "Unfolded Circle Remote 3",
                        "remote3",
                        "Linux",
                        "native",
                    )
                )
            except TypeError:
                # Compatibility with library variants using fewer arguments.
                pair_state = await _maybe_await(tv.pairRequest())

            self._temp_tv = tv
            self._temp_pair_state = pair_state

            return RequestUserInput(
                {"en": "Enter PIN from Philips TV", "de": "PIN vom Philips-TV eingeben"},
                [
                    {
                        "id": "pin",
                        "label": {"en": "PIN shown on TV", "de": "Am TV angezeigte PIN"},
                        "field": {"text": {"value": ""}},
                    }
                ],
            )
        except Exception as err:
            self._reset_temp()
            _LOG.exception("Philips pairing request failed")
            raise ValueError(
                f"TV at {host} could not be paired: {err}. "
                "The TV must be switched on and in the same network."
            ) from err

    async def _verify_pin(self, input_values: dict[str, Any]) -> PhilipsConfig:
        pin = str(input_values.get("pin", "")).strip()
        if not re.fullmatch(r"\d{4,8}", pin):
            raise ValueError("Please enter the PIN shown on the TV")

        assert self._temp_tv is not None
        assert self._temp_host is not None

        try:
            result = await _maybe_await(self._temp_tv.pairGrant(self._temp_pair_state, pin))
            username, password = str(result[0]), str(result[1])

            config = PhilipsConfig(
                identifier=f"philips_{self._temp_host.replace('.', '_')}",
                name=self._temp_name,
                host=self._temp_host,
                mac=self._temp_mac,
                api_version=6,
                username=username,
                password=password,
                secured_transport=True,
                poll_interval=3,
            )
            self._reset_temp()
            return config
        except Exception as err:
            self._reset_temp()
            _LOG.exception("Philips PIN verification failed")
            raise ValueError(f"PIN verification failed: {err}") from err

    def _reset_temp(self) -> None:
        self._temp_host = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_tv = None
        self._temp_pair_state = None
