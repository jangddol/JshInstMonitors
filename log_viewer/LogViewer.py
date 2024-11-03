# 로그 파일을 올려놓으면 자동으로 로그에 맞춰서 그래프를 그려주는 프로그램.
# 로그 파일에는 두 종류가 있음.
# 1. Pressure & Level Log
# 2. Flow & Temperature Log
# 유저는 두 개 이상의 로그를 올려놓을 수 있음.
# 올려놓는다고 바로 그래프를 보여주지는 않아도 됨.
# 그래프를 보여주는 도구는 matplotlib의 plt.show를 그대로 사용할거임.

# 올려놓아진 그래프는 다음의 가능성이 있음.
# 1. 하나의 파일을 올린 경우
# 2. 두 개 이상의 파일을 올린 경우
# 2-1. 시간에 대해서
# 2-1-1. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 있는 경우
# 2-1-2. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 없는 경우
# 2-1-3. 시간에 대해서 연속되지 않은 날짜가 있는 경우
# 2-2. 데이터에 대해서
# 2-2-1. Pressure & Level Log만 올린 경우
# 2-2-2. Flow & Temperature Log만 올린 경우
# 2-2-3. 둘 다 올린 경우

# 1. 하나의 파일을 올린 경우는 그냥 보여주면 됨.
# 2. 두 개 이상의 파일을 올린 경우는 다음과 같이 처리함.
# 2-1. 시간에 대해서
# 2-1-1. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 있는 경우 해당 데이터를 붙여서 그래프를 그림.
# 2-1-2. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 없는 경우 경고를 날리고, 해당 데이터를 붙여서 그래프를 그림.
    # 이를 위해서는 연속된 시간이라는 것을 정의해야하는데, 이는 5분 이내의 차이로 정의함.
# 2-1-3. 시간에 대해서 연속되지 않은 날짜가 있는 경우 경고를 날리고, 해당 데이터를 그려주지 않음.
# 2-2. 데이터에 대해서
# 2-2-1. Pressure & Level Log만 올린 경우 Pressure & Level Log를 그림.
# 2-2-2. Flow & Temperature Log만 올린 경우 Flow & Temperature Log를 그림.
# 2-2-3. 둘 다 올린 경우 위에는 Pressure & Level Log를, 아래는 Flow & Temperature Log를 그림.

# Pressure & Level Log는 다음과 같은 형태로 되어있음.
# YYYY-MM-DD HH:MM:SS: Level V, Pressure psi, Pressure psi, (V 는 나중에 L로 바꿀 예정. 따라서 L도 호환되도록 만들어야함.)
# ex) 2024-10-21 19:10:16: 0.00 V, 0.00 psi, 0.00 psi

# Flow & Temperature Log는 다음과 같은 형태로 되어있음.
# YYYY-MM-DD HH:MM:SS: Flow L/min, Flow L/min, Flow L/min, Temperature K, Temperature K

# 위에 서술한 기능들을 모두 구현하기 위해서, tkinter gui 라이브러리를 사용할 것이고,
# 파일을 드래그 해서 올려놓으면 해당 파일의 경로 및 이름을 저장하게 하도록 할 것임.
# 이를 위해서, 드래그 해서 올려놓을 위치를 filedialog를 사용하여 받아올 것임.
# 그리고 불러온 목록 초기화 버튼, 그래프 그리기 버튼, 보여줄수 있는 기간 표시 영역, 그래프를 그릴 기간 표시 입력 영역을 만들 것임.
# 추가적으로 연속적인 시간으로 불렀는지 경고문구를 띄울 공간도 있어야함.
# 불러온 목록 초기화 버튼을 누르면 불러온 목록이 초기화되고, 그래프 그리기 버튼을 누르면 그래프가 그려질 것임.
# 보여줄수 있는 기간 표시 영역은 현재 불러온 로그 파일들로부터 가장 빠른 날짜와 가장 늦은 날짜를 보여줄 것임.
# 연속적인 시간으로 불렀는지는, 불러온 로그 파일들의 시간 부분이 연속적인지 확인하여, 연속적이지 않으면 경고문구를 띄울 것임.
# 그래프를 그릴 기간 표시 입력 영역은 그래프를 그릴 때, 그래프의 x축에 해당하는 값을 입력하는 영역임.

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from tkinterdnd2 import DND_FILES, TkinterDnD
import re
from dataclasses import dataclass

@dataclass
class LogFile():
    file_path: str
    first_date: datetime
    last_date: datetime
    log_type: str


class LogViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Log Viewer")
        self.log_files = []

        self.create_widgets()
    
    def create_widgets(self):
        # Create status bar
        self.status_bar = tk.Label(self.root, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Create first row
        self.frame1 = tk.Frame(self.root)
        self.frame1.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.clear_button = tk.Button(self.frame1, text="Clear Log Files", command=self.clear_files)
        self.clear_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.draw_button = tk.Button(self.frame1, text="Draw Graph", command=self.draw_graph)
        self.draw_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Create second row
        self.frame2 = tk.Frame(self.root, height=100, bd=1, relief=tk.SUNKEN)
        self.frame2.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.frame2.drop_target_register(DND_FILES)
        self.frame2.dnd_bind('<<Drop>>', self.drop_files)

        # Create third row
        self.frame3 = tk.Frame(self.root)
        self.frame3.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        # Create sunken lines
        self.sunken_line1 = tk.Frame(self.frame3, height=2, bd=1, relief=tk.SUNKEN)
        self.sunken_line1.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)

        self.sunken_line2 = tk.Frame(self.frame3, height=2, bd=1, relief=tk.SUNKEN)
        self.sunken_line2.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        # First row in third frame
        self.possible_period_label = tk.Label(self.frame3, text="Possible Period")
        self.possible_period_label.grid(row=1, column=0, padx=5, pady=5)

        self.possible_period_value1 = tk.Label(self.frame3, text="")
        self.possible_period_value1.grid(row=1, column=1, padx=5, pady=5)

        self.possible_period_value2 = tk.Label(self.frame3, text="")
        self.possible_period_value2.grid(row=1, column=2, padx=5, pady=5)

        # Second row in third frame
        self.setting_period_label = tk.Label(self.frame3, text="Setting Period")
        self.setting_period_label.grid(row=3, column=0, padx=5, pady=5)

        self.setting_period_entry1 = tk.Entry(self.frame3)
        self.setting_period_entry1.grid(row=3, column=1, padx=5, pady=5)

        self.setting_period_entry2 = tk.Entry(self.frame3)
        self.setting_period_entry2.grid(row=3, column=2, padx=5, pady=5)

        # Scrollbars
        self.scrollbar1 = ttk.Scrollbar(self.frame3, orient="horizontal")
        self.scrollbar1.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        self.scrollbar2 = ttk.Scrollbar(self.frame3, orient="horizontal")
        self.scrollbar2.grid(row=5, column=2, padx=5, pady=5, sticky="ew")

    def clear_files(self):
        self.log_files.clear()
        self.manage_log_files()
        self.update_period()
        self.display_files()

    def drop_files(self, event):
        files = self.root.tk.splitlist(event.data)
        for file in files:
            logtype = self.check_file(file)
            if file not in self.log_files:
                logfile = LogFile(file, None, None, logtype)
                self.log_files.append(logfile)
        self.manage_log_files()
        self.update_period()
        self.display_files()

    def display_files(self):
        self.clear_file_display()

        for logfile in self.log_files:
            file_frame = tk.Frame(self.frame2)
            file_frame.pack(fill=tk.X, padx=5, pady=5)

            file_name = tk.Label(file_frame, text=logfile.file_path.split('/')[-1])
            file_name.pack(side=tk.LEFT, padx=5, pady=5)

            sunken_line1 = tk.Frame(file_frame, width=2, bd=1, relief=tk.SUNKEN)
            sunken_line1.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

            delete_button = tk.Button(file_frame, text="Delete", command=lambda f=logfile: self.delete_file(f))
            delete_button.pack(side=tk.RIGHT, padx=5, pady=5)

            sunken_line2 = tk.Frame(file_frame, width=2, bd=1, relief=tk.SUNKEN)
            sunken_line2.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

            file_path = tk.Label(file_frame, text=logfile.file_path)
            file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

    def delete_file(self, logfile):
        self.log_files.remove(logfile)
        self.manage_log_files()
        self.update_period()
        self.display_files()

    def clear_file_display(self):
        for widget in self.frame2.winfo_children():
            widget.destroy()

    def is_valid_pressure_level_log(self, log_line):
        pattern = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}: -?\d+\.\d{2} [VL], -?\d+\.\d{2} psi, -?\d+\.\d{2} psi$'
        return re.match(pattern, log_line) is not None

    def is_valid_flow_temperature_log(self, log_line):
        pattern = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}: -?\d+\.\d{2} L/min, -?\d+\.\d{2} L/min, -?\d+\.\d{2} L/min, -?\d+\.\d{2} K, -?\d+\.\d{2} K$'
        return re.match(pattern, log_line) is not None

    def check_file(self, file):
        # 로그 파일 형태를 잘 따르고 있는지 검사하는 함수.
        # 첫 번째 줄을 읽어서 Pressure & Level Log인지 Flow & Temperature Log인지 확인함.
        # 그리고 두 번째 줄부터는 데이터가 잘 들어있는지 확인함.
        # 데이터가 잘 들어있지 않으면 경고창을 띄우고, 파일을 불러오지 않음.
        try:
            with open(file, 'r') as f:
                first_line = f.readline().strip()
                if self.is_valid_pressure_level_log(first_line):
                    log_type = "Pressure & Level Log"
                elif self.is_valid_flow_temperature_log(first_line):
                    log_type = "Flow & Temperature Log"
                else:
                    raise ValueError("Invalid log file format")

                for line in f:
                    line = line.strip()
                    if log_type == "Pressure & Level Log":
                        if not self.is_valid_pressure_level_log(line):
                            raise ValueError("Invalid log file format")
                    elif log_type == "Flow & Temperature Log":
                        if not self.is_valid_flow_temperature_log(line):
                            raise ValueError("Invalid log file format")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file {file}: {e}")
            return None
        return log_type

    def manage_log_files(self):
        # 로그 파일의 첫번째 줄과 마지막 줄의 시간을 불러온 다음에, 이를 기준으로 로그파일들을 정렬함.
        # 정렬된 로그 파일들을 self.log_files에 저장함.
        if len(self.log_files) == 0:
            return
        
        for logfile in self.log_files:
            with open(logfile.file_path, 'r') as f:
                first_line = f.readline().strip()
                last_line = None
                for line in f:
                    last_line = line
                logfile.first_date = datetime.strptime(first_line.split(': ')[0], "%Y-%m-%d %H:%M:%S")
                logfile.last_date = datetime.strptime(last_line.split(': ')[0], "%Y-%m-%d %H:%M:%S")
        
        self.log_files = sorted(self.log_files, key=lambda x: x.first_date)

    def update_period(self):
        # 불러온 로그 파일들로부터 가장 빠른 날짜와 가장 늦은 날짜를 불러와서, 이를 표시함.
        if len(self.log_files) == 0:
            self.possible_period_value1.config(text="")
            self.possible_period_value2.config(text="")
            return
        
        first_date = None
        last_date = None
        for logfile in self.log_files:
            with open(logfile.file_path, 'r') as f:
                first_line = f.readline().strip()
                last_line = None
                for line in f:
                    last_line = line
                file_first_date = datetime.strptime(first_line.split(': ')[0], "%Y-%m-%d %H:%M:%S")
                file_last_date = datetime.strptime(last_line.split(': ')[0], "%Y-%m-%d %H:%M:%S")
                if first_date is None or file_first_date < first_date:
                    first_date = file_first_date
                if last_date is None or file_last_date > last_date:
                    last_date = file_last_date

        self.possible_period_value1.config(text=first_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.possible_period_value2.config(text=last_date.strftime("%Y-%m-%d %H:%M:%S"))

    def check_continuous_time(self):
        # 불러온 로그 파일들로부터 시간 부분이 연속적인지 확인함.
        # 연속의 기준은 5분 이내로 정함.
        if len(self.log_files) == 0:
            return
        
        prev_date = None
        for logfile in self.log_files:
            with open(logfile.file_path, 'r') as f:
                for line in f:
                    date = datetime.strptime(line.split(': ')[0], "%Y-%m-%d %H:%M:%S")
                    if prev_date is not None and date - prev_date > timedelta(minutes=5):
                        self.status_bar.config(text=f"Status: Non-continuous time detected at {logfile}")
                        return False
                    prev_date = date
        self.status_bar.config(text="")
        return True

    def only_pressure_level_log(self):
        for logfile in self.log_files:
            if logfile.log_type != "Pressure & Level Log":
                return False
        return True

    def only_flow_temperature_log(self):
        for logfile in self.log_files:
            if logfile.log_type != "Flow & Temperature Log":
                return False
        return True

    def draw_graph(self):
        # 그래프를 그리는 함수.
        # 다음 조건에 따라 행동이 달라짐.

        # 1. 하나의 파일을 올린 경우는 그냥 보여주면 됨.
        # 2. 두 개 이상의 파일을 올린 경우는 다음과 같이 처리함.
        # 2-1. 시간에 대해서
        # 2-1-1. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 있는 경우 해당 데이터를 붙여서 그래프를 그림.
        # 2-1-2. 시간에 대해서 연속된 날짜이면서, 연속된 시간의 데이터가 없는 경우 경고를 날리고, 해당 데이터를 붙여서 그래프를 그림.
            # 이를 위해서는 연속된 시간이라는 것을 정의해야하는데, 이는 5분 이내의 차이로 정의함.
        # 2-2. 데이터에 대해서
        # 2-2-1. Pressure & Level Log만 올린 경우 Pressure & Level Log를 그림.
        # 2-2-2. Flow & Temperature Log만 올린 경우 Flow & Temperature Log를 그림.
        # 2-2-3. 둘 다 올린 경우 위에는 Pressure & Level Log를, 아래는 Flow & Temperature Log를 그림.

        if len(self.log_files) == 0:
            return
        
        is_continuous = self.check_continuous_time()
        if not is_continuous:
            MsgBox = messagebox.showinfo("Warning", "Non-continuous time detected. Maybe some data is missing.")
        
        if len(self.log_files) == 1:
            if self.log_files[0].log_type == "Pressure & Level Log":
                self.draw_pressure_level_graph()
            elif self.log_files[0].log_type == "Flow & Temperature Log":
                self.draw_flow_temperature_graph()
            else:
                return
        else:
            if self.only_pressure_level_log(): # Pressure & Level Log만 올린 경우
                self.draw_pressure_level_graph()
            elif self.only_flow_temperature_log(): # Flow & Temperature Log만 올린 경우
                self.draw_flow_temperature_graph()
            else: # 둘 다 올린 경우
                self.draw_multiple_mixed_graph()

    def draw_pressure_level_graph(self):
        datetimes = []
        volume = []
        plant_pressure = []
        storage_pressure = []

        for logfile in self.log_files:
            with open(logfile.file_path, 'r') as f:
                for line in f:
                    date, data = line.split(': ')
                    level, pressure1, pressure2 = data.split(', ')
                    datetimes.append(datetime.strptime(date, "%Y-%m-%d %H:%M:%S"))
                    volume.append(float(level.split()[0]))
                    plant_pressure.append(float(pressure1.split()[0]))
                    storage_pressure.append(float(pressure2.split()[0]))
        
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        ax1.plot(datetimes, volume, 'b-', label='Volume')
        ax2.plot(datetimes, plant_pressure, 'g-', label=f'P_plant')
        ax2.plot(datetimes, storage_pressure, 'r-', label=f'P_storage')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Volume')
        ax2.set_ylabel('Pressure', color='r')
        ax1.legend(loc='lower left')
        ax2.legend(loc='lower right')
        ax1.grid()
        ax2.grid(color='r')
        plt.show()

    def draw_flow_temperature_graph(self):
        datetimes = []
        tip_flow = []
        shield_flow = []
        bypass_flow = []
        head_temperature = []
        coldtip_temperature = []

        for logfile in self.log_files:
            with open(logfile.file_path, 'r') as f:
                for line in f:
                    date, data = line.split(': ')
                    flow1, flow2, flow3, temperature1, temperature2 = data.split(', ')
                    datetimes.append(datetime.strptime(date, "%Y-%m-%d %H:%M:%S"))
                    tip_flow.append(float(flow1.split()[0]))
                    shield_flow.append(float(flow2.split()[0]))
                    bypass_flow.append(float(flow3.split()[0]))
                    head_temperature.append(float(temperature1.split()[0]))
                    coldtip_temperature.append(float(temperature2.split()[0]))
        
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        ax1.plot(datetimes, tip_flow, 'g-', label='Tip Flow')
        ax1.plot(datetimes, shield_flow, 'b-', label='Shield Flow')
        ax1.plot(datetimes, bypass_flow, 'p-', label='Bypass Flow')
        ax2.plot(datetimes, head_temperature, 'r-', label='Head Temperature')
        ax2.plot(datetimes, coldtip_temperature, 'y-', label='Coldtip Temperature')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Flow (L/min)')
        ax2.set_ylabel('Temperature (K)', color='r')
        ax1.legend(loc='lower left')
        ax2.legend(loc='lower right')
        ax1.grid()
        ax2.grid(color='r')
        plt.show()

    def draw_multiple_mixed_graph(self):
        datetimes_pressurelevel = []
        volume = []
        plant_pressure = []
        storage_pressure = []

        datetimes_flowtemp = []
        tip_flow = []
        shield_flow = []
        bypass_flow = []
        head_temperature = []
        coldtip_temperature = []

        for logfile in self.log_files:
            if logfile.log_type == "Pressure & Level Log":
                with open(logfile.file_path, 'r') as f:
                    for line in f:
                        date, data = line.split(': ')
                        level, pressure1, pressure2 = data.split(', ')
                        datetimes_pressurelevel.append(datetime.strptime(date, "%Y-%m-%d %H:%M:%S"))
                        volume.append(float(level.split()[0]))
                        plant_pressure.append(float(pressure1.split()[0]))
                        storage_pressure.append(float(pressure2.split()[0]))
            elif logfile.log_type == "Flow & Temperature Log":
                with open(logfile.file_path, 'r') as f:
                    for line in f:
                        date, data = line.split(': ')
                        flow1, flow2, flow3, temperature1, temperature2 = data.split(', ')
                        datetimes_flowtemp.append(datetime.strptime(date, "%Y-%m-%d %H:%M:%S"))
                        tip_flow.append(float(flow1.split()[0]))
                        shield_flow.append(float(flow2.split()[0]))
                        bypass_flow.append(float(flow3.split()[0]))
                        head_temperature.append(float(temperature1.split()[0]))
                        coldtip_temperature.append(float(temperature2.split()[0]))
        
        fig, ax = plt.subplots(2, 1)
        ax1 = ax[0]
        ax2 = ax[1]
        ax3 = ax1.twinx()
        ax4 = ax2.twinx()

        ax1.plot(datetimes_pressurelevel, volume, 'b-', label='Volume')
        ax3.plot(datetimes_pressurelevel, plant_pressure, 'g-', label=f'P_plant')
        ax3.plot(datetimes_pressurelevel, storage_pressure, 'r-', label=f'P_storage')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Volume')
        ax3.set_ylabel('Pressure', color='r')
        ax1.legend(loc='lower left')
        ax3.legend(loc='lower right')
        ax1.grid()
        ax3.grid(color='r')

        ax2.plot(datetimes_flowtemp, tip_flow, 'g-', label='Tip Flow')
        ax2.plot(datetimes_flowtemp, shield_flow, 'b-', label='Shield Flow')
        ax2.plot(datetimes_flowtemp, bypass_flow, 'p-', label='Bypass Flow')
        ax4.plot(datetimes_flowtemp, head_temperature, 'r-', label='Head Temperature')
        ax4.plot(datetimes_flowtemp, coldtip_temperature, 'y-', label='Coldtip Temperature')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Flow (L/min)')
        ax4.set_ylabel('Temperature (K)', color='r')
        ax2.legend(loc='lower left')
        ax4.legend(loc='lower right')
        ax2.grid()
        ax4.grid(color='r')
        plt.show()



if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = LogViewer(root)
    root.mainloop()