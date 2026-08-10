from __future__ import annotations

import asyncio
import logging

import aiohuesyncbox
from ucapi_framework import PollingDevice

from intg_hue_sync_box.client import HueSyncClient, HueSyncState
from intg_hue_sync_box.config import HueSyncConfig

_LOG = logging.getLogger(__name__)


class HueSyncDevice(PollingDevice):
    MAX_CONSECUTIVE_ERRORS = 5
    RECONNECT_AFTER_ERRORS = 2

    def __init__(self, device_config: HueSyncConfig, **kwargs):
        super().__init__(device_config, poll_interval=device_config.poll_interval, **kwargs)
        self._config = device_config
        self._client = HueSyncClient(
            device_config.host,
            device_config.unique_id,
            device_config.access_token,
            device_config.port,
            device_config.path,
        )
        self._state = HueSyncState()
        self._consecutive_errors = 0
        self._command_lock = asyncio.Lock()
        self._reconnect_lock = asyncio.Lock()

    @property
    def identifier(self): return self._config.identifier
    @property
    def name(self): return self._config.name
    @property
    def address(self): return self._config.host
    @property
    def log_id(self): return f"{self.name} ({self.address})"
    @property
    def state(self): return self._state

    async def establish_connection(self):
        await self._client.start()
        await self.poll_device()
        return self._client

    async def disconnect(self):
        await self._client.close()
        await super().disconnect()

    async def _hard_reconnect(self) -> bool:
        """Recreate the Hue API/session without changing pairing credentials."""
        async with self._reconnect_lock:
            try:
                _LOG.info("[%s] Recreating Hue Sync Box connection", self.log_id)
                await asyncio.wait_for(self._client.reconnect(), timeout=12)
                self._state = await asyncio.wait_for(self._client.read_state(), timeout=6)
                self._consecutive_errors = 0
                self.push_update()
                _LOG.info("[%s] Hue Sync Box connection restored", self.log_id)
                return True
            except aiohuesyncbox.Unauthorized:
                _LOG.error("[%s] Reconnect failed: stored Hue authorization is invalid", self.log_id)
                raise
            except (aiohuesyncbox.RequestError, TimeoutError, asyncio.TimeoutError) as err:
                _LOG.debug("[%s] Reconnect attempt failed: %s", self.log_id, err)
                return False
            except Exception:
                _LOG.debug("[%s] Unexpected reconnect failure", self.log_id, exc_info=True)
                return False

    async def poll_device(self):
        try:
            self._state = await asyncio.wait_for(self._client.read_state(), timeout=6)
            if self._consecutive_errors:
                _LOG.info("[%s] Hue Sync Box reachable again", self.log_id)
            self._consecutive_errors = 0
            self.push_update()
        except aiohuesyncbox.Unauthorized:
            self._state.online = False
            self.push_update()
            _LOG.error("[%s] Hue Sync Box authorization is no longer valid", self.log_id)
            raise
        except (aiohuesyncbox.RequestError, TimeoutError, asyncio.TimeoutError) as err:
            self._consecutive_errors += 1
            _LOG.warning("[%s] Poll failed (%s/%s): %s", self.log_id, self._consecutive_errors, self.MAX_CONSECUTIVE_ERRORS, err)

            # Do not wait for a manual re-pair or integration restart. After two
            # consecutive network failures replace the entire aiohuesyncbox instance
            # and its aiohttp session, keeping the same stored access token.
            if self._consecutive_errors >= self.RECONNECT_AFTER_ERRORS:
                if await self._hard_reconnect():
                    return

            if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                self._state.online = False
                self.push_update()
                raise

    async def _refresh_after_command(self) -> None:
        try:
            await asyncio.sleep(0.15)
            self._state = await asyncio.wait_for(self._client.read_state(), timeout=6)
            self._consecutive_errors = 0
            self.push_update()
        except Exception:
            _LOG.debug("[%s] Immediate post-command refresh failed; polling will retry", self.log_id, exc_info=True)

    async def _execute_command(self, command: str) -> bool:
        if command == "POWER_TOGGLE":
            await self._client.set_execution(mode="powersave" if self._state.power else "passthrough")
        elif command == "POWER_ON": await self._client.set_execution(mode="passthrough")
        elif command == "POWER_OFF": await self._client.set_execution(mode="powersave")
        elif command == "SYNC_TOGGLE": await self._client.call_execution("toggle_sync_active")
        elif command == "SYNC_ON": await self._client.set_execution(sync_active=True)
        elif command == "SYNC_OFF": await self._client.set_execution(sync_active=False)
        elif command.startswith("HDMI_") and command[-1:] in "1234": await self._client.set_execution(hdmi_source=f"input{command[-1]}")
        elif command == "HDMI_PREVIOUS": await self._client.call_execution("cycle_hdmi_source", False)
        elif command == "HDMI_NEXT": await self._client.call_execution("cycle_hdmi_source", True)
        elif command == "MODE_VIDEO": await self._client.set_execution(mode="video")
        elif command == "MODE_GAME": await self._client.set_execution(mode="game")
        elif command == "MODE_MUSIC": await self._client.set_execution(mode="music")
        elif command == "MODE_PREVIOUS": await self._client.call_execution("cycle_sync_mode", False)
        elif command == "MODE_NEXT": await self._client.call_execution("cycle_sync_mode", True)
        elif command.startswith("INTENSITY_") and command not in ("INTENSITY_PREVIOUS", "INTENSITY_NEXT"):
            await self._client.call_execution("set_intensity", command.removeprefix("INTENSITY_").lower())
        elif command == "INTENSITY_PREVIOUS": await self._client.call_execution("cycle_intensity", False)
        elif command == "INTENSITY_NEXT": await self._client.call_execution("cycle_intensity", True)
        elif command == "BRIGHTNESS_DOWN": await self._client.call_execution("increment_brightness", -20)
        elif command == "BRIGHTNESS_UP": await self._client.call_execution("increment_brightness", 20)
        else:
            _LOG.warning("[%s] Unknown command: %s", self.log_id, command)
            return False
        return True

    async def send_command(self, command: str) -> bool:
        async with self._command_lock:
            try:
                if not await self._execute_command(command):
                    return False
                await self._refresh_after_command()
                return True
            except aiohuesyncbox.Unauthorized:
                _LOG.error("[%s] Command %s rejected: authorization invalid", self.log_id, command)
            except aiohuesyncbox.InvalidState as err:
                _LOG.warning("[%s] Command %s rejected by Sync Box state: %s", self.log_id, command, err)
            except (aiohuesyncbox.RequestError, TimeoutError, asyncio.TimeoutError) as err:
                _LOG.warning("[%s] Command %s hit a connection error: %s; forcing reconnect", self.log_id, command, err)
                # Recover the connection immediately so the next button press works.
                # We deliberately do not blindly repeat toggle/cycle commands because
                # a lost HTTP response could mean the box already applied the command.
                await self._hard_reconnect()
            except Exception:
                _LOG.exception("[%s] Unexpected Hue command failure: %s", self.log_id, command)
            return False

    async def unregister(self) -> None:
        try:
            await self._client.api.unregister(self._config.registration_id)
        except Exception:
            _LOG.info("[%s] Could not unregister from Sync Box; removing local config anyway", self.log_id, exc_info=True)
