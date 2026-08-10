import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "driver.json").read_text(encoding="utf-8"))
assert manifest["driver_id"] == "hue_sync_box"
assert manifest["version"] == "0.1.2"
assert manifest["min_core_api"] == "0.22.0"

for path in (ROOT / "intg_hue_sync_box").glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

remote = (ROOT / "intg_hue_sync_box" / "remote.py").read_text(encoding="utf-8")
for command in ("POWER_TOGGLE", "SYNC_TOGGLE", "HDMI_1", "HDMI_4", "MODE_VIDEO", "MODE_GAME", "MODE_MUSIC", "BRIGHTNESS_UP"):
    assert command in remote
assert "custom:" not in remote

setup = (ROOT / "intg_hue_sync_box" / "setup_flow.py").read_text(encoding="utf-8")
assert 'api.register("Unfolded Circle", "Remote 3")' in setup
assert "for _ in range(30)" in setup
assert "asyncio.create_task" not in setup

client = (ROOT / "intg_hue_sync_box" / "client.py").read_text(encoding="utf-8")
assert "aiohuesyncbox.HueSyncBox" in client
assert "set_group_active" in client

workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
assert "--platform=aarch64" in workflow
assert "--collect-all aiohuesyncbox" in workflow
assert "artifacts/bin/driver" in workflow
print("source validation OK")
