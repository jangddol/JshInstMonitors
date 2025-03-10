from copy import deepcopy
import serial
import enum
from channel import Channel
import time

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
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.ser = serial.Serial(port, baudrate, write_timeout=1, xonxoff=False)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def __write(self, data):
        self.ser.reset_input_buffer() # 이거 안하면 write_timeout 걸리던데 왜인지는 모름
        self.ser.write((data + '\n').encode('ascii'))
        self.ser.flush() # 다 써지기를 기다림

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

    def readline_serial(self):
        lf = b'\n'  # 개행 문자를 바이트로 정의
        # time.sleep(0.01) # 이걸로 딜레이를 주었더니 잘못 받아오는 확률이 더 늘어났음. 그냥 아래처럼 3번 읽는게 맞는거 같음
        self.ser.read_until(expected=lf) # 첫 번째 읽기: 현재 라인의 나머지 부분을 읽고 버립니다
        self.ser.read_until(expected=lf) # 두 번째 읽기: 딜레이를 주기 위한 잉여 읽기
        line = self.ser.read_until(expected=lf).decode('ascii').strip() # 세 번째 읽기: 온전한 새 라인을 읽습니다
        while not line or len(line) != 18: # 빈 라인이면 다시 읽습니다
            line = self.ser.read_until(expected=lf).decode('ascii').strip()
        try:
            parsed_numbers = [line[i:i+4] for i in range(0, len(line), 4)]
            print(line, " ", parsed_numbers, " ", len(line))
        except Exception as e:
            print(e)
            line = "0000000000000000"
        return line

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

    def readline_serial(self):
        return self.unparse_flow_serial_buffer()
    

class RFMserial:
    def __init__(self, on, port, baudrate):
        if on:
            self.rfmserial = RFMserial_Real(port, baudrate)
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
    
    def readline_serial(self):
        return self.rfmserial.readline_serial()