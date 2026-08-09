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
        value = (
            States.ON
            if state.online and state.power not in ("STANDBY", "OFF")
            else States.OFF
        )
        self.update({Attributes.STATE: value})

    @staticmethod
    def _button(name: str):
        return getattr(Buttons, name, None)

    @staticmethod
    def _send_cmd(command: str) -> Dict[str, Any]:
        # Use the Remote entity's standard SEND_CMD command instead of mapping
        # physical keys directly to custom simple command ids. This mirrors the
        # official ucapi helper create_send_cmd().
        return {
            "cmd_id": "send_cmd",
            "params": {"command": command},
        }

    def _button_mapping(self) -> List[Dict]:
        # Remote 3 physical media keys are defined by ucapi as PLAY, STOP,
        # PREV, NEXT and RECORD. PLAY is deliberately mapped to the proven
        # Philips "Play" key instead of the non-working "PlayPause" key.
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
            ("PLAY", "PLAY"),
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
                        "short_press": self._send_cmd(command),
                        "long_press": None,
                    }
                )
        return result

    @staticmethod
    def _text(
        text: str,
        x: int,
        y: int,
        command: str,
        width: int = 1,
        height: int = 1,
    ) -> Dict[str, Any]:
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
                    self._text("POWER", 0, 0, "POWER_TOGGLE"),
                    self._text("HOME", 1, 0, "HOME"),
                    self._text("SOURCE", 2, 0, "SOURCE"),
                    # U+FE0E requests monochrome/text presentation instead of
                    # the blue emoji-style gear used by the previous build.
                    self._text("⚙︎", 3, 0, "SETTINGS"),

                    self._text("↑", 1, 1, "CURSOR_UP"),
                    self._text("BACK", 3, 1, "BACK"),

                    self._text("←", 0, 2, "CURSOR_LEFT"),
                    self._text("OK", 1, 2, "CURSOR_ENTER"),
                    self._text("→", 2, 2, "CURSOR_RIGHT"),
                    self._text("INFO", 3, 2, "INFO"),

                    self._text("↓", 1, 3, "CURSOR_DOWN"),
                    self._text("EXIT", 3, 3, "TV_EXIT"),

                    self._text("VOL −", 0, 4, "VOLUME_DOWN"),
                    self._text("MUTE", 1, 4, "MUTE"),
                    self._text("VOL +", 2, 4, "VOLUME_UP"),

                    self._text("CH −", 0, 5, "CHANNEL_DOWN"),
                    self._text("CH +", 3, 5, "CHANNEL_UP"),

                    # Emoji circles are rendered by the Remote itself, avoiding
                    # the broken custom PNG resource path from v0.8.0.
                    self._text("🔴", 0, 6, "RED"),
                    self._text("🟢", 1, 6, "GREEN"),
                    self._text("🟡", 2, 6, "YELLOW"),
                    self._text("🔵", 3, 6, "BLUE"),
                ],
            },
            {
                "page_id": "media",
                "name": "Medien",
                "grid": {"width": 5, "height": 2},
                "items": [
                    self._text("PREV", 0, 0, "PREVIOUS"),
                    self._text("REW", 1, 0, "REWIND"),
                    self._text("PLAY", 2, 0, "PLAY"),
                    self._text("FF", 3, 0, "FAST_FORWARD"),
                    self._text("NEXT", 4, 0, "NEXT"),

                    self._text("PAUSE", 1, 1, "PAUSE"),
                    self._text("STOP", 2, 1, "STOP"),
                    self._text("REC", 3, 1, "RECORD"),
                ],
            },
            {
                "page_id": "apps",
                "name": "Apps",
                "grid": {"width": 4, "height": 1},
                "items": [
                    self._text("CHANNELS", 1, 0, "CHANNELS_APP", 2),
                ],
            },
            {
                "page_id": "numbers",
                "name": "Ziffern",
                "grid": {"width": 3, "height": 4},
                "items": [
                    self._text(
                        str(number),
                        (number - 1) % 3,
                        (number - 1) // 3,
                        f"DIGIT_{number}",
                    )
                    for number in range(1, 10)
                ]
                + [self._text("0", 1, 3, "DIGIT_0")],
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
                return (
                    StatusCodes.OK
                    if await self._device.power_on()
                    else StatusCodes.BAD_REQUEST
                )
            if cmd_id == "off":
                return (
                    StatusCodes.OK
                    if await self._device.power_off()
                    else StatusCodes.BAD_REQUEST
                )
            if cmd_id == "toggle":
                return (
                    StatusCodes.OK
                    if await self._device.power_toggle()
                    else StatusCodes.BAD_REQUEST
                )
            if cmd_id == "send_cmd" and params and "command" in params:
                cmd_id = str(params["command"])

            return (
                StatusCodes.OK
                if await self._device.send_command(cmd_id)
                else StatusCodes.BAD_REQUEST
            )
        except Exception:
            _LOG.exception("Philips command failed: %s", cmd_id)
            return StatusCodes.SERVER_ERROR
