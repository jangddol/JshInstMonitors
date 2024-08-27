import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import requests
import time
from collections import deque
from datetime import datetime, timedelta
import matplotlib.dates as mdates
import threading
import matplotlib.ticker as ticker

from CustomDateLocator import CustomDateLocator

MAXLEN = 100

class VariousTimeDeque:
    def __init__(self, numdata):
        self.numdata = numdata
        self.time_1s = deque(maxlen=MAXLEN)
        self.data_1s = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1min = deque(maxlen=MAXLEN)
        self.data_1min = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_10min = deque(maxlen=MAXLEN)
        self.data_10min = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1hour = deque(maxlen=MAXLEN)
        self.data_1hour = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        
    def update_data(self, data, time):
        if len(data) != self.numdata:
            raise ValueError("Data length mismatch")
        
        if isinstance(time, datetime):
            _time = time
        elif isinstance(time, float):
            _time = datetime.fromtimestamp(time)
        else:
            raise ValueError("Invalid time type")

        self.time_1s.append(_time)
        for i in range(self.numdata):
            self.data_1s[i].append(data[i])
        
        if len(self.time_1min) == 0 or _time - self.time_1min[-1] >= timedelta(minutes=1):
            self.time_1min.append(_time)
            for i in range(self.numdata):
                self.data_1min[i].append(data[i])
        
        if len(self.time_10min) == 0 or _time - self.time_10min[-1] >= timedelta(minutes=10):
            self.time_10min.append(_time)
            for i in range(self.numdata):
                self.data_10min[i].append(data[i])
        
        if len(self.time_1hour) == 0 or _time - self.time_1hour[-1] >= timedelta(hours=1):
            self.time_1hour.append(_time)
            for i in range(self.numdata):
                self.data_1hour[i].append(data[i])

class TotalPlotter:
    def __init__(self, master):
        self.master = master
        self.master.title("Total Plotter")
        self.master.bind("<Configure>", self.on_resize)
        self.width = 800  # Default width
        
        # Create UI components
        self.create_widgets()

        # Deques for storing values
        self.time_rfm_1s: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_rfm_1s: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(3)]
        self.time_drc91c_1s: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_drc91c_1s:list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(2)]
        
        self.time_rfm_1s.append(datetime.fromtimestamp(time.time()))
        for i in range(3):
            self.data_rfm_1s[i].append(0)
        self.time_drc91c_1s.append(datetime.fromtimestamp(time.time()))
        for i in range(2):
            self.data_drc91c_1s[i].append(0)
        
        self.time_rfm_1min: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_rfm_1min: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(3)]
        self.time_drc91c_1min: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_drc91c_1min: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(2)]
        
        self.time_rfm_10min: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_rfm_10min: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(3)]
        self.time_drc91c_10min: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_drc91c_10min: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(2)]
        
        self.time_rfm_1hour: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_rfm_1hour: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(3)]
        self.time_drc91c_1hour: deque[datetime] = deque(maxlen=MAXLEN)
        self.data_drc91c_1hour: list[deque[float]] = [deque(maxlen=MAXLEN) for _ in range(2)]

        self.time_rfm_plot = self.time_rfm_1s
        self.data_rfm_plot = self.data_rfm_1s
        self.time_drc91c_plot = self.time_drc91c_1s
        self.data_drc91c_plot = self.data_drc91c_1s

        # Start the data fetching thread
        self.last_fetch_time = time.time()
        self.last_1min_time = time.time()
        self.last_10min_time = time.time()
        self.last_1hour_time = time.time()
        
        self.rfm_status_code = None
        self.drc91c_status_code = None
        
        self.set_test_data()
        
        self.update_interval(None)
        self.main_loop()
        
    def create_widgets(self):
        # Top frame
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # IntVar를 사용하여 체크박스 상태를 저장
        self.enable_rfm = tk.IntVar()
        self.enable_drc91c = tk.IntVar()

        self.checkbox_rfm = tk.Checkbutton(self.top_frame, text="Enable RFM", variable=self.enable_rfm, command=self.update_plot)
        self.checkbox_rfm.pack(side=tk.LEFT)

        self.checkbox_drc91c = tk.Checkbutton(self.top_frame, text="Enable DRC91C", variable=self.enable_drc91c, command=self.update_plot)
        self.checkbox_drc91c.pack(side=tk.LEFT)

        self.interval_label = tk.Label(self.top_frame, text="Interval:")
        self.interval_label.pack(side=tk.LEFT)

        self.interval_combo = ttk.Combobox(self.top_frame, values=["1 s", "1 min", "10 min", "1 hour"])
        self.interval_combo.current(0)  # Default to 1 s
        self.interval_combo.pack(side=tk.LEFT)
        self.interval_combo.bind("<<ComboboxSelected>>", self.update_interval)
        
        # Bottom frame
        self.bottom_frame = tk.Frame(self.master)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Left canvas for plotting
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.bottom_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        self.ax2 = self.ax.twinx()
        
        # Right frame for displaying values and status
        self.right_frame = tk.Frame(self.bottom_frame, width=150)  # Fixed width for right_frame
        self.right_frame.grid(row=0, column=1, sticky='nsew')

        # Data frame
        self.data_frame = tk.Frame(self.right_frame)
        self.data_frame.pack(side=tk.TOP, fill=tk.Y)

        self.tip_data_label = self.create_value_labels("• Tip", "L/min", self.data_frame, 0)
        self.shield_data_label = self.create_value_labels("• Shield", "L/min", self.data_frame, 1)
        self.vent_data_label = self.create_value_labels("• Vent", "L/min", self.data_frame, 2)
        self.head_data_label = self.create_value_labels("• Head", "K", self.data_frame, 3)
        self.cold_tip_data_label = self.create_value_labels("• Cold Tip", "K", self.data_frame, 4)

        # Status frame
        self.status_frame = tk.Frame(self.right_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.Y)

        self.current_time_label = self.create_value_labels("Current Time", "", self.status_frame, 0)
        self.rfm_status_label = self.create_value_labels("RFM stat", "", self.status_frame, 1)
        self.drc91c_status_label = self.create_value_labels("DRC91C stat", "", self.status_frame, 2)

        # Configure grid weights to maintain aspect ratio
        self.bottom_frame.grid_columnconfigure(0, weight=1)  # Canvas takes remaining space
        self.bottom_frame.grid_columnconfigure(1, weight=0)  # Right frame has fixed width
        self.bottom_frame.grid_rowconfigure(0, weight=1)     # Allow row to expand
    
    def create_value_labels(self, name, unit, frame, row):
        name_label = tk.Label(frame, text=f"{name}")
        name_label.grid(row=row, column=0, sticky='w', padx=(0, 5), pady=2)
        
        value_label = tk.Label(frame, text=f": 0.00 {unit}")
        value_label.grid(row=row, column=1, sticky='w', pady=2)
        
        return value_label
    
    def on_resize(self, event):
        # Get the new width of the window
        self.width = event.width

    def update_interval(self, event):
        interval = self.get_interval()
        if interval == 1:
            self.time_rfm_plot = self.time_rfm_1s
            self.data_rfm_plot = self.data_rfm_1s
            self.time_drc91c_plot = self.time_drc91c_1s
            self.data_drc91c_plot = self.data_drc91c_1s
        elif interval == 60:
            self.time_rfm_plot = self.time_rfm_1min
            self.data_rfm_plot = self.data_rfm_1min
            self.time_drc91c_plot = self.time_drc91c_1min
            self.data_drc91c_plot = self.data_drc91c_1min
        elif interval == 600:
            self.time_rfm_plot = self.time_rfm_10min
            self.data_rfm_plot = self.data_rfm_10min
            self.time_drc91c_plot = self.time_drc91c_10min
            self.data_drc91c_plot = self.data_drc91c_10min
        elif interval == 3600:
            self.time_rfm_plot = self.time_rfm_1hour
            self.data_rfm_plot = self.data_rfm_1hour
            self.time_drc91c_plot = self.time_drc91c_1hour
            self.data_drc91c_plot = self.data_drc91c_1hour
        
        if len(self.time_rfm_plot) <= 2:
            return
        self.update_plot()
    
    def fetch_loop(self):
        self.fetch_data()
        self.update_data()
        self.master.after(1000, self.fetch_loop)
    
    def main_loop(self):
        if time.time() - self.last_fetch_time > 1:
            self.last_fetch_time = time.time()
            self.update_display()
            if self.get_interval() == 1:
                self.update_plot()
        if time.time() - self.last_1min_time > 60:
            self.last_1min_time = time.time()
            # self.update_1min_data()
            if self.get_interval() == 60:
                self.update_plot()
        if time.time() - self.last_10min_time > 600:
            self.last_10min_time = time.time()
            # self.update_10min_data()
            if self.get_interval() == 600:
                self.update_plot()
        if time.time() - self.last_1hour_time > 3600:
            self.last_1hour_time = time.time()
            # self.update_1hour_data()
            if self.get_interval() == 3600:
                self.update_plot()
        # Call this method again after 1 second
        self.master.after(1000, self.main_loop)

    def start(self):
        self.data_fetch_thread = threading.Thread(target=self.fetch_loop)
        self.data_fetch_thread.start()

    def update_data(self):
        last_1s_data_time = self.time_rfm_1s[-1].timestamp()
        last_1min_data_time = self.time_rfm_1min[-1].timestamp()
        last_10min_data_time = self.time_rfm_10min[-1].timestamp()
        last_1hour_data_time = self.time_rfm_1hour[-1].timestamp()
        if last_1s_data_time - last_1min_data_time > 60:
            self.update_1min_data()
        if last_1s_data_time - last_10min_data_time > 600:
            self.update_10min_data()
        if last_1s_data_time - last_1hour_data_time > 3600:
            self.update_1hour_data()

    def update_1min_data(self):
        self.time_rfm_1min.append(self.time_rfm_1s[-1])
        for i in range(3):
            self.data_rfm_1min[i].append(self.data_rfm_1s[i][-1])
        self.time_drc91c_1min.append(self.time_drc91c_1s[-1])
        for i in range(2):
            self.data_drc91c_1min[i].append(self.data_drc91c_1s[i][-1])
    
    def update_10min_data(self):
        self.time_rfm_10min.append(self.time_rfm_1s[-1])
        for i in range(3):
            self.data_rfm_10min[i].append(self.data_rfm_1s[i][-1])
        self.time_drc91c_10min.append(self.time_drc91c_1s[-1])
        for i in range(2):
            self.data_drc91c_10min[i].append(self.data_drc91c_1s[i][-1])
    
    def update_1hour_data(self):
        self.time_rfm_1hour.append(self.time_rfm_1s[-1])
        for i in range(3):
            self.data_rfm_1hour[i].append(self.data_rfm_1s[i][-1])
        self.time_drc91c_1hour.append(self.time_drc91c_1s[-1])
        for i in range(2):
            self.data_drc91c_1hour[i].append(self.data_drc91c_1s[i][-1])

    def parse_temperature(self, value: str) -> float:
        return float(value[1:7])

    def get_data_from_rfm(self):
        # Fetch data from RFM local server daemon
        if self.enable_rfm.get() == 0:
            self.rfm_status_code = 'Off'
            return [0, 0, 0]
        try:
            response = requests.get("http://127.0.0.1:5000/get_value", timeout=1)
            self.rfm_status_code = response.status_code
            if response.status_code == 200:
                json = response.json()
                list_of_str = [json['Tip'], json['Shield'], json['Vent']]
                return [float(x) for x in list_of_str]
            else:
                print(f"Error fetching from RFM: {response.status_code}")
                return [0, 0, 0]
        except requests.exceptions.ConnectionError as e:
            self.rfm_status_code = 'ConnectionError'
            print(f"Connection error fetching from RFM: {e}")
        except requests.exceptions.Timeout as e:
            self.rfm_status_code = 'Timeout'
            print(f"Timeout error fetching from RFM: {e}")
        except requests.exceptions.HTTPError as e:
            self.rfm_status_code = 'HTTPError'
            print(f"HTTP error fetching from RFM: {e}")
        except requests.exceptions.RequestException as e:
            self.rfm_status_code = 'RequestException'
            print(f"General error fetching from RFM: {e}")
        except Exception as e:
            self.rfm_status_code = 'Critical'
            print(f"Critical error fetching from RFM: {e}")
        return [0, 0, 0]

    def get_data_from_drc91c(self):
        # Fetch data from DRC91C local server daemon
        if self.enable_drc91c.get() == 0:
            self.drc91c_status_code = 'Off'
            return [0, 0]
        try:
            response = requests.get("http://127.0.0.1:5001/sensor_pair", timeout=1)
            self.drc91c_status_code = response.status_code
            if response.status_code == 200:
                json = response.json()
                list_of_str = [json['valueA'], json['valueB']]
                return [self.parse_temperature(x) for x in list_of_str]
            else:
                print(f"Error fetching from DRC91C: {response.status_code}")
                return [0, 0]
        except requests.exceptions.ConnectionError as e:
            self.drc91c_status_code = 'ConnectionError'
            print(f"Connection error fetching from RFM: {e}")
        except requests.exceptions.Timeout as e:
            self.drc91c_status_code = 'Timeout'
            print(f"Timeout error fetching from RFM: {e}")
        except requests.exceptions.HTTPError as e:
            self.drc91c_status_code = 'HTTPError'
            print(f"HTTP error fetching from RFM: {e}")
        except requests.exceptions.RequestException as e:
            self.drc91c_status_code = 'RequestException'
            print(f"General error fetching from RFM: {e}")
        except Exception as e:
            self.drc91c_status_code = 'Critical'
            print(f"Critical error fetching from RFM: {e}")
        return [0, 0, 0]

    def fetch_data(self):
        values_rfm = self.get_data_from_rfm()
        for i in range(3):
            self.data_rfm_1s[i].append(values_rfm[i])
        self.time_rfm_1s.append(datetime.fromtimestamp(time.time()))

        values_drc91c = self.get_data_from_drc91c()
        for i in range(2):
            self.data_drc91c_1s[i].append(values_drc91c[i])
        self.time_drc91c_1s.append(datetime.fromtimestamp(time.time()))

    def get_interval(self):
        interval_str = self.interval_combo.get()
        if interval_str == "1 s":
            return 1
        elif interval_str == "1 min":
            return 60
        elif interval_str == "10 min":
            return 600
        elif interval_str == "1 hour":
            return 3600
        return 1

    def make_error_sentence(self, error_code):
        try:
            error_code = int(error_code)
            return f": Err({error_code})"
        except ValueError:
            return f": {error_code}"

    def update_display(self):
        self.tip_data_label.config(text=f": {self.data_rfm_1s[0][-1]:.2f} L/min")
        self.shield_data_label.config(text=f": {self.data_rfm_1s[1][-1]:.2f} L/min")
        self.vent_data_label.config(text=f": {self.data_rfm_1s[2][-1]:.2f} L/min")
        self.head_data_label.config(text=f": {self.data_drc91c_1s[0][-1]:.2f} K")
        self.cold_tip_data_label.config(text=f": {self.data_drc91c_1s[1][-1]:.2f} K")
        self.current_time_label.config(text=f": {datetime.now().strftime('%H:%M:%S')}")
        self.rfm_status_label.config(text=f"{': Connected' if self.rfm_status_code == 200 else self.make_error_sentence(self.rfm_status_code)}")
        self.drc91c_status_label.config(text=f"{': Connected' if self.drc91c_status_code == 200 else self.make_error_sentence(self.drc91c_status_code)}")
    
    def update_plot(self):
        if len(self.time_rfm_plot) <= 2:
            return
        
        self.ax.clear()
        self.ax2.clear()
        
        marker_size = 3
        
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[0], marker='o', color='green', label="Tip", markersize=marker_size)
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[1], marker='o', color='blue', label="Shield", markersize=marker_size)
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[2], marker='o', color='purple', label="Vent", markersize=marker_size)
        
        self.ax2.plot(self.time_drc91c_plot, self.data_drc91c_plot[0], marker='o', color='red', label="Head", markersize=marker_size)
        self.ax2.plot(self.time_drc91c_plot, self.data_drc91c_plot[1], marker='o', color='orange', label="Cold Tip", markersize=marker_size)
        
        ax2_color = 'red'
        
        self.ax.set_xlabel("")
        self.ax.set_ylabel("Flow Rate (L/min)")
        self.ax2.set_ylabel("Temperature (K)", color=ax2_color)
        
        # y축 레이블 위치 조정
        self.ax2.yaxis.set_label_position("right")  # y축 레이블을 오른쪽으로 이동
        self.ax2.yaxis.tick_right()  # y축 눈금을 오른쪽으로 이동
    
        # y축 최소값을 0으로 설정
        if self.ax.get_ylim()[0] < 0:
            self.ax.set_ylim(bottom=0)  # RFM Plot의 y축 최소값을 0으로 설정
        if self.ax2.get_ylim()[0] < 0:
            self.ax2.set_ylim(bottom=0)  # DRC91C Plot의 y축 최소값을 0으로 설정 (필요한 경우)
    
        # 그리드 추가
        self.ax.grid(True)  # RFM Plot에 그리드 추가
        self.ax2.grid(color=ax2_color)  # DRC91C Plot에 그리드 추가
    
        # ax2의 y축 색상을 변경
        self.ax2.tick_params(axis='y', colors=ax2_color)

        self.ax.relim()
        self.ax.autoscale_view()
        
        self.ax.legend(loc='lower left')  # RFM Plot의 legend를 오른쪽 위로 이동
        self.ax2.legend(loc='lower right')  # DRC91C Plot의 legend를 오른쪽 중앙으로 이동
        
        # x축 눈금 글자 대각선으로 회전
        for label in self.ax.get_xticklabels():
            label.set_rotation(30)  # 30도 회전
            label.set_horizontalalignment('right')  # 오른쪽 정렬
        
        self.update_xformatter(self.get_interval())
        self.resize_figure()
        self.canvas.draw()

    def resize_figure(self):
        # Adjust font size based on the new width
        new_font_size = max(8, self.width // 75)  # Adjust the divisor as needed
        
        plt.rcParams.update({
            'font.size': new_font_size,
            'axes.labelsize': new_font_size,
            'axes.titlesize': new_font_size,
            'xtick.labelsize': new_font_size * 0.8,
            'ytick.labelsize': new_font_size * 0.8,
            'legend.fontsize': new_font_size * 0.9,
        })

        # Adjust padding
        self.ax.margins(x=0.1, y=0.5)  # Adjust margins as needed
        self.ax2.margins(x=0.1, y=0.5)  # Adjust margins as needed
        self.figure.tight_layout(pad=1.0)  # Adjust padding as needed

    def update_xformatter(self, interval):
        def format_date(x, pos=None):
            date = mdates.num2date(x)
            if interval == 1:
                return date.strftime("%H:%M:%S")
            elif interval == 3600:
                return date.strftime("%m-%d %H:%M")
            else:
                return date.strftime("%H:%M")

        locator = CustomDateLocator(interval)
        formatter = ticker.FuncFormatter(format_date)
        
        self.ax.xaxis.set_major_locator(locator)
        self.ax.xaxis.set_major_formatter(formatter)
        
        self.figure.autofmt_xdate()

    def set_test_data(self):
        start_time = time.time() - MAXLEN * 3600
        for i in range(MAXLEN):
            self.data_rfm_1s[0].append(0.5)
            self.data_rfm_1s[1].append(0.3)
            self.data_rfm_1s[2].append(0.7)
            self.data_drc91c_1s[0].append(300)
            self.data_drc91c_1s[1].append(400)
            self.data_rfm_1min[0].append(0.5)
            self.data_rfm_1min[1].append(0.3)
            self.data_rfm_1min[2].append(0.7)
            self.data_drc91c_1min[0].append(300)
            self.data_drc91c_1min[1].append(400)
            self.data_rfm_10min[0].append(0.5)
            self.data_rfm_10min[1].append(0.3)
            self.data_rfm_10min[2].append(0.7)
            self.data_drc91c_10min[0].append(300)
            self.data_drc91c_10min[1].append(400)
            self.data_rfm_1hour[0].append(0.5)
            self.data_rfm_1hour[1].append(0.3)
            self.data_rfm_1hour[2].append(0.7)
            self.data_drc91c_1hour[0].append(300)
            self.data_drc91c_1hour[1].append(400)
            
        for i in range(MAXLEN * 3600):
            self.time_rfm_1s.append(datetime.fromtimestamp(start_time + i))
            self.time_drc91c_1s.append(datetime.fromtimestamp(start_time + i))
            if i % 60 == 0:
                self.time_rfm_1min.append(datetime.fromtimestamp(start_time + i))
                self.time_drc91c_1min.append(datetime.fromtimestamp(start_time + i))
            if i % 600 == 0:
                self.time_rfm_10min.append(datetime.fromtimestamp(start_time + i))
                self.time_drc91c_10min.append(datetime.fromtimestamp(start_time + i))
            if i % 3600 == 0:
                self.time_rfm_1hour.append(datetime.fromtimestamp(start_time + i))
                self.time_drc91c_1hour.append(datetime.fromtimestamp(start_time + i))

if __name__ == "__main__":
    root = tk.Tk()
    root.iconbitmap("TotalPlotter.ico")
    app = TotalPlotter(root)
    app.start()
    root.mainloop()
