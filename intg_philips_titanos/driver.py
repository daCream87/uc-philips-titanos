from ucapi_framework import BaseIntegrationDriver

from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.device import PhilipsDevice
from intg_philips_titanos.remote import PhilipsRemote

class PhilipsDriver(BaseIntegrationDriver[PhilipsDevice, PhilipsConfig]):
    def __init__(self):
        super().__init__(
            device_class=PhilipsDevice,
            entity_classes=[PhilipsRemote],
            driver_id="philips_titanos",
        )
