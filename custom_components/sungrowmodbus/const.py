"""Constants used in modbus integration."""

from enum import Enum

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_SENSORS,
    CONF_SWITCHES,
    Platform,
)

# configuration names
CONF_BYTESIZE = "bytesize"
CONF_BRIGHTNESS_REGISTER = "brightness_address"
CONF_COLOR_TEMP_REGISTER = "color_temp_address"
CONF_DATA_TYPE = "data_type"
CONF_DEVICE_ADDRESS = "device_address"
CONF_INPUT_TYPE = "input_type"
CONF_MAX_TEMP = "max_temp"
CONF_MAX_VALUE = "max_value"
CONF_MIN_TEMP = "min_temp"
CONF_MIN_VALUE = "min_value"
CONF_MSG_WAIT = "message_wait_milliseconds"
CONF_NAN_VALUE = "nan_value"
CONF_PRECISION = "precision"
CONF_SCALE = "scale"
CONF_SLAVE_COUNT = "slave_count"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_STATUS_REGISTER = "status_register"
CONF_STATUS_REGISTER_TYPE = "status_register_type"
CONF_STEP = "temp_step"
CONF_SWAP = "swap"
CONF_SWAP_BYTE = "byte"
CONF_SWAP_WORD = "word"
CONF_SWAP_WORD_BYTE = "word_byte"
CONF_TARGET_TEMP = "target_temp_register"
CONF_TARGET_TEMP_WRITE_REGISTERS = "target_temp_write_registers"
CONF_WRITE_REGISTERS = "write_registers"
CONF_VERIFY = "verify"
CONF_VIRTUAL_COUNT = "virtual_count"
CONF_WRITE_TYPE = "write_type"
CONF_ZERO_SUPPRESS = "zero_suppress"

SUNGROW = "sungrow"


# service call attributes
ATTR_ADDRESS = CONF_ADDRESS
ATTR_HUB = "hub"
ATTR_UNIT = "unit"
ATTR_SLAVE = "slave"
ATTR_VALUE = "value"


class DataType(str, Enum):
    """Data types used by sensor etc."""

    CUSTOM = "custom"
    STRING = "string"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT16 = "float16"
    FLOAT32 = "float32"
    FLOAT64 = "float64"


# call types
CALL_TYPE_COIL = "coil"
CALL_TYPE_DISCRETE = "discrete_input"
CALL_TYPE_REGISTER_HOLDING = "holding"
CALL_TYPE_REGISTER_INPUT = "input"
CALL_TYPE_WRITE_COIL = "write_coil"
CALL_TYPE_WRITE_COILS = "write_coils"
CALL_TYPE_WRITE_REGISTER = "write_register"
CALL_TYPE_WRITE_REGISTERS = "write_registers"
CALL_TYPE_X_COILS = "coils"
CALL_TYPE_X_REGISTER_HOLDINGS = "holdings"

# service calls
SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"
SERVICE_STOP = "stop"
SERVICE_RESTART = "restart"

# dispatcher signals
SIGNAL_STOP_ENTITY = "sungrowmodbus.stop"
SIGNAL_START_ENTITY = "sungrowmodbus.start"

# integration names
DEFAULT_HUB = "sungrowmodbus_hub"
DEFAULT_SCAN_INTERVAL = 15  # seconds
DEFAULT_SLAVE = 1
DEFAULT_STRUCTURE_PREFIX = ">f"
DEFAULT_TEMP_UNIT = "C"
MODBUS_DOMAIN = "sungrowmodbus"

ACTIVE_SCAN_INTERVAL = 2  # limit to force an extra update

PLATFORMS = (
    (Platform.BINARY_SENSOR, CONF_BINARY_SENSORS),
    (Platform.SENSOR, CONF_SENSORS),
    (Platform.SWITCH, CONF_SWITCHES),
)
