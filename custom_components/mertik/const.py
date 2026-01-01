"""Constants for the Mertik integration."""

DOMAIN = "mertik"

# --- NETWORK ---
UDP_PORT_DISCOVERY = 30719
UDP_PORT_TARGET = 30718
DISCOVERY_PAYLOAD = "000100f6"

# --- COMMAND PREFIXES ---
# This strange prefix precedes almost every command sent to the device
CMD_PREFIX = "0233303330333033303830"

# --- RESPONSE PREFIXES ---
# The device replies start with these patterns
RESPONSE_PREFIX_1 = "303030300003"
RESPONSE_PREFIX_2 = "030300000003"

# --- CONTROL COMMANDS ---
CMD_STATUS_POLL   = "303303"
CMD_IGNITE        = "314103"
CMD_SHUTDOWN      = "313003"      # Full off (Safety shutoff)
CMD_PILOT_STANDBY = "3136303003"  # Drop to Pilot (Level 0)

CMD_AUX_ON        = "32303031030a"
CMD_AUX_OFF       = "32303030030a"

CMD_LIGHT_ON      = "3330303103"
CMD_LIGHT_OFF     = "3330303003"

CMD_FAN_ON        = "3430303103"  # Fan On
CMD_FAN_OFF       = "3430303003"  # Fan Off

CMD_ECO_MODE      = "4233303103"  # Wave pattern
CMD_MANUAL_MODE   = "423003"      # Static flame

# --- FLAME HEIGHT LOGIC ---
# The command structure for flame is: 3136 + [STEP_CODE] + 03
CMD_FLAME_PREFIX = "3136"
CMD_FLAME_SUFFIX = "03"

# Hex codes corresponding to Levels 0 - 12
FLAME_STEPS = [
    "3030", # Level 0 (Pilot)
    "3830", # Level 1
    "3842", # Level 2
    "3937", # Level 3
    "4132", # Level 4
    "4145", # Level 5
    "4239", # Level 6
    "4335", # Level 7
    "4430", # Level 8
    "4443", # Level 9
    "4537", # Level 10
    "4633", # Level 11
    "4646"  # Level 12 (Max)
]

# --- LIGHT BRIGHTNESS LOGIC ---
# The command structure is: 33304645 + [BRIGHTNESS_CODE] + 03
CMD_LIGHT_SET_PREFIX = "33304645"
CMD_LIGHT_SET_SUFFIX = "03"
