from __future__ import annotations

import asyncio
import logging

from ucapi_framework import PollingDevice

from intg_philips_titanos.client import PhilipsConnectionError, PhilipsJointSpaceClient, TvState
from intg_philips_titanos.commands import KEY_CANDIDATES
from intg_philips_titanos.config import PhilipsConfig

_LOG = logging.getLogger(__name__)


class PhilipsDevice(PollingDevice):
    def __init__(self, device_config: PhilipsConfig, **kwargs):
        super().__init__(device_config, poll_interval=device_config.poll_interval, **kwargs)
        self._config = device_config
        self._client = PhilipsJointSpaceClient(
            device_config.host,
            device_config.api_version,
            device_config.username,
            device_config.password,
            verify_tls=False,
            secured_transport=device_config.secured_transport,
        )
        self._state = TvState()

    @property
    def identifier(self):
        return self._config.identifier

    @property
    def name(self):
        return self._config.name

    @property
    def address(self):
        return self._config.host

    @property
    def log_id(self):
        return f"{self.name} ({self.address})"

    @property
    def state(self):
        return self._state

    async def establish_connection(self):
        await self._client.start()
        await self.poll_device()
        return self._client

    async def disconnect(self):
        await self._client.close()
        await super().disconnect()

    async def poll_device(self):
        self._state = await self._client.read_state()
        self.push_update()

    async def power_on(self) -> bool:
        if not self._config.mac:
            _LOG.warning("[%s] Wake-on-LAN unavailable: no TV MAC configured", self.log_id)
            return False

        try:
            # Send multiple WOL packets because the TV network interface may
            # need a moment to wake from deep standby.
            for delay in (0, 2, 5):
                if delay:
                    await asyncio.sleep(delay)
                await self._client.wake_on_lan(self._config.mac)

            # Wait up to ten seconds for JointSpace to become available.
            for _ in range(10):
                await asyncio.sleep(1)
                state = await self._client.read_state()
                if state.online:
                    self._state = state
                    self.push_update()
                    _LOG.info("[%s] TV woke successfully through Wake-on-LAN", self.log_id)
                    return True

            # WOL was sent successfully even if the API is slower to return.
            _LOG.info("[%s] Wake-on-LAN sent; TV API not online after ten seconds", self.log_id)
            return True
        except Exception:
            _LOG.exception("[%s] Wake-on-LAN failed", self.log_id)
            return False

    async def power_off(self) -> bool:
        return await self.send_command("POWER_OFF")

    async def power_toggle(self) -> bool:
        # Use the last known state. If the TV is unreachable/offline, wake it.
        if self._state.online and self._state.power not in ("STANDBY", "OFF"):
            return await self.power_off()
        return await self.power_on()

    async def send_command(self, command: str) -> bool:
        if command == "POWER_TOGGLE":
            return await self.power_toggle()
        if command == "POWER_OFF":
            # Avoid recursion through power_off(): send the Standby key directly,
            # then publish OFF immediately once accepted.
            keys = KEY_CANDIDATES.get(command)
            if not keys:
                return False
            last_error = None
            for key in keys:
                try:
                    await self._client.send_key(key)
                    _LOG.info("[%s] Command sent: %s -> %s", self.log_id, command, key)
                    self._state.power = "STANDBY"
                    self._state.online = False
                    self.push_update()
                    _LOG.info("[%s] Standby accepted; power state updated to OFF immediately", self.log_id)
                    return True
                except Exception as err:
                    last_error = err
                    _LOG.debug("[%s] Candidate key failed: %s -> %s: %s", self.log_id, command, key, err)
            if isinstance(last_error, PhilipsConnectionError):
                _LOG.error("[%s] Network error sending %s: %s", self.log_id, command, last_error)
            else:
                _LOG.error("[%s] All key candidates failed for %s: %s", self.log_id, command, last_error)
            return False

        keys = KEY_CANDIDATES.get(command)
        if not keys:
            _LOG.warning("[%s] Unknown command: %s", self.log_id, command)
            return False

        last_error = None
        for key in keys:
            try:
                await self._client.send_key(key)
                _LOG.info("[%s] Command sent: %s -> %s", self.log_id, command, key)
                return True
            except Exception as err:
                last_error = err
                _LOG.debug(
                    "[%s] Candidate key failed: %s -> %s: %s",
                    self.log_id,
                    command,
                    key,
                    err,
                )

        if isinstance(last_error, PhilipsConnectionError):
            _LOG.exception("[%s] Network error sending %s", self.log_id, command)
        else:
            _LOG.error("[%s] All key candidates failed for %s: %s", self.log_id, command, last_error)
        return False

    async def set_volume(self, volume: int):
        try:
            await self._client.set_volume(volume, bool(self._state.muted))
            return True
        except Exception:
            _LOG.exception("[%s] Volume command failed", self.log_id)
            return False
