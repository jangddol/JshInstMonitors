"""RFM error types — raised at serial, re-raised by controller, shown by GUI."""


class RFMError(Exception):
    """Base for all RFM stack errors (serial → controller → GUI)."""


class RFMSerialError(RFMError):
    """Serial port open / read / write failure."""


class RFMSerialTimeout(RFMSerialError):
    """No complete serial line within the overall read timeout."""


class RFMControllerError(RFMError):
    """Business-logic failure (parse, invalid state, wrapped serial)."""
