import json
import tkinter as tk
from typing import Final
import numpy as np
import time
import os
import sys
from enum import Enum

from RFMserial import RFMserial
from channel import Channel, ChannelName, convert_int_to_channel
from schedularwindow import Action, SchedularWindow, ScheduleWidget

SERIAL_ON = True

# graphic constants
COLUMNNUM = 3
COLUMNWIDTH = 235
HEIGHT = 385
FONT_SIZE = 15
SWITCH_XOFFSET = 10
SWITCH_YOFFSET = 240
SWITCH_WIDTH = 100
SWITCH_HEIGHT = 30
RESET_XOFFSET = 120
RESET_YOFFSET = 5
RESET_WIDTH = 50
RESET_HEIGHT = 15
SCHEDULAR_XOFFSET = RESET_XOFFSET
SCHEDULAR_YOFFSET = 30
SCHEDULAR_WIDTH = RESET_WIDTH
SCHEDULAR_HEIGHT = RESET_HEIGHT
MINITOGGLE_XOFFSET = RESET_XOFFSET + 60
MINITOGGLE_YOFFSET = SCHEDULAR_YOFFSET
MINITOGGLE_WIDTH = RESET_WIDTH
MINITOGGLE_HEIGHT = RESET_HEIGHT
MINIHEIGHT = 130

# color constant
COLOR_WHITE = "white"
COLOR_BLACK = "black"
COLOR_HIGHLIGHTED = "gray"

# highlighed entry enum
ENTRY_HIGHLIGHTED_NONE = 0
ENTRY_HIGHLIGHTED_FLOWSET_L = 1
ENTRY_HIGHLIGHTED_FLOWSET_M = 2
ENTRY_HIGHLIGHTED_FLOWSET_R = 3
ENTRY_HIGHLIGHTED_CH_L = 4
ENTRY_HIGHLIGHTED_CH_M = 5
ENTRY_HIGHLIGHTED_CH_R = 6

# toggleStates constant
class ToggleState(Enum):
    On = 1
    Off = 2
    SelectChannel = 3



class RFMApp:
    DAY_TO_HOUR : Final = 24
    HOUR_TO_MIN : Final = 60
    PC_INPUT_MAX : Final = 99
    ARDUINO_WRITE_MAX : Final = 4095
    
    def __init__(self, master, port):
        self.master = master
        self.setup_initial_state()
        self.setup_ui()
        self.setup_schedular()
        self.setup_serial(SERIAL_ON, port)
        self.main_loop()
        self.last_read_time = time.time()

    def initialize_arrays(self):
        self.flowSetPoint_Entry = [""] * COLUMNNUM
        self.flowSetPoints_Shown = ["  Set Channel"] * COLUMNNUM
        self.toggleStates = [ToggleState.Off] * COLUMNNUM
        self.channels = [Channel.CH_UNKNOWN] * COLUMNNUM
        self.channelsEntry = [""] * COLUMNNUM
        self.flowSetPointBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.channelBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.last_flow_values = [0] * COLUMNNUM

    def setup_initial_state(self):
        self.initialize_arrays()
        self.highlighted_entry = ENTRY_HIGHLIGHTED_NONE
        self.mn = False
        self.lastwidth = 0
        self.lastheight = 0
        self.width = COLUMNNUM * COLUMNWIDTH
        self.height = HEIGHT

    def setup_ui(self):
        self.master.geometry(f"{self.width}x{self.height}")
        self.master.resizable(True, True)
        self.master.title("MFC Readout Reader")
        
        self.canvas = tk.Canvas(self.master, width=self.width, height=self.height, bg='black')
        self.canvas.pack()

        self.setup_buttons()
        self.setup_bindings()

    def setup_buttons(self):
        self.switchs_toggle = [
            tk.Button(self.master, text="OFF", command=lambda i=i: self.on_switch_toggle(i))
            for i in range(COLUMNNUM)
        ]
        
        self.reset_button = tk.Button(self.master, text="RESET", command=self.on_reset_click)
        self.schedular_button = tk.Button(self.master, text="Schedular", command=self.on_schedular_click)
        self.mini_toggle = tk.Button(self.master, text="Mini", command=self.on_mini_toggle)
        
        self.place_buttons()

    def place_buttons(self):
        if not self.mn:
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            for i in range(COLUMNNUM):
                self.switchs_toggle[i].place(x=(SWITCH_XOFFSET + i * COLUMNWIDTH) * resize_ratio_x, y=SWITCH_YOFFSET * resize_ratio_y,
                                             width=SWITCH_WIDTH * resize_ratio_x, height=SWITCH_HEIGHT * resize_ratio_y)
            self.reset_button.place(x=RESET_XOFFSET * resize_ratio_x, y=RESET_YOFFSET * resize_ratio_y,
                                    width=RESET_WIDTH * resize_ratio_x, height=RESET_HEIGHT * resize_ratio_y)
            self.schedular_button.place(x=SCHEDULAR_XOFFSET * resize_ratio_x, y=SCHEDULAR_YOFFSET * resize_ratio_y,
                                   width=SCHEDULAR_WIDTH * resize_ratio_x, height=SCHEDULAR_HEIGHT * resize_ratio_y)
            self.mini_toggle.place(x=MINITOGGLE_XOFFSET * resize_ratio_x, y=MINITOGGLE_YOFFSET * resize_ratio_y,
                                   width=MINITOGGLE_WIDTH * resize_ratio_x, height=MINITOGGLE_HEIGHT * resize_ratio_y)
        else:
            self.reset_button.place(x=RESET_XOFFSET, y=RESET_YOFFSET, width=RESET_WIDTH, height=RESET_HEIGHT)
            self.schedular_button.place(x=SCHEDULAR_XOFFSET, y=SCHEDULAR_YOFFSET, width=SCHEDULAR_WIDTH, height=SCHEDULAR_HEIGHT)
            self.mini_toggle.place(x=MINITOGGLE_XOFFSET, y=MINITOGGLE_YOFFSET, width=MINITOGGLE_WIDTH, height=MINITOGGLE_HEIGHT)

    def setup_bindings(self):
        self.master.bind("<Key>", self.key_pressed)
        self.master.bind("<Button-1>", self.mouse_pressed)
        self.master.bind("<Configure>", self.on_resize)

    def setup_schedular(self):
        self.last_schedule_handle_time_in_min = self.get_time_in_min()
        self.schedular_window = None

    def setup_serial(self, on, port):
        self.serial = RFMserial(on, port, 9600)

    def get_time_in_min(self):
        localtime = time.localtime()
        return localtime.tm_wday * self.DAY_TO_HOUR * self.HOUR_TO_MIN + localtime.tm_hour * self.HOUR_TO_MIN + localtime.tm_min

    def main_loop(self):
        self.update()
        UPDATE_INTERVAL_MS = 100
        self.master.after(UPDATE_INTERVAL_MS, self.main_loop)  # Schedule next update, 0.1 s

    def update(self):
        self.draw()
        
        self.last_flow_values = self.read_flow_values()
        self.displayFlowValues([f"{x:.2f}" for x in self.last_flow_values])
        
        self.handle_schedular()

    def read_flow_values(self):
        flow_values = [0] * COLUMNNUM
        
        self.serial.setReadingChannel_serial(self.channels)

        serial_buffer = self.serial.readline_serial()
        if serial_buffer:
            temp_flow_values = self.parse_flow_serial_buffer(serial_buffer)
            flow_values[0] = temp_flow_values[0]
            flow_values[1] = temp_flow_values[1]
        

        tempChannels = [Channel.CH_UNKNOWN, self.channels[2]]
        if self.channels[2] != Channel.CH_UNKNOWN:
            self.serial.setReadingChannel_serial(tempChannels)
            serial_buffer = self.serial.readline_serial()
            if serial_buffer:
                temp_flow_values = self.parse_flow_serial_buffer(serial_buffer)
                flow_values[2] = temp_flow_values[1]

        self.last_read_time = time.time()

        return flow_values

    def handle_schedular(self):
        if not hasattr(self, 'schedular_window') or self.schedular_window is None:
            return

        # load schedularwidget data
        schedules = self.schedular_window.schedule_widgets
        localtime = time.localtime()
        for schedule in schedules:
            if self.is_needed_to_do_scheduling(schedule, localtime):
                self.process_schedule_action(schedule)
        
        self.last_schedule_handle_time_in_min = self.get_time_in_min()

    def is_needed_to_do_scheduling(self, schedule: ScheduleWidget, localtime):
        # 요일이 같고 시간이 같으면서 (최소 1분에 한번은 update가 돌 것이라는 가정하에)
        # schedule_handle_time이 현재 시간과 다르면 (이는 일주일 중 단 한번만 실행되게끔 보장하기 위함이다.)
        # schdular에 있는 동작을 수행한다.
        try:
            schedule.day.get_int()
        except:
            print("Invalid schedule data : day")
            return False
        try:
            schedule.hour
        except:
            print("Invalid schedule data : hour")
            return False
        try:
            schedule.minute
        except:
            print("Invalid schedule data : minute")
            return False
        if schedule.action == Action.Setpoint:
            try:
                schedule.number
            except:
                print("Invalid schedule data : setpoint")
                return False
        is_same_day = schedule.day.get_int() == localtime.tm_wday
        is_same_time: bool = schedule.hour == localtime.tm_hour and schedule.minute == localtime.tm_min
        is_different_time_with_last_time = self.last_schedule_handle_time_in_min != self.get_time_in_min()
        return is_same_day and is_same_time and is_different_time_with_last_time

    def process_schedule_action(self, schedule: ScheduleWidget):
        channel_index = schedule.channelname.get_column()
        channel = self.channels[channel_index]
        if channel == Channel.CH_UNKNOWN:
            return
        
        action = schedule.action
        if action == Action.On:
            if self.toggleStates[channel_index] == ToggleState.Off:
                self.on_switch_toggle(channel_index)
        elif action == Action.Off:
            if self.toggleStates[channel_index] == ToggleState.On:
                self.on_switch_toggle(channel_index)
        elif action == Action.Setpoint:
            if self.toggleStates[channel_index] == ToggleState.On:
                self.flowSetPoint_Entry[channel_index] = str(schedule.number)
                self.update_flow_setpoint(channel_index)

    def draw(self):
        # background as black
        self.master.configure(bg="black")
        # update width and height from window size
        self.width = self.master.winfo_width()
        self.height = self.master.winfo_height()
        
        self.fillEntryBkgColor()
        self.displayTexts()
        self.place_buttons()

    def on_resize(self, event):
        self.width = event.width
        self.height = event.height
        if self.width != self.lastwidth or self.height != self.lastheight:
            self.draw()
            self.lastwidth = self.width
            self.lastheight = self.height
        self.canvas.config(width=self.width, height=self.height)

    def on_switch_toggle(self, index):
        state = self.switchs_toggle[index].config('relief')[-1] == 'sunken'
        self.toggle_switch(index, state)
        if state:
            self.switchs_toggle[index].config(relief="raised", text="OFF")
        else:
            self.switchs_toggle[index].config(relief="sunken", text="ON")

    def toggle_switch(self, switch_index, last_switch_state):
        if last_switch_state:
            self.toggleStates[switch_index] = ToggleState.Off
            if self.channels[switch_index] == Channel.CH_UNKNOWN:
                return
            
            self.flowSetPoints_Shown[switch_index] = "paused"
            self.flowSetPoint_Entry[switch_index] = ""
            self.serial.writeChannelOff_serial(self.channels[switch_index])
        else:
            if self.channels[switch_index] == Channel.CH_UNKNOWN:
                self.toggleStates[switch_index] = ToggleState.SelectChannel
                return
            
            self.toggleStates[switch_index] = ToggleState.On
            self.flowSetPoints_Shown[switch_index] = "0"
            self.serial.writeFlowSetpoint_serial("0", self.channels[switch_index])
            self.serial.writeChannelOn_serial(self.channels[switch_index])

    def on_mini_toggle(self):
        if self.mini_toggle.config('relief')[-1] == 'sunken':
            self.mini_toggle.config(relief="raised")
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{HEIGHT}")
            self.mn = False
        else:
            self.mini_toggle.config(relief="sunken")
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{MINIHEIGHT}")
            self.mn = True

    def on_reset_click(self):
        self.setup_initial_state()
        self.serial.reset_serial()

    def on_schedular_click(self):
        if not hasattr(self, 'schedular_window') or self.schedular_window is None:
            self.schedular_window = SchedularWindow(self.master)
        
        self.schedular_window.show()

    def fillEntryBkgColor(self):
        self.canvas.delete("all")  # 기존 도형 모두 삭제
        if not self.mn:
            for i in range(COLUMNNUM):
                # flowSetPointBkgColors 사각형
                x1 = (60 + i * COLUMNWIDTH) * self.width / (COLUMNNUM * COLUMNWIDTH)
                y1 = 167 * self.height / HEIGHT
                x2 = x1 + 160 * self.width / (COLUMNNUM * COLUMNWIDTH)
                y2 = y1 + 18 * self.height / HEIGHT
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.flowSetPointBkgColors[i], outline="")

                # channelBkgColors 사각형
                y1 = 337 * self.height / HEIGHT
                y2 = y1 + 18 * self.height / HEIGHT
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.channelBkgColors[i], outline="")

    def displayTexts(self):
        COLUMNNAME = [ChannelName.Tip.value, ChannelName.Shield.value, ChannelName.Bypass.value]
        if not self.mn:
            line = '.' * 100
            
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            resize_ratio_tot = (self.height + self.width) / (COLUMNNUM * COLUMNWIDTH + HEIGHT)
            font_size = int(FONT_SIZE * resize_ratio_tot)
            font = ('Calibri Light', font_size)
            
            self.canvas.create_text(0, resize_ratio_y * 125,
                                    text=line, fill='white', font=font, anchor='w')
            self.canvas.create_text(0, resize_ratio_y * 210,
                                    text=line, fill='white', font=font, anchor='w')
            self.canvas.create_text(0, resize_ratio_y * 305,
                                    text=line, fill='white', font=font, anchor='w')

            for i in range(COLUMNNUM):
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 20,
                                        text=f"({COLUMNNAME[i]}) Ch  {self.channels[i].value}", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 55,
                                        text="Sensing Output", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 150,
                                        text="Setting Input", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 175,
                                        text=f"Input: {self.flowSetPoint_Entry[i]}", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * i * COLUMNWIDTH, resize_ratio_y * 200,
                                        text=f"  {self.flowSetPoints_Shown[i]}", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 325,
                                        text=f"Setting {COLUMNNAME[i]} Ch.", fill='white', font=font, anchor='w')
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 345,
                                        text=f"Input: {self.channelsEntry[i]}", fill='white', font=font, anchor='w')
        else:
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{MINIHEIGHT}")
            font = ('Calibri Light', FONT_SIZE)
            for i in range(COLUMNNUM):
                self.canvas.create_text(10 + i * COLUMNWIDTH, 20,
                                        text=f"({COLUMNNAME[i]}) Ch  {self.channels[i].value}", fill='white', font=font, anchor='w')
                self.canvas.create_text(10 + i * COLUMNWIDTH, 55,
                                        text="Sensing Output", fill='white', font=font, anchor='w')

    def parse_flow_serial_buffer(self, flow_string):
        # aaaabb.bb is the format of the flow sensor data
        # aaaa * (99/10) / 4095 is the first channel's flow value
        # bbbb * (99/10) / 4095 is the second channel's flow value
        # the magic numbers 99 and 40950 are determined by the flow sensor's characteristics
        aaaabbpbb = float(flow_string)
        aaaapbbbb = aaaabbpbb / 100
        aaaa = int(aaaapbbbb)
        bbbb = int((aaaapbbbb - aaaa) * 1e4)
        flow_L = (float(aaaa) * (self.PC_INPUT_MAX/10) / self.ARDUINO_WRITE_MAX)
        flow_R = (float(bbbb) * (self.PC_INPUT_MAX/10) / self.ARDUINO_WRITE_MAX)
        return [flow_L, flow_R]

    def displayFlowValues(self, flowValues):
        if not self.mn:
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            resize_ratio_tot = (self.height + self.width) / (COLUMNNUM * COLUMNWIDTH + HEIGHT)
            font_size = int(FONT_SIZE * resize_ratio_tot)
            font = ('Calibri Light', font_size)
            for i in range(COLUMNNUM):
                self.canvas.create_text(resize_ratio_x * (10 + i * COLUMNWIDTH), resize_ratio_y * 80,
                                        text=flowValues[i], fill='white', font=font, anchor='w')
        else:
            font = ('Calibri Light', FONT_SIZE)
            for i in range(COLUMNNUM):
                self.canvas.create_text(10 + i * COLUMNWIDTH, 80,
                                        text=flowValues[i], fill='white', font=font, anchor='w')

    def is_valid_flow_setpoint(self, flow_setpoint_entry):
        try:
            flow_setpoint = int(flow_setpoint_entry)
        except:
            return False
        return 0 <= flow_setpoint <= self.PC_INPUT_MAX
    
    def update_flow_setpoint(self, index):
        if self.channels[index] == Channel.CH_UNKNOWN:
            self.flowSetPoints_Shown[index] = "Set Channel"
            return

        if not self.is_valid_flow_setpoint(self.flowSetPoint_Entry[index]):
            self.flowSetPoints_Shown[index] = "Input invalid"
            return

        self.serial.writeFlowSetpoint_serial(self.flowSetPoint_Entry[index], self.channels[index])
        self.flowSetPoints_Shown[index] = self.flowSetPoint_Entry[index]

    def apply_changed_channel(self, index):
        channelEntry_int = 0
        try:
            channelEntry_int = int(self.channelsEntry[index])
        except Exception:
            pass
        self.channelsEntry[index] = ""
        self.channels[index] = convert_int_to_channel(channelEntry_int)
        if self.channels[index] != Channel.CH_UNKNOWN:
            self.flowSetPoints_Shown[index] = "paused"
            self.serial.setReadingChannel_serial(self.channels)

    def is_key_code_change_highlight_entry(self, key_code):
        return key_code == 'Tab' or key_code == 'Left' or key_code == 'Right' or key_code == 'Up' or key_code == 'Down'
    
    def get_highlight_entry_using_keycode(self, key_code, highlighted_entry):
        if key_code == 'Tab':
            highlighted_entry = highlighted_entry + 1
        if highlighted_entry == COLUMNNUM * 2 + 1:
            highlighted_entry = 1
        return highlighted_entry

    def key_pressed(self, event):
        if self.is_key_code_change_highlight_entry(event.keysym):
            highlight_entry = self.get_highlight_entry_using_keycode(event.keysym, self.highlighted_entry)
            self.change_highlight_entry_to(highlight_entry)
        elif event.keysym == 'Return' or event.keysym == 'Enter':
            if self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_L and self.toggleStates[0] == ToggleState.On:
                self.update_flow_setpoint(0)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_M and self.toggleStates[1] == ToggleState.On:
                self.update_flow_setpoint(1)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_R and self.toggleStates[2] == ToggleState.On:
                self.update_flow_setpoint(2)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_L and self.toggleStates[0] == ToggleState.Off:
                self.apply_changed_channel(0)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_M and self.toggleStates[1] == ToggleState.Off:
                self.apply_changed_channel(1)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_R and self.toggleStates[2] == ToggleState.Off:
                self.apply_changed_channel(2)
        else:
            if self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_L and self.toggleStates[0] == ToggleState.On:
                self.flowSetPoint_Entry[0] = self.modify_number_string_by_key(self.flowSetPoint_Entry[0], event.keysym, event.char)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_M and self.toggleStates[1] == ToggleState.On:
                self.flowSetPoint_Entry[1] = self.modify_number_string_by_key(self.flowSetPoint_Entry[1], event.keysym, event.char)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_FLOWSET_R and self.toggleStates[2] == ToggleState.On:
                self.flowSetPoint_Entry[2] = self.modify_number_string_by_key(self.flowSetPoint_Entry[2], event.keysym, event.char)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_L and self.toggleStates[0] == ToggleState.Off:
                self.channelsEntry[0] = self.modify_number_string_by_key(self.channelsEntry[0], event.keysym, event.char)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_M and self.toggleStates[1] == ToggleState.Off:
                self.channelsEntry[1] = self.modify_number_string_by_key(self.channelsEntry[1], event.keysym, event.char)
            elif self.highlighted_entry == ENTRY_HIGHLIGHTED_CH_R and self.toggleStates[2] == ToggleState.Off:
                self.channelsEntry[2] = self.modify_number_string_by_key(self.channelsEntry[2], event.keysym, event.char)

    def modify_number_string_by_key(self, number_string, key_code, key):
        if key_code == 'BackSpace' and len(number_string) > 0:
            number_string = number_string[:-1]
        if key.isdigit():
            number_string += key
        return number_string

    def get_column_index_from_mouse(self, mouseX):
        columnwidth = COLUMNWIDTH
        if not self.mn:
            columnwidth = COLUMNWIDTH * self.width / (COLUMNNUM * COLUMNWIDTH)
        return np.floor(mouseX / columnwidth)
    
    def get_row_index_from_mouse(self, mouseY):
        SENTINAL_VALUE = -1
        if not self.mn:
            if (mouseY < self.height * 266 / HEIGHT) and (mouseY > 139 * self.height / HEIGHT):
                return 0
            elif mouseY > self.height * 320 / HEIGHT:
                return 1
            else:
                return SENTINAL_VALUE
        else:
            if (mouseY < 266) and (mouseY > 139):
                return 0
            elif mouseY > 320:
                return 1
            else:
                return SENTINAL_VALUE
    
    def get_highlited_entry_from_mouse(self, mouseX, mouseY):
        if self.get_row_index_from_mouse(mouseY) == -1:
            return ENTRY_HIGHLIGHTED_NONE
        return 1 + self.get_column_index_from_mouse(mouseX) + COLUMNNUM * self.get_row_index_from_mouse(mouseY)
        
    def mouse_pressed(self, event):
        highlighted_entry = self.get_highlited_entry_from_mouse(event.x, event.y)
        self.change_highlight_entry_to(highlighted_entry)

    def change_highlight_entry_to(self, entry):
        self.highlighted_entry = entry
        
        if entry == ENTRY_HIGHLIGHTED_FLOWSET_L:
            self.flowSetPointBkgColors[0] = COLOR_HIGHLIGHTED
        else:
            self.flowSetPointBkgColors[0] = COLOR_BLACK
            self.flowSetPoint_Entry[0] = ""
        
        if entry == ENTRY_HIGHLIGHTED_FLOWSET_M:
            self.flowSetPointBkgColors[1] = COLOR_HIGHLIGHTED
        else:
            self.flowSetPointBkgColors[1] = COLOR_BLACK
            self.flowSetPoint_Entry[1] = ""
        
        if entry == ENTRY_HIGHLIGHTED_FLOWSET_R:
            self.flowSetPointBkgColors[2] = COLOR_HIGHLIGHTED
        else:
            self.flowSetPointBkgColors[2] = COLOR_BLACK
            self.flowSetPoint_Entry[2] = ""
        
        if entry == ENTRY_HIGHLIGHTED_CH_L:
            self.channelBkgColors[0] = COLOR_HIGHLIGHTED
        else:
            self.channelBkgColors[0] = COLOR_BLACK
            self.channelsEntry[0] = ""
        
        if entry == ENTRY_HIGHLIGHTED_CH_M:
            self.channelBkgColors[1] = COLOR_HIGHLIGHTED
        else:
            self.channelBkgColors[1] = COLOR_BLACK
            self.channelsEntry[1] = ""
        
        if entry == ENTRY_HIGHLIGHTED_CH_R:
            self.channelBkgColors[2] = COLOR_HIGHLIGHTED
        else:
            self.channelBkgColors[2] = COLOR_BLACK
            self.channelsEntry[2] = ""


def open_config_file(file_path: str):
    # json file has two keys: 'arduino_port' and 'localserver_port'
    # 'arduino_port' is the COM port of the arduino for controlling MKS247C.
    # 'localserver_port' is the port number of the server. It should be an integer in range of 0 to 65535.
    
    with open(file_path, 'r') as file: # open json from file_path
        config_data = json.load(file)
        arduino_port = config_data.get('arduino_port')
        localserver_port = config_data.get('localserver_port')
        
        if not isinstance(arduino_port, str) or not isinstance(localserver_port, int): # parsing json, check error from casting
            raise ValueError("Invalid configuration data")
        
        return arduino_port, localserver_port


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    import threading
    from flask import Flask, jsonify
    
    config_file_path = "rfm_config.json"
    # If loading fails, create a default config.json.
    try:
        arduino_port, localserver_port = open_config_file(config_file_path)
    except Exception as e:
        print(e)
        with open(config_file_path, 'w') as file:
            json.dump({'arduino_port': 'COM3', 'localserver_port': 5000}, file)
        arduino_port, localserver_port = open_config_file(config_file_path)
    
    # Flask 애플리케이션 설정
    app = Flask(__name__)

    @app.route('/get_value', methods=['GET'])
    def get_value():
        return jsonify({'Tip': rfmapp.last_flow_values[0], 'Shield': rfmapp.last_flow_values[1], 'Bypass': rfmapp.last_flow_values[2], 'timestamp': rfmapp.last_read_time})

    def run_app(port):
        # GUI 애플리케이션 실행
        master = tk.Tk()
        master.iconbitmap(resource_path("MFC.ico"))
        global rfmapp
        rfmapp = RFMApp(master, port)
        rfmapp.master.mainloop()

    def run_flask():
        # Flask 서버 실행
        app.run(host='0.0.0.0', port=localserver_port, use_reloader=False)

    # 서브 스레드에서 Flask 서버 실행
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    run_app(arduino_port)
