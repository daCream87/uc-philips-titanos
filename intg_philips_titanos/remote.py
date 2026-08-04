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
        state = self._device.state
        value = States.ON if state.online and state.power not in ("STANDBY", "OFF") else States.OFF
        self.update({Attributes.STATE: value})

    @staticmethod
    def _button(name: str):
        return getattr(Buttons, name, None)

    def _button_mapping(self) -> List[Dict]:
        # Only map physical button identifiers that exist in ucapi 0.7.
        candidates = [
            ("POWER", "POWER_TOGGLE"),
            ("HOME", "HOME"),
            ("BACK", "BACK"),
            ("DPAD_UP", "CURSOR_UP"),
            ("DPAD_DOWN", "CURSOR_DOWN"),
            ("DPAD_LEFT", "CURSOR_LEFT"),
            ("DPAD_RIGHT", "CURSOR_RIGHT"),
            ("DPAD_MIDDLE", "CURSOR_ENTER"),
            ("VOLUME_UP", "VOLUME_UP"),
            ("VOLUME_DOWN", "VOLUME_DOWN"),
            ("MUTE", "MUTE"),
            ("CHANNEL_UP", "CHANNEL_UP"),
            ("CHANNEL_DOWN", "CHANNEL_DOWN"),
            ("PREV", "PREVIOUS"),
            ("PLAY", "PLAY_PAUSE"),
            ("NEXT", "NEXT"),
            ("STOP", "STOP"),
            ("RECORD", "RECORD"),
            ("MENU", "SETTINGS"),
            ("RED", "RED"),
            ("GREEN", "GREEN"),
            ("YELLOW", "YELLOW"),
            ("BLUE", "BLUE"),
        ]
        result = []
        for name, command in candidates:
            button = self._button(name)
            if button is not None:
                result.append(
                    {
                        "button": button.value,
                        "short_press": {"cmd_id": command},
                        "long_press": None,
                    }
                )
        return result

    @staticmethod
    def _icon(icon: str, x: int, y: int, command: str, width: int = 1, height: int = 1) -> Dict[str, Any]:
        item = {
            "type": "icon",
            "location": {"x": x, "y": y},
            "icon": f"custom:{icon}",
            "command": {"cmd_id": command},
        }
        if width != 1 or height != 1:
            item["size"] = {"width": width, "height": height}
        return item

    @staticmethod
    def _text(text: str, x: int, y: int, command: str, width: int = 1, height: int = 1) -> Dict[str, Any]:
        item = {
            "type": "text",
            "location": {"x": x, "y": y},
            "text": text,
            "command": {"cmd_id": command},
        }
        if width != 1 or height != 1:
            item["size"] = {"width": width, "height": height}
        return item

    def _ui_pages(self) -> List[Dict[str, Any]]:
        return [
            {
                "page_id": "control",
                "name": "Steuerung",
                "grid": {"width": 4, "height": 7},
                "items": [
                    self._icon("ui-power.png", 0, 0, "POWER_TOGGLE"),
                    self._icon("ui-home.png", 1, 0, "HOME"),
                    self._icon("ui-source.png", 2, 0, "SOURCE"),
                    self._icon("ui-settings.png", 3, 0, "SETTINGS"),

                    self._icon("ui-up.png", 1, 1, "CURSOR_UP"),
                    self._icon("ui-back.png", 3, 1, "BACK"),

                    self._icon("ui-left.png", 0, 2, "CURSOR_LEFT"),
                    self._icon("ui-ok.png", 1, 2, "CURSOR_ENTER"),
                    self._icon("ui-right.png", 2, 2, "CURSOR_RIGHT"),
                    self._icon("ui-info.png", 3, 2, "INFO"),

                    self._icon("ui-down.png", 1, 3, "CURSOR_DOWN"),
                    self._icon("ui-exit.png", 3, 3, "TV_EXIT"),

                    self._icon("ui-vol-minus.png", 0, 4, "VOLUME_DOWN"),
                    self._icon("ui-mute.png", 1, 4, "MUTE"),
                    self._icon("ui-vol-plus.png", 2, 4, "VOLUME_UP"),

                    self._icon("ui-ch-minus.png", 0, 5, "CHANNEL_DOWN"),
                    self._icon("ui-ch-plus.png", 3, 5, "CHANNEL_UP"),

                    self._icon("ui-red.png", 0, 6, "RED"),
                    self._icon("ui-green.png", 1, 6, "GREEN"),
                    self._icon("ui-yellow.png", 2, 6, "YELLOW"),
                    self._icon("ui-blue.png", 3, 6, "BLUE"),
                ],
            },
            {
                "page_id": "media",
                "name": "Medien",
                "grid": {"width": 5, "height": 3},
                "items": [
                    self._icon("ui-previous.png", 0, 0, "PREVIOUS"),
                    self._icon("ui-rewind.png", 1, 0, "REWIND"),
                    self._icon("ui-playpause.png", 2, 0, "PLAY_PAUSE"),
                    self._icon("ui-fastforward.png", 3, 0, "FAST_FORWARD"),
                    self._icon("ui-next.png", 4, 0, "NEXT"),

                    self._icon("ui-play.png", 0, 1, "PLAY"),
                    self._icon("ui-pause.png", 1, 1, "PAUSE"),
                    self._icon("ui-stop.png", 2, 1, "STOP"),
                    self._icon("ui-record.png", 3, 1, "RECORD"),
                ],
            },
            {
                "page_id": "apps",
                "name": "Apps",
                "grid": {"width": 4, "height": 3},
                "items": [
                    self._text("NETFLIX", 0, 0, "NETFLIX", 2),
                    self._text("PRIME VIDEO", 2, 0, "PRIME_VIDEO", 2),
                    self._text("DISNEY+", 0, 1, "DISNEY_PLUS", 2),
                    self._text("YOUTUBE", 2, 1, "YOUTUBE", 2),
                    self._text("CHANNELS", 0, 2, "CHANNELS_APP", 2),
                    self._text("JOYN", 2, 2, "JOYN", 2),
                ],
            },
            {
                "page_id": "numbers",
                "name": "Ziffern",
                "grid": {"width": 3, "height": 4},
                "items": [
                    self._text(str(number), (number - 1) % 3, (number - 1) // 3, f"DIGIT_{number}")
                    for number in range(1, 10)
                ] + [self._text("0", 1, 3, "DIGIT_0")],
            },
        ]

    async def _handle_command(
        self,
        entity: Remote,
        cmd_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> StatusCodes:
        try:
            if cmd_id == "on":
                return StatusCodes.OK if await self._device.power_on() else StatusCodes.BAD_REQUEST
            if cmd_id == "off":
                return StatusCodes.OK if await self._device.power_off() else StatusCodes.BAD_REQUEST
            if cmd_id == "toggle":
                return StatusCodes.OK if await self._device.power_toggle() else StatusCodes.BAD_REQUEST
            if cmd_id == "send_cmd" and params and "command" in params:
                cmd_id = str(params["command"])
            return StatusCodes.OK if await self._device.send_command(cmd_id) else StatusCodes.BAD_REQUEST
        except Exception:
            _LOG.exception("Philips command failed: %s", cmd_id)
            return StatusCodes.SERVER_ERROR
