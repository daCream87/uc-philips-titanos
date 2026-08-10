from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Any

import aiohuesyncbox
from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from intg_hue_sync_box.config import HueSyncConfig
from intg_hue_sync_box.discovery import discover

_LOG = logging.getLogger(__name__)


class HueSyncSetupFlow(BaseSetupFlow[HueSyncConfig]):
    """Two-stage setup with no background pairing task and no parallel sessions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._temp: dict[str, Any] | None = None

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Hue Sync Box Setup", "de": "Hue Sync Box einrichten"},
            [
                {"id": "name", "label": {"en": "Device Name", "de": "Gerätename"}, "field": {"text": {"value": "Hue Sync Box"}}},
                {"id": "host", "label": {"en": "Sync Box IP Address", "de": "IP-Adresse der Sync Box"}, "field": {"text": {"value": ""}}},
                {"id": "unique_id", "label": {"en": "Unique ID (C4...); leave empty for local discovery", "de": "Unique ID (C4...); leer lassen für lokale Suche"}, "field": {"text": {"value": ""}}},
            ],
        )

    def _button_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Pair Hue Sync Box", "de": "Hue Sync Box koppeln"},
            [
                {
                    "id": "pair",
                    "label": {"en": "First tap Continue to start pairing. Then press and briefly hold the physical Sync Box button until the LED lights up green once. Leave PAIR entered and continue.", "de": "Tippe zuerst auf Weiter, um das Pairing zu starten. Drücke anschließend die physische Taste an der Sync Box und halte sie kurz gedrückt, bis die LED einmal kurz grün aufleuchtet. PAIR einfach stehen lassen und fortfahren."},
                    "field": {"text": {"value": "PAIR"}},
                }
            ],
        )

    async def query_device(self, input_values: dict[str, Any]) -> HueSyncConfig | RequestUserInput:
        if "pair" in input_values:
            return await self._finish_pairing(input_values)
        return await self._prepare_pairing(input_values)

    async def _prepare_pairing(self, input_values: dict[str, Any]) -> RequestUserInput:
        name = str(input_values.get("name", "Hue Sync Box")).strip() or "Hue Sync Box"
        host = str(input_values.get("host", "")).strip()
        unique_id = str(input_values.get("unique_id", "")).strip()
        try:
            ipaddress.ip_address(host)
        except ValueError as err:
            raise ValueError("Enter a valid Hue Sync Box IP address") from err

        port, path = 443, "/api"
        if not unique_id:
            devices = await discover(timeout=3.0)
            matches = [d for d in devices if d.host == host]
            if len(matches) != 1:
                raise ValueError("Could not uniquely discover the Sync Box ID for this IP. Enter the Unique ID shown in the Hue app.")
            found = matches[0]
            unique_id, port, path = found.unique_id, found.port, found.path
            if name == "Hue Sync Box" and found.name:
                name = found.name

        # Prove that the host/ID combination reaches the API before starting pairing.
        probe = aiohuesyncbox.HueSyncBox(host, unique_id, port=port, path=path)
        try:
            await probe.is_registered()
        except aiohuesyncbox.RequestError as err:
            raise ValueError(f"Hue Sync Box is not reachable: {err}") from err
        finally:
            await probe.close()

        self._temp = {"name": name, "host": host, "unique_id": unique_id, "port": port, "path": path}
        return self._button_form()

    async def _finish_pairing(self, input_values: dict[str, Any]) -> HueSyncConfig:
        if self._temp is None:
            raise ValueError("Pairing session expired. Restart setup.")
        if str(input_values.get("pair", "")).strip().upper() != "PAIR":
            raise ValueError("Enter PAIR after starting pairing and pressing the Sync Box button.")

        data = dict(self._temp)
        self._temp = None  # consume session immediately: no parallel/reused session
        api = aiohuesyncbox.HueSyncBox(data["host"], data["unique_id"], port=data["port"], path=data["path"])
        try:
            registration = None
            # Bounded foreground pairing loop: no orphan background task can survive setup.
            for _ in range(30):
                try:
                    registration = await api.register("Unfolded Circle", "Remote 3")
                    break
                except aiohuesyncbox.InvalidState:
                    await asyncio.sleep(1)
            if not registration:
                raise ValueError("Pairing timed out. Start pairing first, then press and briefly hold the Sync Box button until the LED lights up green once, and restart setup.")
            await api.initialize()
            actual_name = getattr(api.device, "name", "") or data["name"]
            return HueSyncConfig(
                identifier=f"hue_sync_{data['unique_id'].lower()}",
                name=actual_name,
                host=data["host"],
                unique_id=data["unique_id"],
                access_token=registration["access_token"],
                registration_id=registration["registration_id"],
                port=data["port"], path=data["path"], poll_interval=3,
            )
        except aiohuesyncbox.RequestError as err:
            raise ValueError(f"Hue Sync Box pairing failed: {err}") from err
        finally:
            await api.close()
