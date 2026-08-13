import logging

from ucapi_framework import BaseIntegrationDriver

from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.device import PhilipsDevice
from intg_philips_titanos.remote import PhilipsRemote

_LOG = logging.getLogger(__name__)

class PhilipsDriver(BaseIntegrationDriver[PhilipsDevice, PhilipsConfig]):
    def __init__(self):
        super().__init__(
            device_class=PhilipsDevice,
            entity_classes=[PhilipsRemote],
            driver_id="philips_titanos",
        )

    async def on_r2_enter_standby(self) -> None:
        """Keep the device connection alive but reduce background polling.

        The framework normally disconnects devices on display standby. We keep
        the existing connection/session to avoid wake reconnect problems, while
        increasing the polling interval to reduce LAN traffic and background work.
        """
        _LOG.debug("Enter standby: keeping connection alive, poll interval -> 15s")
        for device in self._device_instances.values():
            device._poll_interval = 15

    async def on_r2_exit_standby(self) -> None:
        """Restore the normal polling interval without reconnecting the device."""
        _LOG.debug("Exit standby: connection kept alive, poll interval -> 3s")
        for device in self._device_instances.values():
            device._poll_interval = 3
