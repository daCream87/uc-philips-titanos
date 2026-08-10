from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ucapi import StatusCodes
from ucapi.remote import Attributes, Features, Remote, States
from ucapi.ui import Buttons
from ucapi_framework import RemoteEntity

from intg_hue_sync_box.commands import SUPPORTED_COMMANDS
from intg_hue_sync_box.config import HueSyncConfig
from intg_hue_sync_box.device import HueSyncDevice

_LOG = logging.getLogger(__name__)


class HueSyncRemote(RemoteEntity):
    def __init__(self, device_config: HueSyncConfig, device: HueSyncDevice):
        self._device = device
        self._config = device_config
        super().__init__(
            f"remote.{device_config.identifier}",
            device_config.name,
            features=[Features.SEND_CMD, Features.ON_OFF, Features.TOGGLE],
            attributes={Attributes.STATE: States.UNKNOWN},
            simple_commands=SUPPORTED_COMMANDS,
            button_mapping=self._button_mapping(),
            ui_pages=self._ui_pages(),
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        state = self._device.state
        self.update({Attributes.STATE: States.ON if state.online and state.power else States.OFF})

    @staticmethod
    def _button(name: str): return getattr(Buttons, name, None)

    @staticmethod
    def _send_cmd(command: str) -> Dict[str, Any]:
        return {"cmd_id": "send_cmd", "params": {"command": command}}

    def _button_mapping(self) -> List[Dict]:
        # Physical Remote 3 mapping: only functions with a natural Sync Box meaning.
        candidates = [
            ("POWER", "POWER_TOGGLE"),
            ("DPAD_LEFT", "HDMI_PREVIOUS"),
            ("DPAD_RIGHT", "HDMI_NEXT"),
            ("DPAD_UP", "BRIGHTNESS_UP"),
            ("DPAD_DOWN", "BRIGHTNESS_DOWN"),
            ("DPAD_MIDDLE", "SYNC_TOGGLE"),
            ("PREV", "HDMI_PREVIOUS"),
            ("NEXT", "HDMI_NEXT"),
            ("PLAY", "SYNC_ON"),
            ("STOP", "SYNC_OFF"),
            ("MENU", "MODE_NEXT"),
        ]
        result = []
        for name, command in candidates:
            button = self._button(name)
            if button is not None:
                result.append({"button": button.value, "short_press": self._send_cmd(command), "long_press": None})
        return result

    @staticmethod
    def _text(text: str, x: int, y: int, command: str, width: int = 1, height: int = 1) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "type": "text",
            "location": {"x": x, "y": y},
            "text": text,
            "command": {"cmd_id": command},
        }
        if width != 1 or height != 1:
            item["size"] = {"width": width, "height": height}
        return item

    def _ui_pages(self) -> List[Dict[str, Any]]:
        # Native text controls only. Avoid custom touchscreen PNGs in v0.1.x.
        return [
            {
                "page_id": "control", "name": "Steuerung", "grid": {"width": 4, "height": 4},
                "items": [
                    self._text("POWER", 0, 0, "POWER_TOGGLE", 2),
                    self._text("SYNC", 2, 0, "SYNC_TOGGLE", 2),
                    self._text("HDMI 1", 0, 1, "HDMI_1", 2),
                    self._text("HDMI 2", 2, 1, "HDMI_2", 2),
                    self._text("HDMI 3", 0, 2, "HDMI_3", 2),
                    self._text("HDMI 4", 2, 2, "HDMI_4", 2),
                    self._text("← HDMI", 0, 3, "HDMI_PREVIOUS", 2),
                    self._text("HDMI →", 2, 3, "HDMI_NEXT", 2),
                ],
            },
            {
                "page_id": "sync", "name": "Sync", "grid": {"width": 4, "height": 5},
                "items": [
                    self._text("VIDEO", 0, 0, "MODE_VIDEO"),
                    self._text("GAME", 1, 0, "MODE_GAME"),
                    self._text("MUSIC", 2, 0, "MODE_MUSIC"),
                    self._text("MODE →", 3, 0, "MODE_NEXT"),
                    self._text("DEZENT", 0, 1, "INTENSITY_SUBTLE"),
                    self._text("MITTEL", 1, 1, "INTENSITY_MODERATE"),
                    self._text("HOCH", 2, 1, "INTENSITY_HIGH"),
                    self._text("INTENSIV", 3, 1, "INTENSITY_INTENSE"),
                    self._text("INT −", 0, 2, "INTENSITY_PREVIOUS", 2),
                    self._text("INT +", 2, 2, "INTENSITY_NEXT", 2),
                    self._text("HELL −", 0, 3, "BRIGHTNESS_DOWN", 2),
                    self._text("HELL +", 2, 3, "BRIGHTNESS_UP", 2),
                    self._text("SYNC EIN", 0, 4, "SYNC_ON", 2),
                    self._text("SYNC AUS", 2, 4, "SYNC_OFF", 2),
                ],
            },
        ]

    async def _handle_command(self, entity: Remote, cmd_id: str, params: Optional[Dict[str, Any]] = None) -> StatusCodes:
        try:
            if cmd_id == "on": cmd_id = "POWER_ON"
            elif cmd_id == "off": cmd_id = "POWER_OFF"
            elif cmd_id == "toggle": cmd_id = "POWER_TOGGLE"
            elif cmd_id == "send_cmd" and params and "command" in params:
                cmd_id = str(params["command"])
            return StatusCodes.OK if await self._device.send_command(cmd_id) else StatusCodes.BAD_REQUEST
        except Exception:
            _LOG.exception("Hue Sync Box command failed without escaping to UC API: %s", cmd_id)
            return StatusCodes.SERVER_ERROR
