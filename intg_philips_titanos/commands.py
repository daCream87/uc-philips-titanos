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
    # v0.9.13 deterministic HDMI selection. These commands are intercepted
    # by PhilipsDevice and executed as Source-menu navigation macros.
    # The placeholders keep the commands available as Remote simple commands.
    "HDMI_1": ["__SOURCE_MACRO__"],
    "HDMI_2": ["__SOURCE_MACRO__"],
    "HDMI_3": ["__SOURCE_MACRO__"],
    "HDMI_4": ["__SOURCE_MACRO__"],

    # v0.9.12 discovery command retained as a hidden diagnostic command.
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
