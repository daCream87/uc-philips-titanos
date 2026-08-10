from ucapi_framework import BaseIntegrationDriver

from intg_hue_sync_box.config import HueSyncConfig
from intg_hue_sync_box.device import HueSyncDevice
from intg_hue_sync_box.remote import HueSyncRemote


class HueSyncDriver(BaseIntegrationDriver[HueSyncDevice, HueSyncConfig]):
    def __init__(self):
        super().__init__(device_class=HueSyncDevice, entity_classes=[HueSyncRemote], driver_id="hue_sync_box")
