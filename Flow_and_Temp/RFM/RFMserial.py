import enum
import re
import time

import serial
from channel import Channel
from rfm_errors import RFMSerialError, RFMSerialTimeout

# Serial read timeout (seconds). Prevents UI-thread hangs when Arduino is silent.
# Per-read timeout is short so a dead port cannot stall the Tk tick for long.
DEFAULT_READ_TIMEOUT_S = 0.25
DEFAULT_OVERALL_READ_TIMEOUT_S = 0.8
EXPECTED_LINE_LEN = 34
# Arduino: "%04d"*8 + "%01d"*2 → 34 decimal digits + println.
_FLOW_LINE_RE = re.compile(rf"^\d{{{EXPECTED_LINE_LEN}}}$")


def is_valid_flow_line(line: str) -> bool:
    """True if line matches Arduino MeasureBuffer (34 decimal digits)."""
    return bool(line) and _FLOW_LINE_RE.match(line) is not None


class CMD(enum.Enum):
    # serial command dictionary constant
    # U means UNKNOWN
    CMD_SET_CH1_ON = "z"
    CMD_SET_CH2_ON = "x"
    CMD_SET_CH3_ON = "c"
    CMD_SET_CH4_ON = "v"
    CMD_SET_CH1_OFF = "a"
    CMD_SET_CH2_OFF = "s"
    CMD_SET_CH3_OFF = "d"
    CMD_SET_CH4_OFF = "f"
    CMD_SET_FLOW_SETPOINT_CH1 = "q"
    CMD_SET_FLOW_SETPOINT_CH2 = "w"
    CMD_SET_FLOW_SETPOINT_CH3 = "e"
    CMD_SET_FLOW_SETPOINT_CH4 = "r"
    CMD_RESET = "B"


class RFMserial_Real:
    def __init__(self, port, baudrate, timeout=DEFAULT_READ_TIMEOUT_S, *, open_port=True):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        if open_port:
            self._open_port()

    def _open_port(self):
        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                write_timeout=1,
                xonxoff=False,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RFMSerialError(f"Failed to open serial port {self.port}: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected error opening serial port {self.port}: {e}") from e

    def close(self):
        """Close the serial handle if open (best-effort)."""
        ser = self.ser
        self.ser = None
        if ser is None:
            return
        try:
            if ser.is_open:
                ser.close()
        except Exception:
            pass

    def reopen(self):
        """Close and reopen the same COM port (USB blip / driver recovery)."""
        self.close()
        time.sleep(0.05)
        self._open_port()

    def __write(self, data):
        """Write data to the serial port after resetting the input buffer."""
        if self.ser is None:
            raise RFMSerialError(f"Serial port {self.port} is not open")
        try:
            self.ser.reset_input_buffer()
            self.ser.write((data + "\n").encode("ascii"))
            self.ser.flush()
        except serial.SerialException as e:
            raise RFMSerialError(f"Serial write failed: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected serial write error: {e}") from e

    def flush_input(self):
        """Drop pending RX bytes so the next read can resync on a fresh frame."""
        if self.ser is None:
            raise RFMSerialError(f"Serial port {self.port} is not open")
        try:
            self.ser.reset_input_buffer()
        except serial.SerialException as e:
            raise RFMSerialError(f"Serial flush failed: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected serial flush error: {e}") from e

    def reset_serial(self):
        self.__write(CMD.CMD_RESET.value)

    def writeFlowSetpoint_serial(self, flowSetpoint, ch):
        self.__write(flowSetpoint)
        if ch == Channel.CH1:
            self.__write(CMD.CMD_SET_FLOW_SETPOINT_CH1.value)
        elif ch == Channel.CH2:
            self.__write(CMD.CMD_SET_FLOW_SETPOINT_CH2.value)
        elif ch == Channel.CH3:
            self.__write(CMD.CMD_SET_FLOW_SETPOINT_CH3.value)
        elif ch == Channel.CH4:
            self.__write(CMD.CMD_SET_FLOW_SETPOINT_CH4.value)

    def writeChannelOn_serial(self, ch):
        if ch == Channel.CH1:
            self.__write(CMD.CMD_SET_CH1_ON.value)
        elif ch == Channel.CH2:
            self.__write(CMD.CMD_SET_CH2_ON.value)
        elif ch == Channel.CH3:
            self.__write(CMD.CMD_SET_CH3_ON.value)
        elif ch == Channel.CH4:
            self.__write(CMD.CMD_SET_CH4_ON.value)

    def writeChannelOff_serial(self, ch):
        if ch == Channel.CH1:
            self.__write(CMD.CMD_SET_CH1_OFF.value)
        elif ch == Channel.CH2:
            self.__write(CMD.CMD_SET_CH2_OFF.value)
        elif ch == Channel.CH3:
            self.__write(CMD.CMD_SET_CH3_OFF.value)
        elif ch == Channel.CH4:
            self.__write(CMD.CMD_SET_CH4_OFF.value)

    def _read_until_lf(self):
        if self.ser is None:
            raise RFMSerialError(f"Serial port {self.port} is not open")
        lf = b"\n"
        try:
            raw = self.ser.read_until(expected=lf)
            return raw.decode("ascii", errors="replace").strip()
        except serial.SerialException as e:
            raise RFMSerialError(f"Serial read failed: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected serial read error: {e}") from e

    def readline_serial(self, overall_timeout=DEFAULT_OVERALL_READ_TIMEOUT_S):
        """
        Read one Arduino flow frame (34 decimal digits).

        Drains incomplete / non-matching lines until a valid frame or overall_timeout.
        Raises RFMSerialTimeout if no valid line arrives in time (message may include
        short samples of discarded lines for flog/UI).
        Raises RFMSerialError on port I/O failures.
        """
        deadline = time.monotonic() + overall_timeout
        discarded = []

        while time.monotonic() < deadline:
            line = self._read_until_lf()
            if is_valid_flow_line(line):
                return line
            if line:
                discarded.append(f"len={len(line)} raw={line[:64]!r}")

        if discarded:
            # Keep last few samples — enough to debug without flooding the exception text.
            detail = " | discarded: " + "; ".join(discarded[-3:])
        else:
            detail = " | empty RX"
        raise RFMSerialTimeout(
            f"Serial read timeout ({overall_timeout}s): "
            f"no complete {EXPECTED_LINE_LEN}-digit line{detail}"
        )


class RFMserial_Sim:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.channel_state = [False, False, False, False]
        self.flow_setpoint = [0, 0, 0, 0]
        self.channels = [Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN]
        self.reopen_count = 0

    def close(self):
        pass

    def reopen(self):
        self.reopen_count += 1

    def flush_input(self):
        pass

    def reset_serial(self):
        self.channel_state = [False, False, False, False]
        self.flow_setpoint = [0, 0, 0, 0]
        self.channels = [Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN]

    def writeFlowSetpoint_serial(self, flowSetpoint, ch):
        if ch == Channel.CH1:
            self.flow_setpoint[0] = flowSetpoint
        elif ch == Channel.CH2:
            self.flow_setpoint[1] = flowSetpoint
        elif ch == Channel.CH3:
            self.flow_setpoint[2] = flowSetpoint
        elif ch == Channel.CH4:
            self.flow_setpoint[3] = flowSetpoint

    def writeChannelOn_serial(self, ch):
        if ch == Channel.CH1:
            self.channel_state[0] = True
        elif ch == Channel.CH2:
            self.channel_state[1] = True
        elif ch == Channel.CH3:
            self.channel_state[2] = True
        elif ch == Channel.CH4:
            self.channel_state[3] = True

    def writeChannelOff_serial(self, ch):
        if ch == Channel.CH1:
            self.channel_state[0] = False
        elif ch == Channel.CH2:
            self.channel_state[1] = False
        elif ch == Channel.CH3:
            self.channel_state[2] = False
        elif ch == Channel.CH4:
            self.channel_state[3] = False

    def unparse_flow_serial_buffer(self):
        # Match Arduino makeMeasrueBufferFromValues: 8×4-digit + 2×1-digit = 34.
        _flows = [int(float(flows) * 4095 / 99) for flows in self.flow_setpoint]
        return "{:04d}{:04d}{:04d}{:04d}{:04d}{:04d}{:04d}{:04d}{:01d}{:01d}".format(
            _flows[0],
            _flows[1],
            _flows[2],
            _flows[3],
            _flows[0],
            _flows[1],
            _flows[2],
            _flows[3],
            0,
            1,
        )

    def readline_serial(self, overall_timeout=DEFAULT_OVERALL_READ_TIMEOUT_S):
        return self.unparse_flow_serial_buffer()


class RFMserial:
    def __init__(self, on, port, baudrate, timeout=DEFAULT_READ_TIMEOUT_S, *, open_port=True):
        self.on = on
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        if on:
            self.rfmserial = RFMserial_Real(
                port, baudrate, timeout=timeout, open_port=open_port
            )
        else:
            self.rfmserial = RFMserial_Sim(port, baudrate)

    def close(self):
        self.rfmserial.close()

    def reopen(self):
        self.rfmserial.reopen()

    def flush_input(self):
        self.rfmserial.flush_input()

    def reset_serial(self):
        self.rfmserial.reset_serial()

    def writeFlowSetpoint_serial(self, flowSetpoint, ch):
        self.rfmserial.writeFlowSetpoint_serial(flowSetpoint, ch)

    def writeChannelOn_serial(self, ch):
        self.rfmserial.writeChannelOn_serial(ch)

    def writeChannelOff_serial(self, ch):
        self.rfmserial.writeChannelOff_serial(ch)

    def readline_serial(self, overall_timeout=DEFAULT_OVERALL_READ_TIMEOUT_S):
        return self.rfmserial.readline_serial(overall_timeout=overall_timeout)
