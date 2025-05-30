from datetime import datetime
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import requests
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from CustomDateLocator import CustomDateLocator
from PressureLevelSetting import PressureLevelSetting
from VariousTimeDeque import VariousTimeDeque
from CustomMail import send_mail

MAXLEN = 100


class PressureLevelPlotter:
    def __init__(self, master):
        self.master = master
        self.master.title("Pressure & Level Plotter")
        self.master.bind("<Configure>", self.on_resize)
        self.width = 800  # Default width

        # Create UI components
        self.create_widgets()

        # Deques for storing values
        self.arduino_deque = VariousTimeDeque(4) # 0: P_st, 1: P_pl, 2: V_pl, 3: P_pr

        self.time_arduino_plot = self.arduino_deque.get_time_deque(1)
        self.data_arduino_plot = self.arduino_deque.get_data_deque(1)

        self.arduino_status_code = "Off"

        self.update_interval(None)
        self.main_loop()

    def create_widgets(self):
        # Top frame
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # IntVar를 사용하여 체크박스 상태를 저장
        self.enable_arduino = tk.IntVar()
        self.enable_localmaxmin = tk.IntVar()

        self.checkbox_arduino = tk.Checkbutton(self.top_frame, text="Enable Arduino", variable=self.enable_arduino, command=self.update_plot)
        self.checkbox_arduino.pack(side=tk.LEFT)

        self.checkbox_localmaxmin = tk.Checkbutton(self.top_frame, text="Local Max/Min", variable=self.enable_localmaxmin, command=self.update_plot)
        self.checkbox_localmaxmin.pack(side=tk.LEFT)

        self.interval_label = tk.Label(self.top_frame, text="Interval:")
        self.interval_label.pack(side=tk.LEFT)

        self.interval_combo = ttk.Combobox(self.top_frame, values=["1 s", "1 min", "10 min", "1 hour"])
        self.interval_combo.current(0)  # Default to 1 s
        self.interval_combo.pack(side=tk.LEFT)
        self.interval_combo.bind("<<ComboboxSelected>>", self.update_interval)

        self.setting_button = tk.Button(self.top_frame, text="Setting", command=self.open_setting)
        self.setting_button.pack(side=tk.RIGHT)

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

        self.label_name_unit_pairs = [
            ("• V_plant", "L"),
            ("• P_plant", "psi"),
            ("• P_storage", "psi"),
            ("• P_purifier", "psi")]
        self.name_labels = []
        self.value_labels = []
        for i, (name, unit) in enumerate(self.label_name_unit_pairs):
            name_label, value_label = self.create_value_labels(name, unit, self.data_frame, i)
            self.name_labels.append(name_label)
            self.value_labels.append(value_label)
        self.last_positions = [0, 1, 2, 3]

        # Status frame
        self.status_frame = tk.Frame(self.right_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.Y)

        self.current_time_label = self.create_value_labels("Current Time", "", self.status_frame, 0)[1]
        self.arduino_status_label = self.create_value_labels("Arduino stat", "", self.status_frame, 1)[1]

        # Configure grid weights to maintain aspect ratio
        self.bottom_frame.grid_columnconfigure(0, weight=1)  # Canvas takes remaining space
        self.bottom_frame.grid_columnconfigure(1, weight=0)  # Right frame has fixed width
        self.bottom_frame.grid_rowconfigure(0, weight=1)     # Allow row to expand

    def create_value_labels(self, name, unit, frame, row):
        name_label = tk.Label(frame, text=f"{name}")
        name_label.grid(row=row, column=0, sticky='w', padx=(0, 5), pady=2)

        value_label = tk.Label(frame, text=f": 0.00 {unit}")
        value_label.grid(row=row, column=1, sticky='w', pady=2)

        return [name_label, value_label]
    
    def on_resize(self, event):
        # Get the new width of the window
        self.last_width = self.width
        self.width = event.width
        if self.last_width != self.width:
            self.resize_figure()

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

        self.figure.tight_layout(pad=1.0)

    def update_interval(self, event):
        interval = self.get_interval()
        self.time_arduino_plot = self.arduino_deque.get_time_deque(interval)
        self.data_arduino_plot = self.arduino_deque.get_data_deque(interval)

        if len(self.time_arduino_plot) <= 2:
            return
        self.update_plot()

    def main_loop(self):
        loop_start_time = time.time()

        self.update_display()

        expected_exc_delay = 0.2
        if loop_start_time - self.arduino_deque.get_last_time().timestamp() < expected_exc_delay:
            if self.get_interval() == 1:
                self.update_plot()

        if loop_start_time - self.arduino_deque.get_last_1min_time().timestamp() < expected_exc_delay:
            if self.get_interval() == 60:
                self.update_plot()
            self.save_log(self.arduino_deque.get_last_1min_time(), self.arduino_deque.get_last_data())

        if loop_start_time - self.arduino_deque.get_last_10min_time().timestamp() < expected_exc_delay:
            if self.get_interval() == 600:
                self.update_plot()
            if self.arduino_status_code != 200 and self.enable_arduino.get():
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                subject = f"{date_str} Arduino is disconnected."
                contents = f"Plz check the Arduino. Arduino is disconnected at {date_str}."
                send_mail(subject, contents)
            if self.arduino_deque.get_last_data()[1] > 3.0 or self.arduino_deque.get_last_data()[0] > 9.0:
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                subject = f"{date_str} Pressure is too high."
                contents = f"Plz check the Pressure. Pressure is too high at {date_str}."
                send_mail(subject, contents)

        if loop_start_time - self.arduino_deque.get_last_1hour_time().timestamp() < expected_exc_delay:
            if self.get_interval() == 3600:
                self.update_plot()

        loop_end_time = time.time()
        execution_time = loop_end_time - loop_start_time

        # Calculate the time to wait before the next execution
        next_execution_delay = max(0, int((expected_exc_delay - execution_time) * 1000))

        self.master.after(next_execution_delay, self.main_loop)

    def fetch_loop(self):
        while True:
            loop_start_time = time.time()

            self.fetch_data()

            elapsed_time = time.time() - loop_start_time
            sleep_time = max(0, 1 - elapsed_time)

            time.sleep(sleep_time)

    def start(self):
        self.data_fetch_thread = threading.Thread(target=self.fetch_loop)
        self.data_fetch_thread.daemon = True
        self.data_fetch_thread.start()

    def get_data_from_arduino(self):
        # Fetch data from Arduino local server daemon
        if self.enable_arduino.get() == 0:
            self.arduino_status_code = 'Off'
            return [0, 0, 0, 0]
        try:
            response = requests.get("http://127.0.0.1:5003/Meas", timeout=1)
            self.arduino_status_code = response.status_code
            if response.status_code != 200:
                print(f"Error fetching from Arduino: {response.status_code}")
                return [0, 0, 0, 0]

            json = response.json()

            if time.time() - json['timestamp'] > 5:
                self.arduino_status_code = 'DataTooOld'
                print("Data is too old")
                return [0, 0, 0, 0]

            list_of_str = [json['P_st'], json['P_pl'], json['V_pl'], json['P_pur']]
            return [float(x.split(' ')[0]) for x in list_of_str]
        except requests.exceptions.ConnectionError as e:
            self.arduino_status_code = 'ConnectionError'
            print(f"Connection error fetching from Storage: {e}")
        except requests.exceptions.Timeout as e:
            self.arduino_status_code = 'Timeout'
            print(f"Timeout error fetching from Storage: {e}")
        except requests.exceptions.HTTPError as e:
            self.arduino_status_code = 'HTTPError'
            print(f"HTTP error fetching from Storage: {e}")
        except requests.exceptions.RequestException as e:
            self.arduino_status_code = 'RequestException'
            print(f"General error fetching from Storage: {e}")
        except Exception as e:
            self.arduino_status_code = 'Critical'
            print(f"Critical error fetching from Storage: {e}")
        return [0, 0, 0, 0]

    def fetch_data(self):
        values_arduino = self.get_data_from_arduino()
        self.arduino_deque.update_data(values_arduino, time.time())

    def get_interval(self):
        interval_str = self.interval_combo.get()
        if interval_str == "1 s":
            return 1
        if interval_str == "1 min":
            return 60
        if interval_str == "10 min":
            return 600
        if interval_str == "1 hour":
            return 3600
        return 1

    def make_error_sentence(self, error_code):
        try:
            error_code = int(error_code)
            return f": Err({error_code})"
        except ValueError:
            return f": {error_code}"

    def update_display(self):
        data_order = [2, 1, 0, 3]
        for i, position in enumerate(self.last_positions):
            self.name_labels[i].config(text=self.label_name_unit_pairs[position][0])
            self.value_labels[i].config(text=f": {self.arduino_deque.get_last_data()[data_order[position]]:.2f} {self.label_name_unit_pairs[position][1]}")
        self.current_time_label.config(text=f": {datetime.now().strftime('%H:%M:%S')}")
        self.arduino_status_label.config(text=f"{': Connected' if self.arduino_status_code == 200 else self.make_error_sentence(self.arduino_status_code)}")

    def update_plot(self):
        if len(self.time_arduino_plot) <= 2:
            return

        self.ax.clear()
        self.ax2.clear()

        marker_size = 3

        self.ax.plot(self.time_arduino_plot, self.data_arduino_plot[2], marker='o', color='blue', label="Volume", markersize=marker_size)

        self.ax2.plot(self.time_arduino_plot, self.data_arduino_plot[1], marker='o', color='green', label="P_plant", markersize=marker_size)
        self.ax2.plot(self.time_arduino_plot, self.data_arduino_plot[0], marker='o', color='red', label="P_storage", markersize=marker_size)
        self.ax2.plot(self.time_arduino_plot, self.data_arduino_plot[3], marker='o', color='skyblue', label="P_purifier", markersize=marker_size)

        ax2_color = 'red'

        self.ax.set_xlabel("")
        self.ax.set_ylabel("Volume (L)")
        self.ax2.set_ylabel("Pressure (psi)", color=ax2_color)

        # y축 레이블 위치 조정
        self.ax2.yaxis.set_label_position("right")  # y축 레이블을 오른쪽으로 이동
        self.ax2.yaxis.tick_right()  # y축 눈금을 오른쪽으로 이동

        # 그리드 추가
        self.ax.grid(True)  # RFM Plot에 그리드 추가
        self.ax2.grid(color=ax2_color)  # DRC91C Plot에 그리드 추가

        # ax2의 y축 색상을 변경
        self.ax2.tick_params(axis='y', colors=ax2_color)

        max_pressure = max(10, max(self.data_arduino_plot[1]), max(self.data_arduino_plot[0]), max(self.data_arduino_plot[3]))
        if self.enable_localmaxmin.get() == 1:
            self.draw_local_maxmin(self.ax2, max_pressure)

        self.ax.set_ylim(0, max(100, max(self.data_arduino_plot[2])))
        self.ax2.set_ylim(0, max_pressure)

        self.ax.autoscale_view()

        self.ax.legend(loc='lower left')
        self.ax2.legend(loc='upper left')

        # x축 눈금 글자 대각선으로 회전
        for label in self.ax.get_xticklabels():
            label.set_rotation(30)  # 30도 회전
            label.set_horizontalalignment('right')  # 오른쪽 정렬

        self.update_xformatter(self.get_interval())
        self.set_axes_margin()
        self.canvas.draw()

    def find_peaks(self, data):
        threshold = 0.1
        width = 4
        window_size = 2 * width + 1

        # data smoothing
        data_notdeque = list(data)
        data_smooth = [
            sum(data_notdeque[max(i - width, 0):min(i + width + 1, len(data_notdeque))]) / (min(i + width + 1, len(data_notdeque)) - max(i - width, 0))
            for i in range(len(data_notdeque))
        ]

        # find peaks
        peaks = [
            i for i in range(width, len(data_smooth) - width)
            if data_smooth[i] == max(data_smooth[i - width:i + width + 1]) and
            max(data_smooth[i - width:i + width + 1]) - min(data_smooth[i - width:i + width + 1]) > threshold
        ]

        return peaks

    def draw_local_maxmin(self, ax, max_pressure):
        # Find local maxima and minima for plant pressure
        peaks = self.find_peaks(self.data_arduino_plot[1])
        valleys = self.find_peaks([-x for x in self.data_arduino_plot[1]])  # Invert data to find minima

        for peak in peaks: # Annotate local maxima
            ax.annotate(f'P_pl = {self.data_arduino_plot[1][peak]:.2f} psi\nP_st = {self.data_arduino_plot[0][peak]:.2f} psi',
                            (self.time_arduino_plot[peak], min(self.data_arduino_plot[1][peak], max_pressure) - 1),
                            textcoords="data", ha='left', color='green', alpha=0.8, fontweight='bold')
            # vertical line
            ax.plot([self.time_arduino_plot[peak], self.time_arduino_plot[peak]], [0, max_pressure], 'g--', alpha=0.5)
            ax.annotate(f'{self.time_arduino_plot[peak].strftime("%H:%M:%S")}',
                            (self.time_arduino_plot[peak], 0),
                            textcoords="data", xytext=(self.time_arduino_plot[peak], -1),
                            ha='right', color='green', alpha=0.8, fontweight='bold', rotation=30)

        for valley in valleys: # Annotate local minima
            ax.annotate(f'P_pl = {self.data_arduino_plot[1][valley]:.2f} psi\nP_st = {self.data_arduino_plot[0][valley]:.2f} psi',
                            (self.time_arduino_plot[valley], max(self.data_arduino_plot[1][valley], 0) + 1),
                            textcoords="data", ha='left', color='green', alpha=0.8, fontweight='bold')
            # vertical line
            ax.plot([self.time_arduino_plot[valley], self.time_arduino_plot[valley]], [0, max_pressure], 'g--', alpha=0.5)
            ax.annotate(f'{self.time_arduino_plot[valley].strftime("%H:%M:%S")}',
                            (self.time_arduino_plot[valley], 0),
                            textcoords="data", xytext=(self.time_arduino_plot[valley], -1),
                            ha='right', color='green', alpha=0.8, fontweight='bold', rotation=30)

        # Find local maxima and minima for storage pressure
        peaks = self.find_peaks(self.data_arduino_plot[0])
        valleys = self.find_peaks([-x for x in self.data_arduino_plot[0]])

        for peak in peaks:
            ax.annotate(f'P_pl = {self.data_arduino_plot[1][peak]:.2f} psi\nP_st = {self.data_arduino_plot[0][peak]:.2f} psi',
                            (self.time_arduino_plot[peak], min(self.data_arduino_plot[0][peak], max_pressure) - 1),
                            textcoords="data", ha='left', color='red', alpha=0.8, fontweight='bold')
            # vertical line
            ax.plot([self.time_arduino_plot[peak], self.time_arduino_plot[peak]], [0, max_pressure], 'r--', alpha=0.5)
            ax.annotate(f'{self.time_arduino_plot[peak].strftime("%H:%M:%S")}',
                            (self.time_arduino_plot[peak], 0),
                            textcoords="data", xytext=(self.time_arduino_plot[peak], -1),
                            ha='right', color='red', alpha=0.8, fontweight='bold', rotation=30)

        for valley in valleys:
            ax.annotate(f'P_pl = {self.data_arduino_plot[1][valley]:.2f} psi\nP_st = {self.data_arduino_plot[0][valley]:.2f} psi',
                            (self.time_arduino_plot[valley], max(self.data_arduino_plot[0][valley], 0) + 1),
                            textcoords="data", ha='left', color='red', alpha=0.8, fontweight='bold')
            # vertical line
            ax.plot([self.time_arduino_plot[valley], self.time_arduino_plot[valley]], [0, max_pressure], 'r--', alpha=0.5)
            ax.annotate(f'{self.time_arduino_plot[valley].strftime("%H:%M:%S")}',
                            (self.time_arduino_plot[valley], 0),
                            textcoords="data", xytext=(self.time_arduino_plot[valley], -1),
                            ha='right', color='red', alpha=0.8, fontweight='bold', rotation=30)

    def set_axes_margin(self):
        self.ax.margins(x=0.1, y=0.5)
        self.ax2.margins(x=0.1, y=0.5)

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

    def save_log(self, time, arduino_data):
        # 로그 폴더 경로 설정
        log_dir = "log_pressurelevel"

        # 현재 날짜에 맞는 폴더 경로 설정
        year = time.strftime('%Y')
        month = time.strftime('%m')
        day = time.strftime('%d')

        # 연도/월 폴더 경로
        year_month_dir = os.path.join(log_dir, year, month)

        # 폴더가 없으면 생성
        os.makedirs(year_month_dir, exist_ok=True)

        # 날짜에 해당하는 로그 파일 경로
        log_file_path = os.path.join(year_month_dir, f"{day}.txt")

        # 로그 파일에 데이터 추가
        with open(log_file_path, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {arduino_data[2]:.2f} L, {arduino_data[1]:.2f} psi, {arduino_data[0]:.2f} psi, {arduino_data[3]:.2f} psi\n")

    def open_setting(self):
        """
        PressureLevelSetting 클래스로 윈도우를 엽니다.
        """
        self.setting_window = PressureLevelSetting(self)
        self.setting_window.grab_set()
    
    def update_positions(self, positions):
        """
        PressureLevelSetting 클래스로부터 반환받은 positions을 이 클래스에 적용합니다.
        """
        self.last_positions = positions
        self.update_display()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    root = tk.Tk()
    root.iconbitmap(resource_path("PressureLevelPlotter.ico"))
    app = PressureLevelPlotter(root)
    app.start()
    root.mainloop()
