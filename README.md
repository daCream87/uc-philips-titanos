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


## v0.6.1
Fully asynchronous runtime transport with detailed URL, retry and exception logging. Raw TCP pre-check removed; setup now uses the actual Philips API discovery call.


## v0.6.2
Fixed the setup crash `NameError: socket is not defined` by restoring the required standard-library import. Added a CI source check to prevent this regression.


## v0.6.3 direct Philips pairing

- Removed `haphilipsjs` from the setup path.
- `/6/system`, `/6/pair/request` and `/6/pair/grant` are now called directly.
- Uses the same Philips HMAC and Digest pairing protocol as the successful desktop test.
- Tries HTTPS first and HTTP second for `/system`.
- Logs the exact URL, HTTP status, protocol and concrete exception type.
- Keeps UC add, update, remove, reset, backup and restore handling.


## v0.7.0 UI and key mapping refresh

- New grouped German touchscreen pages with symbolic labels.
- Physical media buttons mapped where supported by the installed UC API.
- Colour keys now map to Philips colour commands instead of app shortcuts.
- Settings uses `Options` instead of ignored `Adjust`.
- Added Record, Next and Previous commands.
- Channels opens live TV (`WatchTV`).
- Restart falls back to standby plus Wake-on-LAN when Titan OS rejects reboot endpoints with HTTP 400.
- Streaming app keys remain experimental because availability depends on TV firmware.


## v0.8.0 – Clean icon layout

- Replaced unreliable Unicode glyphs with packaged transparent PNG icons.
- All navigation arrows, Back and Settings now use one consistent white style.
- Removed Guide, Ambilight, Subtitle and TV Restart from the touchscreen pages.
- Removed the dangerous restart implementation entirely.
- Reworked the media page into a compact, uniform icon grid.
- Corrected physical button mapping to the button identifiers available in ucapi 0.7.
- Power now toggles based on the last known TV state.
- Offline power-on uses repeated Wake-on-LAN packets and waits up to ten seconds for the TV API.
- Bluetooth/IR fallback is not included because custom integrations currently have no supported
  API for transmitting arbitrary Bluetooth or built-in IR commands. Wake-on-LAN is the safe
  local-network fallback.
- App buttons try multiple known Titan OS key names, but availability remains firmware-dependent.


## v0.8.1 – Reliable text UI

- Fixes the black Steuerung and Medien pages caused by unresolved custom icon resources.
- Uses direct text widgets for all touch controls; no external UI resource lookup is required.
- Restores four white directional arrows (↑ ↓ ← →) and keeps SOURCE prominently available.
- Keeps the working Settings command.
- Keeps the working numeric keypad unchanged.
- Removes unverified Netflix, Prime Video, Disney+, YouTube and Joyn touch commands.
- Keeps CHANNELS / WatchTV, which is confirmed working on the tested 77OLED759/12.
- Restores the known-good v0.7.0 GitHub build workflow to avoid the v0.8.0 archive failure.


## v0.8.2 – UI cleanup & physical media buttons

- SOURCE is now shown only once, on the main control page.
- Removed the touchscreen PLAY/PAUSE control; separate PLAY and PAUSE remain.
- Settings uses the monochrome text-style gear `⚙︎` instead of the blue emoji gear.
- Colour keys are displayed as red, green, yellow and blue circles.
- Physical PLAY now sends the proven Philips `Play` command instead of `PlayPause`.
- Physical media mappings now use the standard Remote `send_cmd` structure from ucapi.
- Physical STOP, PREV, NEXT and RECORD use the same standard `send_cmd` structure.
- The numeric keypad remains unchanged.
- Apps page keeps only CHANNELS, the app-style function confirmed working on this TV.


## v0.8.3 – Page order cleanup

- Ziffern is now the second page directly after Steuerung.
- The separate Apps page has been removed completely.
- CHANNELS moved to the Medien page.
- Medien now contains PREV, REW, PLAY, FF, NEXT, PAUSE, STOP, REC and CHANNELS.
- SOURCE remains only once on the Steuerung page.
- Settings is shown as plain white text for reliable rendering.
- Numeric keypad remains unchanged.


## v0.8.4
Restored the four colour buttons as red, green, yellow and blue dots on the main control page.


## v0.8.5 – Configurator locale fix

- Normalized Configurator-facing names to locale dictionaries.
- Added both `de`/`en` and `de_DE`/`en_US` variants where relevant.
- Converted Remote entity display name and page titles from raw strings to locale objects.
- No changes to pairing, Philips communication, key mappings or page layout.
