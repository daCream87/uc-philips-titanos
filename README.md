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
