
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any

from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.pairing import PhilipsPairingClient

_LOG = logging.getLogger(__name__)


def _local_ipv4_for(target: str) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target, 9))
            return str(sock.getsockname()[0])
    except OSError:
        return None


class PhilipsSetupFlow(BaseSetupFlow[PhilipsConfig]):
    """UC setup flow with add/update/remove/reset/backup/restore support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._temp_host: str | None = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_pair_client: PhilipsPairingClient | None = None
        self._temp_pair_state: dict[str, Any] | None = None

    def get_manual_entry_form(self) -> RequestUserInput:
        _LOG.info("Building Philips manual entry form")
        return RequestUserInput(
            {"en": "Philips TV Setup", "de": "Philips-TV einrichten"},
            [
                {
                    "id": "name",
                    "label": {"en": "Device Name", "de": "Gerätename"},
                    "field": {"text": {"value": "Philips TV"}},
                },
                {
                    "id": "host",
                    "label": {
                        "en": "TV IP Address",
                        "de": "IP-Adresse des Fernsehers",
                    },
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "mac",
                    "label": {
                        "en": "TV MAC Address",
                        "de": "MAC-Adresse des Fernsehers",
                    },
                    "field": {"text": {"value": ""}},
                },
            ],
        )

    def _pin_form(self) -> RequestUserInput:
        return RequestUserInput(
            {
                "en": "Enter PIN from Philips TV",
                "de": "PIN vom Philips-TV eingeben",
            },
            [
                {
                    "id": "pin",
                    "label": {
                        "en": "PIN shown on TV",
                        "de": "Am Fernseher angezeigte PIN",
                    },
                    "field": {"text": {"value": ""}},
                }
            ],
        )

    async def query_device(
        self,
        input_values: dict[str, Any],
    ) -> PhilipsConfig | RequestUserInput:
        if "pin" in input_values:
            if (
                not self._temp_host
                or self._temp_pair_client is None
                or self._temp_pair_state is None
            ):
                raise ValueError("Pairing session expired. Restart setup.")
            return await self._verify_pin(input_values)

        return await self._request_pairing(input_values)

    async def _request_pairing(
        self,
        input_values: dict[str, Any],
    ) -> RequestUserInput:
        host = str(input_values.get("host", "")).strip()
        mac = str(input_values.get("mac", "")).strip()
        name = str(input_values.get("name", "Philips TV")).strip() or "Philips TV"

        try:
            ipaddress.ip_address(host)
        except ValueError as err:
            raise ValueError("Enter a valid TV IP address") from err

        if mac and not re.fullmatch(
            r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}",
            mac,
        ):
            raise ValueError("Enter a valid TV MAC address")

        local_ip = _local_ipv4_for(host)
        if local_ip == host:
            raise ValueError(
                f"{host} is the Remote 3 IP address. "
                "Enter the Philips TV IP address instead."
            )

        await self._reset_temp()

        self._temp_host = host
        self._temp_mac = mac
        self._temp_name = name
        self._temp_pair_client = PhilipsPairingClient(host)

        try:
            _LOG.info(
                "Starting direct Philips pairing: tv=%s remote_ip=%s api=6",
                host,
                local_ip,
            )
            await self._temp_pair_client.discover()
            self._temp_pair_state = (
                await self._temp_pair_client.pair_request()
            )
            _LOG.info(
                "Philips pairing PIN requested successfully for %s",
                host,
            )
            return self._pin_form()
        except Exception as err:
            _LOG.exception("Direct Philips pairing request failed")
            await self._reset_temp()
            raise ValueError(
                f"Philips pairing request failed: {type(err).__name__}: {err}"
            ) from err

    async def _verify_pin(
        self,
        input_values: dict[str, Any],
    ) -> PhilipsConfig:
        pin = str(input_values.get("pin", "")).strip()
        if not pin.isdigit():
            raise ValueError("The PIN must contain digits only")

        assert self._temp_pair_client is not None
        assert self._temp_pair_state is not None
        assert self._temp_host is not None

        try:
            username, password = (
                await self._temp_pair_client.pair_grant(
                    self._temp_pair_state,
                    pin,
                )
            )

            protocol = str(
                self._temp_pair_state.get("protocol", "https")
            )

            config = PhilipsConfig(
                identifier=(
                    f"philips_{self._temp_host.replace('.', '_')}"
                ),
                name=self._temp_name,
                host=self._temp_host,
                mac=self._temp_mac,
                api_version=6,
                username=username,
                password=password,
                secured_transport=(protocol == "https"),
                poll_interval=3,
            )

            _LOG.info(
                "Direct Philips pairing completed for %s using %s",
                self._temp_host,
                protocol,
            )
            await self._reset_temp()
            return config
        except Exception as err:
            _LOG.exception("Direct Philips PIN verification failed")
            await self._reset_temp()
            raise ValueError(
                "PIN verification failed: "
                f"{type(err).__name__}: {err}. "
                "Restart setup to request a new PIN."
            ) from err

    async def _reset_temp(self) -> None:
        client = self._temp_pair_client
        self._temp_pair_client = None

        if client is not None:
            try:
                await client.close()
            except Exception:
                _LOG.debug(
                    "Could not close temporary Philips pairing client",
                    exc_info=True,
                )

        self._temp_host = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_pair_state = None
