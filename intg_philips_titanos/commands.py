# Philips JointSpace input keys.
# The 77OLED759/12 implements only a subset of vendor-specific keys.

KEY_CANDIDATES = {
    "POWER_OFF": ["Standby"],
    "BACK": ["Back"],
    "HOME": ["Home"],
    "SETTINGS": ["Options"],
    "INFO": ["Info"],
    "TV_EXIT": ["WatchTV"],
    "SOURCE": ["Source"],
    # v0.9.7 experimental direct HDMI key candidates. Titan OS firmware
    # differs from Android/JointSpace models, so each command tries common
    # vendor spellings in order without removing the proven SOURCE command.
    "HDMI_1": ["Hdmi1", "HDMI1", "SourceHdmi1", "SourceHDMI1"],
    "HDMI_2": ["Hdmi2", "HDMI2", "SourceHdmi2", "SourceHDMI2"],
    "HDMI_3": ["Hdmi3", "HDMI3", "SourceHdmi3", "SourceHDMI3"],
    "HDMI_4": ["Hdmi4", "HDMI4", "SourceHdmi4", "SourceHDMI4"],

    # v0.9.12 discovery command. Runs a controlled matrix of source tests
    # through the already paired Remote 3 connection and logs every result.
    "HDMI_DISCOVERY": ["__DISCOVERY__"],
    "CURSOR_UP": ["CursorUp"],
    "CURSOR_DOWN": ["CursorDown"],
    "CURSOR_LEFT": ["CursorLeft"],
    "CURSOR_RIGHT": ["CursorRight"],
    "CURSOR_ENTER": ["Confirm"],
    "VOLUME_UP": ["VolumeUp"],
    "VOLUME_DOWN": ["VolumeDown"],
    "MUTE": ["Mute"],
    "CHANNEL_UP": ["ChannelStepUp"],
    "CHANNEL_DOWN": ["ChannelStepDown"],
    "RED": ["RedColour"],
    "GREEN": ["GreenColour"],
    "YELLOW": ["YellowColour"],
    "BLUE": ["BlueColour"],
    "PLAY_PAUSE": ["PlayPause", "Play"],
    "PLAY": ["Play"],
    "PAUSE": ["Pause"],
    "STOP": ["Stop"],
    "REWIND": ["Rewind"],
    "FAST_FORWARD": ["FastForward"],
    "RECORD": ["Record"],
    "NEXT": ["Next"],
    "PREVIOUS": ["Previous"],
    "DIGIT_0": ["Digit0"],
    "DIGIT_1": ["Digit1"],
    "DIGIT_2": ["Digit2"],
    "DIGIT_3": ["Digit3"],
    "DIGIT_4": ["Digit4"],
    "DIGIT_5": ["Digit5"],
    "DIGIT_6": ["Digit6"],
    "DIGIT_7": ["Digit7"],
    "DIGIT_8": ["Digit8"],
    "DIGIT_9": ["Digit9"],

    # Experimental app buttons: different Titan OS firmware versions use
    # different key names. The driver tries the candidates in order.
    "CHANNELS_APP": ["WatchTV", "Channels"],
}

# Compatibility for existing imports.
KEY_MAP = {command: keys[0] for command, keys in KEY_CANDIDATES.items()}
SUPPORTED_COMMANDS = list(KEY_CANDIDATES) + ["POWER_TOGGLE"]
