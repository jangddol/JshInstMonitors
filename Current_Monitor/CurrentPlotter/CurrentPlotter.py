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
from VariousTimeDeque import VariousTimeDeque

MAXLEN = 100


class CurrentPlotter:
    def __init__(self, master):
        self.master = master
        self.master.title("Current Plotter")
        self.master.bind("<Configure>", self.on_resize)
        self.width = 800  # Default width

        # Create UI components
        self.create_widgets()

        # Deques for storing values
        self.arduino_deque = VariousTimeDeque(1) # 0: Current

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

        self.label_name_unit_pairs = [
            ("• Current", "A")]
        self.name_labels = []
        self.value_labels = []
        for i, (name, unit) in enumerate(self.label_name_unit_pairs):
            name_label, value_label = self.create_value_labels(name, unit, self.data_frame, i)
            self.name_labels.append(name_label)
            self.value_labels.append(value_label)
        self.last_positions = [0]

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
            return [0]
        try:
            response = requests.get("http://127.0.0.1:5005/Meas", timeout=1)
            self.arduino_status_code = response.status_code
            if response.status_code != 200:
                print(f"Error fetching from Arduino: {response.status_code}")
                return [0]

            json = response.json()

            if time.time() - json['timestamp'] > 5:
                self.arduino_status_code = 'DataTooOld'
                print("Data is too old")
                return [0]

            list_of_str = [json['Current']]
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
        return [0]

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
        data_order = [0]
        for i, position in enumerate(self.last_positions):
            self.name_labels[i].config(text=self.label_name_unit_pairs[position][0])
            self.value_labels[i].config(text=f": {self.arduino_deque.get_last_data()[data_order[position]]:.2f} {self.label_name_unit_pairs[position][1]}")
        self.current_time_label.config(text=f": {datetime.now().strftime('%H:%M:%S')}")
        self.arduino_status_label.config(text=f"{': Connected' if self.arduino_status_code == 200 else self.make_error_sentence(self.arduino_status_code)}")

    def update_plot(self):
        if len(self.time_arduino_plot) <= 2:
            return

        self.ax.clear()

        marker_size = 3

        self.ax.plot(self.time_arduino_plot, self.data_arduino_plot[0], marker='o', color='blue', label="Current", markersize=marker_size)

        self.ax.set_xlabel("")
        self.ax.set_ylabel("Volume (L)")
        self.ax.set_ylim(0, max(1, max(self.data_arduino_plot[0])))
        self.ax.autoscale_view()
        self.ax.legend(loc='lower left')

        # x축 눈금 글자 대각선으로 회전
        for label in self.ax.get_xticklabels():
            label.set_rotation(30)  # 30도 회전
            label.set_horizontalalignment('right')  # 오른쪽 정렬

        self.update_xformatter(self.get_interval())
        self.set_axes_margin()
        self.canvas.draw()

    def set_axes_margin(self):
        self.ax.margins(x=0.1, y=0.5)

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
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {arduino_data[0]:.2f} A\n")


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
    root.iconbitmap(resource_path("CurrentPlotter.ico"))
    app = CurrentPlotter(root)
    app.start()
    root.mainloop()
