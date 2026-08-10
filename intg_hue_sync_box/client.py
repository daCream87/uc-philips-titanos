from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import aiohuesyncbox

_LOG = logging.getLogger(__name__)


@dataclass
class HueSyncState:
    online: bool = False
    power: bool = False
    sync_active: bool = False
    mode: str = "unknown"
    hdmi_source: str = "unknown"
    hdmi_name: str = ""
    brightness_api: int = 100
    intensity: str = "unknown"
    input_names: dict[str, str] = field(default_factory=dict)

    @property
    def brightness_percent(self) -> int:
        # Same linear conversion used by the supplied Home Assistant integration:
        # HA 1..100 <-> Sync Box 0..200.
        return max(1, min(100, round(((self.brightness_api * 99) / 200) + 1)))


class HueSyncClient:
    """Hue Sync Box API wrapper with a hard reconnect path.

    aiohuesyncbox keeps its aiohttp ClientSession object after close(). Its request()
    method intentionally returns when that session is closed instead of creating a
    replacement session. Therefore a device/network outage followed by a framework
    disconnect can otherwise leave the integration permanently attached to a closed
    session. Rebuilding HueSyncBox preserves the stored registration credentials while
    guaranteeing a fresh TCP/TLS session.
    """

    def __init__(self, host: str, unique_id: str, access_token: str, port: int = 443, path: str = "/api"):
        self._host = host
        self._unique_id = unique_id
        self._access_token = access_token
        self._port = port
        self._path = path
        self._api = self._create_api()

    def _create_api(self):
        return aiohuesyncbox.HueSyncBox(
            self._host,
            self._unique_id,
            self._access_token,
            self._port,
            self._path,
        )

    @property
    def api(self):
        return self._api

    async def start(self) -> None:
        # Always create a fresh API object when (re-)establishing a framework
        # connection. This is safe on first start and fixes closed-session reuse.
        await self.reconnect()

    async def reconnect(self) -> None:
        old_api = self._api
        try:
            await old_api.close()
        except Exception:
            _LOG.debug("Ignoring error while closing stale Hue Sync Box session", exc_info=True)

        self._api = self._create_api()
        try:
            await self._api.initialize()
        except Exception:
            # Do not leave a half-open replacement around. The next reconnect attempt
            # will get another completely fresh API/session object.
            try:
                await self._api.close()
            except Exception:
                pass
            raise

    async def close(self) -> None:
        await self._api.close()

    async def read_state(self) -> HueSyncState:
        await self._api.update()
        execution = self._api.execution
        input_names: dict[str, str] = {}
        for input_id in ("input1", "input2", "input3", "input4"):
            input_obj = getattr(self._api.hdmi, input_id, None)
            input_names[input_id] = getattr(input_obj, "name", input_id) if input_obj else input_id
        current_name = input_names.get(execution.hdmi_source, execution.hdmi_source)
        mode_for_intensity = execution.mode if execution.mode in ("video", "game", "music") else execution.last_sync_mode
        intensity = "unknown"
        if mode_for_intensity in ("video", "game", "music"):
            intensity = getattr(getattr(execution, mode_for_intensity), "intensity", "unknown")
        return HueSyncState(
            online=True,
            power=(str(execution.mode) != "powersave"),
            sync_active=bool(execution.sync_active),
            mode=str(execution.mode),
            hdmi_source=str(execution.hdmi_source),
            hdmi_name=str(current_name),
            brightness_api=int(execution.brightness),
            intensity=str(intensity),
            input_names=input_names,
        )

    async def _retry_invalid_state(self, action: Callable[[], Awaitable[Any]]) -> None:
        try:
            await action()
            return
        except aiohuesyncbox.InvalidState:
            # Match the supplied Home Assistant integration: another application may
            # own the active Entertainment Area. Stop that stream once and retry once.
            for group in self._api.hue.groups:
                if getattr(group, "active", False):
                    _LOG.info("Stopping active Hue stream for area %s before retry", getattr(group, "name", getattr(group, "id", "?")))
                    await self._api.hue.set_group_active(group.id, active=False)
                    await action()
                    return
            raise

    async def set_execution(self, **kwargs: Any) -> None:
        await self._retry_invalid_state(lambda: self._api.execution.set_state(**kwargs))

    async def call_execution(self, method: str, *args: Any, **kwargs: Any) -> None:
        fn = getattr(self._api.execution, method)
        await self._retry_invalid_state(lambda: fn(*args, **kwargs))
