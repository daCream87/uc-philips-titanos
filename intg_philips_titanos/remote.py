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

    def _button_mapping(self) -> List[Dict]:
        rows = [
            (Buttons.POWER, "POWER_OFF"),
            (Buttons.HOME, "HOME"),
            (Buttons.BACK, "BACK"),
            (Buttons.DPAD_UP, "CURSOR_UP"),
            (Buttons.DPAD_DOWN, "CURSOR_DOWN"),
            (Buttons.DPAD_LEFT, "CURSOR_LEFT"),
            (Buttons.DPAD_RIGHT, "CURSOR_RIGHT"),
            (Buttons.DPAD_MIDDLE, "CURSOR_ENTER"),
            (Buttons.VOLUME_UP, "VOLUME_UP"),
            (Buttons.VOLUME_DOWN, "VOLUME_DOWN"),
            (Buttons.MUTE, "MUTE"),
            (Buttons.RED, "NETFLIX"),
            (Buttons.GREEN, "PRIME_VIDEO"),
            (Buttons.YELLOW, "DISNEY_PLUS"),
            (Buttons.BLUE, "YOUTUBE"),
        ]
        return [
            {
                "button": button.value,
                "short_press": {"cmd_id": command},
                "long_press": None,
            }
            for button, command in rows
        ]

    def _ui_pages(self) -> List[Dict[str, Any]]:
        return [
            {
                "page_id": "navigation",
                "name": "TV",
                "grid": {"width": 4, "height": 6},
                "items": [
                    self._item("Source", 0, 0, "SOURCE"),
                    self._item("Guide", 1, 0, "GUIDE"),
                    self._item("Info", 2, 0, "INFO"),
                    self._item("Settings", 3, 0, "SETTINGS"),
                    self._item("UP", 1, 1, "CURSOR_UP"),
                    self._item("LEFT", 0, 2, "CURSOR_LEFT"),
                    self._item("OK", 1, 2, "CURSOR_ENTER"),
                    self._item("RIGHT", 2, 2, "CURSOR_RIGHT"),
                    self._item("BACK", 3, 2, "BACK"),
                    self._item("DOWN", 1, 3, "CURSOR_DOWN"),
                    self._item("HOME", 3, 3, "HOME"),
                    self._item("VOL-", 0, 4, "VOLUME_DOWN"),
                    self._item("MUTE", 1, 4, "MUTE"),
                    self._item("VOL+", 2, 4, "VOLUME_UP"),
                    self._item("CH-", 0, 5, "CHANNEL_DOWN"),
                    self._item("TV/Exit", 1, 5, "TV_EXIT"),
                    self._item("CH+", 2, 5, "CHANNEL_UP"),
                    self._item("Power", 3, 5, "POWER_OFF"),
                ],
            },
            {
                "page_id": "apps",
                "name": "Apps",
                "grid": {"width": 4, "height": 6},
                "items": [
                    self._item("Netflix", 0, 0, "NETFLIX", 2),
                    self._item("Prime Video", 2, 0, "PRIME_VIDEO", 2),
                    self._item("Disney+", 0, 1, "DISNEY_PLUS", 2),
                    self._item("YouTube", 2, 1, "YOUTUBE", 2),
                    self._item("Channels", 0, 2, "CHANNELS_APP", 2),
                    self._item("Joyn", 2, 2, "JOYN", 2),
                    self._item("Ambilight", 0, 4, "AMBILIGHT", 2),
                    self._item("Subtitle", 2, 4, "SUBTITLE", 2),
                ],
            },
            {
                "page_id": "media",
                "name": "Media",
                "grid": {"width": 4, "height": 5},
                "items": [
                    self._item("<<", 0, 0, "REWIND"),
                    self._item("Play/Pause", 1, 0, "PLAY_PAUSE", 2),
                    self._item(">>", 3, 0, "FAST_FORWARD"),
                    self._item("Stop", 1, 1, "STOP", 2),
                    self._item("TV Restart", 0, 2, "RESTART_TV", 2),
                    self._item("Subtitle", 2, 2, "SUBTITLE", 2),
                    self._item("Red", 0, 4, "RED"),
                    self._item("Green", 1, 4, "GREEN"),
                    self._item("Yellow", 2, 4, "YELLOW"),
                    self._item("Blue", 3, 4, "BLUE"),
                ],
            },
            {
                "page_id": "numbers",
                "name": "Numbers",
                "grid": {"width": 3, "height": 4},
                "items": [
                    self._item(str(n), (n-1) % 3, (n-1) // 3, f"DIGIT_{n}")
                    for n in range(1, 10)
                ] + [self._item("0", 1, 3, "DIGIT_0")],
            },
        ]

    @staticmethod
    def _item(text: str, x: int, y: int, command: str, width: int = 1) -> Dict[str, Any]:
        item = {
            "type": "text",
            "location": {"x": x, "y": y},
            "text": text,
            "command": {"cmd_id": command},
        }
        if width != 1:
            item["size"] = {"width": width, "height": 1}
        return item

    async def _handle_command(
        self,
        entity: Remote,
        cmd_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> StatusCodes:
        try:
            if cmd_id == "on":
                ok = await self._device.power_on()
                return StatusCodes.OK if ok else StatusCodes.BAD_REQUEST
            if cmd_id == "off":
                ok = await self._device.power_off()
                return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
            if cmd_id == "toggle":
                if self._device.state.online:
                    ok = await self._device.power_off()
                else:
                    ok = await self._device.power_on()
                return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
            if cmd_id == "send_cmd" and params and "command" in params:
                cmd_id = str(params["command"])
            ok = await self._device.send_command(cmd_id)
            return StatusCodes.OK if ok else StatusCodes.BAD_REQUEST
        except Exception:
            _LOG.exception("Philips command failed: %s", cmd_id)
            return StatusCodes.SERVER_ERROR
