import enum
import time

import serial
from channel import Channel
from rfm_errors import RFMSerialError, RFMSerialTimeout

# Serial read timeout (seconds). Prevents UI-thread hangs when Arduino is silent.
# Per-read timeout is short so a dead port cannot stall the Tk tick for long.
DEFAULT_READ_TIMEOUT_S = 0.25
DEFAULT_OVERALL_READ_TIMEOUT_S = 0.8
EXPECTED_LINE_LEN = 34


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
    def __init__(self, port, baudrate, timeout=DEFAULT_READ_TIMEOUT_S):
        self.port = port
        self.baudrate = baudrate
        try:
            self.ser = serial.Serial(
                port,
                baudrate,
                timeout=timeout,
                write_timeout=1,
                xonxoff=False,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RFMSerialError(f"Failed to open serial port {port}: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected error opening serial port {port}: {e}") from e

    def __write(self, data):
        """Write data to the serial port after resetting the input buffer."""
        try:
            self.ser.reset_input_buffer()
            self.ser.write((data + "\n").encode("ascii"))
            self.ser.flush()
        except serial.SerialException as e:
            raise RFMSerialError(f"Serial write failed: {e}") from e
        except Exception as e:
            raise RFMSerialError(f"Unexpected serial write error: {e}") from e

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
        Read one complete flow line.

        Raises RFMSerialTimeout if no valid line arrives within overall_timeout.
        Raises RFMSerialError on port I/O failures.
        """
        deadline = time.monotonic() + overall_timeout

        for _ in range(2):
            if time.monotonic() >= deadline:
                raise RFMSerialTimeout(
                    f"Serial read timeout ({overall_timeout}s) while discarding stale lines"
                )
            self._read_until_lf()

        while time.monotonic() < deadline:
            line = self._read_until_lf()
            if line and len(line) == EXPECTED_LINE_LEN:
                # Raw Arduino line for console diagnostics (34 chars when healthy).
                print(line)
                return line

        raise RFMSerialTimeout(
            f"Serial read timeout ({overall_timeout}s): no complete {EXPECTED_LINE_LEN}-char line"
        )


class RFMserial_Sim:
    def __init__(self, port, baudrate):
        self.channel_state = [False, False, False, False]
        self.flow_setpoint = [0, 0, 0, 0]
        self.channels = [Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN, Channel.CH_UNKNOWN]

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
        _flows = [int(float(flows) * 4095 / 99) for flows in self.flow_setpoint]
        return "{:04d}{:04d}{:04d}{:04d}".format(_flows[0], _flows[1], _flows[2], _flows[3])

    def readline_serial(self, overall_timeout=DEFAULT_OVERALL_READ_TIMEOUT_S):
        return self.unparse_flow_serial_buffer()


class RFMserial:
    def __init__(self, on, port, baudrate, timeout=DEFAULT_READ_TIMEOUT_S):
        if on:
            self.rfmserial = RFMserial_Real(port, baudrate, timeout=timeout)
        else:
            self.rfmserial = RFMserial_Sim(port, baudrate)

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
