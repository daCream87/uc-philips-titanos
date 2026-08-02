# Philips Titan OS TV integration for Unfolded Circle Remote 3

Direct local-network driver for Philips JointSpace API 6.x / Titan OS televisions.

Tested protocol/model baseline: Philips 77OLED759/12, API 6.1.0, HTTPS port 1926, digest pairing.

## Functions
Power/Wake-on-LAN, volume, mute, channels, cursor/OK, Home, Back, Source, Guide, Settings, Info, Options, subtitles, Ambilight, playback, colour keys, digits, and dedicated app keys.

## Build
Push this repository to GitHub and run **Build Remote 3 package** under Actions. Download the generated `uc-intg-philips-titanos-...-aarch64.tar.gz` artifact and upload it in the Remote 3 Web Configurator under Integrations → Add → Install Custom.

## Setup on the remote
Enter TV IP, optional MAC address, and display name. Accept the pairing request on the TV and enter the displayed PIN in the setup dialog.

## Notes
Titan OS blocks `/applications` and `/sources` with HTTP 403 on the tested OLED759. Dedicated source/app key commands are used instead. The driver polls power, volume and mute every two seconds.
