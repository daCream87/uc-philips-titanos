# Philips Hue Sync Box – Unfolded Circle Remote 3

Native local-network Custom Integration for Philips Hue Play HDMI Sync Box.

## v0.1.2

Built from the proven Remote 3 architecture of the Philips Titan OS integration and the communication model used by the supplied Home Assistant Hue Sync Box integration (`aiohuesyncbox==0.0.31`). Home Assistant is not required at runtime.

### v0.1.2 reconnect fix
- Recreates the complete `aiohuesyncbox.HueSyncBox` client after connection loss, preserving the stored access token and registration ID.
- Self-healing polling tries a hard reconnect after two consecutive network failures.
- Command connection failures trigger an immediate reconnect so a new pairing is not required after the Sync Box was powered off or disconnected from the network.
- Toggle/cycle commands are not blindly replayed after an ambiguous network failure, avoiding accidental double toggles.

### Controls
- Power on/off/toggle
- Sync on/off/toggle
- HDMI 1–4 and previous/next
- Video / Game / Music
- Intensity: subtle / moderate / high / intense + cycle
- Brightness +/-
- Two native text-button touchscreen pages
- Physical Remote 3 mapping

### Pairing
Enter the Sync Box IP address and Unique ID (C4...). The Unique ID may be left blank if local `_huesync._tcp.local.` discovery can resolve exactly one box at the entered IP. Then start the pairing step on Remote 3. Afterwards, press and briefly hold the physical button on the Sync Box until the LED lights up green once and finish the pairing step.

Credentials (`access_token` and `registration_id`) are stored in the integration configuration by the ucapi framework.

### Build
Push a `v*` tag or run the GitHub Actions workflow manually. The workflow creates the AArch64 `tar.gz` expected by Remote 3 with `driver.json` and `driver-logo.png` at archive root and the executable at `bin/driver`.
