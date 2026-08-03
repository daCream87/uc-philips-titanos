from __future__ import annotations

import inspect
import ipaddress
import logging
import re
import socket
from typing import Any

from haphilipsjs import PhilipsTV
from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from intg_philips_titanos.config import PhilipsConfig

_LOG = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _local_ipv4_for(target: str) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target, 9))
            return str(sock.getsockname()[0])
    except OSError:
        return None


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class PhilipsSetupFlow(BaseSetupFlow[PhilipsConfig]):
    """UC setup flow with full add/update/remove/reset/backup/restore support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._temp_host: str | None = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_tv: PhilipsTV | None = None
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
                    "label": {"en": "TV IP Address", "de": "IP-Adresse des Fernsehers"},
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "mac",
                    "label": {"en": "TV MAC Address", "de": "MAC-Adresse des Fernsehers"},
                    "field": {"text": {"value": ""}},
                },
            ],
        )

    def _pin_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Enter PIN from Philips TV", "de": "PIN vom Philips-TV eingeben"},
            [
                {
                    "id": "pin",
                    "label": {"en": "PIN shown on TV", "de": "Am Fernseher angezeigte PIN"},
                    "field": {"text": {"value": ""}},
                }
            ],
        )

    async def query_device(self, input_values: dict[str, Any]) -> PhilipsConfig | RequestUserInput:
        if "pin" in input_values:
            if not self._temp_host or self._temp_tv is None or self._temp_pair_state is None:
                raise ValueError("Pairing session expired. Restart setup.")
            return await self._verify_pin(input_values)
        return await self._request_pairing(input_values)

    async def _request_pairing(self, input_values: dict[str, Any]) -> RequestUserInput:
        host = str(input_values.get("host", "")).strip()
        mac = str(input_values.get("mac", "")).strip()
        name = str(input_values.get("name", "Philips TV")).strip() or "Philips TV"

        try:
            ipaddress.ip_address(host)
        except ValueError as err:
            raise ValueError("Enter a valid TV IP address") from err

        if mac and not re.fullmatch(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", mac):
            raise ValueError("Enter a valid TV MAC address")

        local_ip = _local_ipv4_for(host)
        if local_ip == host:
            raise ValueError(
                f"{host} is the Remote 3 IP address. Enter the Philips TV IP address instead."
            )

        if not _port_open(host, 1926):
            if _port_open(host, 1925):
                _LOG.warning("TV only answers on HTTP port 1925; trying compatibility mode")
            else:
                raise ValueError(
                    f"Philips TV {host} is not reachable on port 1926 or 1925. "
                    "Check the TV IP address and network."
                )

        await self._reset_temp()
        self._temp_host = host
        self._temp_mac = mac
        self._temp_name = name

        tv = PhilipsTV(host, 6)
        self._temp_tv = tv

        try:
            _LOG.info(
                "Pairing Philips TV host=%s remote_ip=%s api=6",
                host,
                local_ip,
            )
            await _maybe_await(tv.getSystem())
            secured = getattr(tv, "secured_transport", True)
            await _maybe_await(tv.setTransport(secured_transport=bool(secured)))

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
            except Exception as first_error:
                _LOG.warning("Pair request failed on advertised transport: %s", first_error)
                await _maybe_await(tv.setTransport(secured_transport=not bool(secured)))
                pair_state = await _maybe_await(
                    tv.pairRequest(
                        "unfolded_circle",
                        "Unfolded Circle Remote 3",
                        "remote3",
                        "Linux",
                        "native",
                    )
                )

            if not isinstance(pair_state, dict):
                raise RuntimeError(f"Unexpected pairing state: {pair_state!r}")

            self._temp_pair_state = pair_state
            return self._pin_form()
        except Exception as err:
            _LOG.exception("Philips pairing request failed")
            await self._reset_temp()
            raise ValueError(f"Philips pairing failed: {err}") from err

    async def _verify_pin(self, input_values: dict[str, Any]) -> PhilipsConfig:
        pin = str(input_values.get("pin", "")).strip()
        if not pin.isdigit():
            raise ValueError("The PIN must contain digits only")

        assert self._temp_tv is not None
        assert self._temp_host is not None
        assert self._temp_pair_state is not None

        try:
            result = await _maybe_await(
                self._temp_tv.pairGrant(self._temp_pair_state, pin)
            )
            if not isinstance(result, (tuple, list)) or len(result) != 2:
                raise RuntimeError(f"Unexpected pairing response: {result!r}")

            username, password = str(result[0]), str(result[1])
            protocol = getattr(self._temp_tv, "protocol", "https")

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
            _LOG.info("Philips pairing completed for %s", self._temp_host)
            await self._reset_temp()
            return config
        except Exception as err:
            _LOG.exception("Philips PIN verification failed")
            await self._reset_temp()
            raise ValueError(
                f"PIN verification failed: {err}. Restart setup for a new PIN."
            ) from err

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

    async def _reset_temp(self) -> None:
        await self._close_temp_tv()
        self._temp_host = None
        self._temp_mac = ""
        self._temp_name = "Philips TV"
        self._temp_pair_state = None
