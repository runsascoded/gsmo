from enum import Enum


class Err(Enum):
    OK = 1
    IGNORE = 1
    WARN = 2
    RAISE = 3
    ERR = 3
    ERROR = 3


OK = Err.OK
WARN = Err.WARN
RAISE = Err.RAISE
