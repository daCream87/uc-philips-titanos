from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from ucapi import DeviceStates
from ucapi_framework import BaseConfigManager, get_config_path

from intg_philips_titanos.config import PhilipsConfig
from intg_philips_titanos.driver import PhilipsDriver
from intg_philips_titanos.setup_flow import PhilipsSetupFlow

__version__ = "0.8.3"
_LOG = logging.getLogger(__name__)


def _manifest_path() -> Path:
    """Return the external Remote 3 manifest path.

    In the installed PyInstaller onedir package:
      /app/driver
      /app/driver.json
      /app/_internal/...

    __file__ points into /app/_internal, so deriving the path from __file__
    incorrectly searches for /app/_internal/driver.json. The executable
    directory is the stable package root on Remote 3.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "driver.json"

    # Source/development execution.
    return Path(__file__).resolve().parent.parent / "driver.json"


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s",
    )
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    _LOG.info("Starting Philips Titan OS integration v%s", __version__)

    manifest = _manifest_path()
    if not manifest.is_file():
        raise FileNotFoundError(f"Remote 3 manifest not found: {manifest}")
    _LOG.info("Using manifest: %s", manifest)

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
    await driver.api.init(str(manifest), setup_handler)
    _LOG.info("UC API initialized and setup handler registered")

    await driver.register_all_device_instances(connect=False)

    if len(list(config_manager.all())):
        await driver.api.set_device_state(DeviceStates.CONNECTED)
    else:
        await driver.api.set_device_state(DeviceStates.DISCONNECTED)

    await asyncio.Future()
