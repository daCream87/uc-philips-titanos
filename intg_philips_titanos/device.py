
from __future__ import annotations
import logging
from ucapi_framework import PollingDevice
from intg_philips_titanos.client import PhilipsConnectionError, PhilipsJointSpaceClient, TvState
from intg_philips_titanos.commands import KEY_MAP
from intg_philips_titanos.config import PhilipsConfig
_LOG = logging.getLogger(__name__)

class PhilipsDevice(PollingDevice):
    def __init__(self, device_config: PhilipsConfig, **kwargs):
        super().__init__(device_config, poll_interval=device_config.poll_interval, **kwargs)
        self._config = device_config
        self._client = PhilipsJointSpaceClient(
            device_config.host, device_config.api_version, device_config.username,
            device_config.password, verify_tls=False,
            secured_transport=device_config.secured_transport)
        self._state = TvState()

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

    async def poll_device(self):
        self._state = await self._client.read_state()
        self.push_update()

    async def power_on(self):
        if not self._config.mac:
            _LOG.warning("[%s] Wake-on-LAN unavailable: no TV MAC configured", self.log_id)
            return False
        try:
            await self._client.wake_on_lan(self._config.mac)
            return True
        except Exception:
            _LOG.exception("[%s] Wake-on-LAN failed", self.log_id)
            return False

    async def power_off(self):
        return await self.send_command("POWER_OFF")

    async def restart_tv(self):
        try:
            endpoint = await self._client.restart_tv(self._config.mac)
            _LOG.info("[%s] TV restart requested via %s", self.log_id, endpoint)
            return True
        except Exception:
            _LOG.exception("[%s] TV restart command failed", self.log_id)
            return False

    async def send_command(self, command: str):
        if command == "RESTART_TV":
            return await self.restart_tv()
        key = KEY_MAP.get(command)
        if not key:
            _LOG.warning("[%s] Unknown command: %s", self.log_id, command)
            return False
        try:
            await self._client.send_key(key)
            _LOG.info("[%s] Command sent: %s -> %s", self.log_id, command, key)
            return True
        except PhilipsConnectionError:
            _LOG.exception("[%s] Network error sending %s", self.log_id, command)
            return False
        except Exception:
            _LOG.exception("[%s] Command failed: %s", self.log_id, command)
            return False

    async def set_volume(self, volume: int):
        try:
            await self._client.set_volume(volume, bool(self._state.muted))
            return True
        except Exception:
            _LOG.exception("[%s] Volume command failed", self.log_id)
            return False
