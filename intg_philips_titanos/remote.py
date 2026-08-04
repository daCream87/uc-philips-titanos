from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ucapi import StatusCodes
from ucapi.remote import Attributes, Features, Remote, States
from ucapi.ui import Buttons
from ucapi_framework import RemoteEntity

from intg_philips_titanos.commands import SUPPORTED_COMMANDS
from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.device import PhilipsDevice

_LOG = logging.getLogger(__name__)


class PhilipsRemote(RemoteEntity):
    def __init__(self, device_config: PhilipsConfig, device: PhilipsDevice):
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
        s = self._device.state
        state = States.ON if s.online and s.power != "STANDBY" else States.OFF
        self.update({Attributes.STATE: state})

    @staticmethod
    def _button(name: str):
        return getattr(Buttons, name, None)

    def _button_mapping(self) -> List[Dict]:
        candidates = [
            ("POWER", "POWER_OFF"), ("HOME", "HOME"), ("BACK", "BACK"),
            ("DPAD_UP", "CURSOR_UP"), ("DPAD_DOWN", "CURSOR_DOWN"),
            ("DPAD_LEFT", "CURSOR_LEFT"), ("DPAD_RIGHT", "CURSOR_RIGHT"),
            ("DPAD_MIDDLE", "CURSOR_ENTER"), ("VOLUME_UP", "VOLUME_UP"),
            ("VOLUME_DOWN", "VOLUME_DOWN"), ("MUTE", "MUTE"),
            ("CHANNEL_UP", "CHANNEL_UP"), ("CHANNEL_DOWN", "CHANNEL_DOWN"),
            ("PLAY_PAUSE", "PLAY_PAUSE"), ("PLAY", "PLAY"), ("PAUSE", "PAUSE"),
            ("STOP", "STOP"), ("RECORD", "RECORD"),
            ("FAST_FORWARD", "FAST_FORWARD"), ("REWIND", "REWIND"),
            ("NEXT", "NEXT"), ("PREVIOUS", "PREVIOUS"),
            ("MENU", "SETTINGS"), ("RED", "RED"), ("GREEN", "GREEN"),
            ("YELLOW", "YELLOW"), ("BLUE", "BLUE"),
        ]
        result = []
        for name, command in candidates:
            button = self._button(name)
            if button is not None:
                result.append({"button": button.value, "short_press": {"cmd_id": command}, "long_press": None})
        return result

    @staticmethod
    def _item(text: str, x: int, y: int, command: str, width: int = 1, height: int = 1) -> Dict[str, Any]:
        item = {"type": "text", "location": {"x": x, "y": y}, "text": text, "command": {"cmd_id": command}}
        if width != 1 or height != 1:
            item["size"] = {"width": width, "height": height}
        return item

    def _ui_pages(self) -> List[Dict[str, Any]]:
        return [
            {
                "page_id": "control", "name": "Steuerung", "grid": {"width": 4, "height": 7},
                "items": [
                    self._item("⏻", 0, 0, "POWER_OFF"), self._item("⌂", 1, 0, "HOME"),
                    self._item("SOURCE", 2, 0, "SOURCE"), self._item("⚙", 3, 0, "SETTINGS"),
                    self._item("▲", 1, 1, "CURSOR_UP"),
                    self._item("◀", 0, 2, "CURSOR_LEFT"), self._item("OK", 1, 2, "CURSOR_ENTER"),
                    self._item("▶", 2, 2, "CURSOR_RIGHT"), self._item("↩", 3, 2, "BACK"),
                    self._item("▼", 1, 3, "CURSOR_DOWN"), self._item("INFO", 3, 3, "INFO"),
                    self._item("VOL −", 0, 4, "VOLUME_DOWN"), self._item("MUTE", 1, 4, "MUTE"),
                    self._item("VOL +", 2, 4, "VOLUME_UP"), self._item("GUIDE", 3, 4, "GUIDE"),
                    self._item("CH −", 0, 5, "CHANNEL_DOWN"), self._item("TV / EXIT", 1, 5, "TV_EXIT", 2),
                    self._item("CH +", 3, 5, "CHANNEL_UP"),
                    self._item("ROT", 0, 6, "RED"), self._item("GRÜN", 1, 6, "GREEN"),
                    self._item("GELB", 2, 6, "YELLOW"), self._item("BLAU", 3, 6, "BLUE"),
                ],
            },
            {
                "page_id": "media", "name": "Medien", "grid": {"width": 5, "height": 4},
                "items": [
                    self._item("|◀", 0, 0, "PREVIOUS"), self._item("◀◀", 1, 0, "REWIND"),
                    self._item("▶ / Ⅱ", 2, 0, "PLAY_PAUSE"), self._item("▶▶", 3, 0, "FAST_FORWARD"),
                    self._item("▶|", 4, 0, "NEXT"),
                    self._item("▶", 0, 1, "PLAY"), self._item("Ⅱ", 1, 1, "PAUSE"),
                    self._item("■ STOP", 2, 1, "STOP"), self._item("● REC", 3, 1, "RECORD"),
                    self._item("SUB", 4, 1, "SUBTITLE"),
                    self._item("AMBILIGHT", 0, 2, "AMBILIGHT", 2),
                    self._item("TV NEUSTART", 2, 2, "RESTART_TV", 3),
                ],
            },
            {
                "page_id": "apps", "name": "Apps", "grid": {"width": 4, "height": 4},
                "items": [
                    self._item("NETFLIX", 0, 0, "NETFLIX", 2), self._item("PRIME VIDEO", 2, 0, "PRIME_VIDEO", 2),
                    self._item("DISNEY+", 0, 1, "DISNEY_PLUS", 2), self._item("YOUTUBE", 2, 1, "YOUTUBE", 2),
                    self._item("CHANNELS", 0, 2, "CHANNELS_APP", 2), self._item("JOYN", 2, 2, "JOYN", 2),
                    self._item("Hinweis: App-Tasten sind firmwareabhängig", 0, 3, "HOME", 4),
                ],
            },
            {
                "page_id": "numbers", "name": "Ziffern", "grid": {"width": 3, "height": 4},
                "items": [self._item(str(n), (n - 1) % 3, (n - 1) // 3, f"DIGIT_{n}") for n in range(1, 10)]
                + [self._item("0", 1, 3, "DIGIT_0")],
            },
        ]

    async def _handle_command(self, entity: Remote, cmd_id: str, params: Optional[Dict[str, Any]] = None) -> StatusCodes:
        try:
            if cmd_id == "on":
                return StatusCodes.OK if await self._device.power_on() else StatusCodes.BAD_REQUEST
            if cmd_id == "off":
                return StatusCodes.OK if await self._device.power_off() else StatusCodes.BAD_REQUEST
            if cmd_id == "toggle":
                ok = await (self._device.power_off() if self._device.state.online else self._device.power_on())
                return StatusCodes.OK if ok else StatusCodes.BAD_REQUEST
            if cmd_id == "send_cmd" and params and "command" in params:
                cmd_id = str(params["command"])
            return StatusCodes.OK if await self._device.send_command(cmd_id) else StatusCodes.BAD_REQUEST
        except Exception:
            _LOG.exception("Philips command failed: %s", cmd_id)
            return StatusCodes.SERVER_ERROR
