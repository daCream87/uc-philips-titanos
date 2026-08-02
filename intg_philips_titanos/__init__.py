from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from ucapi import DeviceStates
from ucapi_framework import BaseConfigManager, get_config_path

from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.driver import PhilipsDriver
from intg_philips_titanos.setup_flow import PhilipsSetupFlow

try:
    with open(Path(__file__).parent.parent / "driver.json", "r", encoding="utf-8") as file:
        __version__ = json.load(file).get("version", "0.0.0")
except Exception:
    __version__ = "0.0.0"

_LOG = logging.getLogger(__name__)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s",
    )
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    _LOG.info("Starting Philips Titan OS integration v%s", __version__)

    driver = PhilipsDriver()
    config_path = get_config_path(driver.api.config_dir_path or "")
    config_manager = BaseConfigManager(
        config_path,
        add_handler=driver.on_device_added,
        remove_handler=driver.on_device_removed,
        config_class=PhilipsConfig,
    )
    driver.config_manager = config_manager

    setup_handler = PhilipsSetupFlow.create_handler(driver)
    manifest = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "driver.json"))
    await driver.api.init(manifest, setup_handler)
    await driver.register_all_device_instances(connect=False)

    if len(list(config_manager.all())):
        await driver.api.set_device_state(DeviceStates.CONNECTED)
    else:
        await driver.api.set_device_state(DeviceStates.DISCONNECTED)

    await asyncio.Future()
