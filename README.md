# Philips Titan OS TV for Unfolded Circle Remote 3

Direct local-network integration for Philips Titan OS TVs using JointSpace API 6.

## Tested TV
- Philips 77OLED759/12
- JointSpace API 6.1.0
- HTTPS / digest pairing
- Power state, volume and mute polling
- Direct IP key commands

## Setup
1. Install the compiled `.tar.gz` in the Remote 3 Web Configurator.
2. Start setup.
3. Enter TV IP, MAC address and name.
4. Enter the PIN shown on the TV.
5. Add the created Remote entity to an activity.

## Important
The setup flow is implemented with `ucapi-framework`, matching the architecture used by working Remote 3 community integrations.

## v0.5.2 pairing fix
- Uses the exact successful Windows `pairRequest` / `pairGrant` sequence.
- Verifies Digest credentials before configuration is saved.
- Keeps the PIN session alive after an invalid PIN instead of falling into a Retry loop.
- Removes unsupported physical channel-button enum mappings; channel controls remain on the UI page.


## v0.5.5
- Removed the immediate authenticated probe after `pairGrant`; Titan OS may not accept the new digest credentials instantly.
- Retry now clears stale pairing state so a new PIN can be requested.
- Added `RESTART_TV`, trying `/6/system/reboot` and `/6/system/restart`. Availability depends on firmware.


## v0.5.7 setup diagnostic
The first manual entry screen now uses the exact field structure of the
working Fire TV reference integration. No TV connection is attempted until
the user submits the IP-address form.


## v0.5.8 runtime startup fix

The Remote 3 log showed that the integration crashed before setup with:

`FileNotFoundError: /app/_internal/driver.json`

The driver now resolves the external manifest from the executable directory:

`/app/driver.json`

This matches the installed Remote 3 package layout and no longer depends on
PyInstaller's internal module directory.


## v0.6.0 hardened baseline

- Keeps UC Framework add/update/remove/reset/backup/restore behavior.
- Uses the exact Philips API 6 pairing call proven on Windows.
- Rejects the Remote 3 IP when entered as the TV IP.
- Tests Philips ports 1926/1925 before starting pairing.
- Prevents unhandled network errors from surfacing as generic error 500.
- Adds retries and explicit connectivity logging for every command.
- Keeps the TV restart command (`system/reboot`, then `system/restart`).
