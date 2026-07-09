from datetime import datetime, timedelta
import json
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import os
import re
import sys
import requests
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Deque

_COMMON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "common"))
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from CustomDateLocator import CustomDateLocator
from VariousTimeDeque import VariousTimeDeque, Interval, MAXLEN
from CustomMail import send_mail
from FuncLogger import FuncLogger
from paths import bundle_path, writable_path

flog = FuncLogger("flowtemp", "FlowTempPlotter")
_LOG_DIR_NAME = "log_flowtemp"
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}): "
    r"(-?\d+\.\d{2}), (-?\d+\.\d{2}), (-?\d+\.\d{2}), (-?\d+\.\d{2}), "
    r"(-?\d+\.\d{2}), (-?\d+\.\d{2})$"
)


class FlowTempPlotter:
    def __init__(self, master: tk.Tk, _rfm_localserver_port: int, _drc91c_localserver_port: int):
        """Initialize the FlowTempPlotter application.

        Args:
            master (tk.Tk): The root Tkinter window.
            _rfm_localserver_port (int): The port for the RFM local server.
            _drc91c_localserver_port (int): The port for the DRC91C local server.
        """
        self.master: tk.Tk = master
        self.master.title("Flow & Temperature Plotter")
        self.master.bind("<Configure>", self.on_resize)
        self.width: int = 800  # Default width

        self.rfm_localserver_port: int = _rfm_localserver_port
        self.drc91c_localserver_port: int = _drc91c_localserver_port

        # Create UI components
        self.create_widgets()

        # Deques for storing values
        self.rfm_deque: VariousTimeDeque = VariousTimeDeque(4)
        self.drc91c_deque: VariousTimeDeque = VariousTimeDeque(2)

        self.time_rfm_plot: Deque[datetime] = self.rfm_deque.get_time_deque(Interval.ONE_SECOND)
        self.data_rfm_plot: List[Deque[float]] = self.rfm_deque.get_data_deque(Interval.ONE_SECOND)
        self.time_drc91c_plot: Deque[datetime] = self.drc91c_deque.get_time_deque(Interval.ONE_SECOND)
        self.data_drc91c_plot: List[Deque[float]] = self.drc91c_deque.get_data_deque(Interval.ONE_SECOND)

        self.rfm_status_code: str = "Off"
        self.drc91c_status_code: str = "Off"
        self._last_logged_rfm_status = None
        self._last_logged_drc91c_status = None

        flog.info("FlowTempPlotter started")

        loaded_count = self._load_history_from_logs()
        if loaded_count > 0:
            flog.info(f"Restored {loaded_count} log record(s) into plot buffers")
        self._ensure_live_sample_after_history_load()

        self.update_interval(None)
        if len(self.time_rfm_plot) > 2:
            self.update_plot()
        self.main_loop()

    def create_widgets(self):
        """Create and configure the widgets for the application."""
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
        self.bypass_data_label = self.create_value_labels("• Bypass", "L/min", self.data_frame, 2)
        self.pumping_data_label = self.create_value_labels("• Pumping", "L/min", self.data_frame, 3)
        self.head_data_label = self.create_value_labels("• Head", "K", self.data_frame, 4)
        self.cold_tip_data_label = self.create_value_labels("• Cold Tip", "K", self.data_frame, 5)

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

    def create_value_labels(self, name: str, unit: str, frame: tk.Frame, row: int) -> tk.Label:
        """Create a label for displaying a value.

        Args:
            name (str): The name of the value.
            unit (str): The unit of the value.
            frame (tk.Frame): The parent frame for the label.
            row (int): The row in the grid layout.

        Returns:
            tk.Label: The created label.
        """
        name_label = tk.Label(frame, text=f"{name}")
        name_label.grid(row=row, column=0, sticky='w', padx=(0, 5), pady=2)

        value_label = tk.Label(frame, text=f": 0.00 {unit}")
        value_label.grid(row=row, column=1, sticky='w', pady=2)

        return value_label

    def on_resize(self, event: tk.Event):
        """Handle the resize event for the application window.

        Args:
            event (tk.Event): The resize event.
        """
        self.last_width = self.width
        self.width = event.width
        if self.last_width != self.width:
            self.resize_figure()

    def resize_figure(self):
        """Resize the figure based on the current window width."""
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

    def update_interval(self, event: Optional[tk.Event]):
        """Update the interval for data plotting.

        Args:
            event (Optional[tk.Event]): The event triggering the update.
        """
        interval = self.get_interval()
        self.time_rfm_plot = self.rfm_deque.get_time_deque(interval)
        self.data_rfm_plot = self.rfm_deque.get_data_deque(interval)
        self.time_drc91c_plot = self.drc91c_deque.get_time_deque(interval)
        self.data_drc91c_plot = self.drc91c_deque.get_data_deque(interval)

        if len(self.time_rfm_plot) <= 2:
            return
        self.update_plot()

    def main_loop(self):
        """Main loop for updating the application state."""
        loop_start_time = time.time()

        self.update_display()

        expected_exc_delay = 0.2
        if (len(self.rfm_deque.time_1s) > 0 and
                loop_start_time - self.rfm_deque.get_last_time().timestamp() < expected_exc_delay):
            if self.get_interval() == Interval.ONE_SECOND:
                self.update_plot()

        if (len(self.rfm_deque.time_1min) > 0 and
                loop_start_time - self.rfm_deque.get_last_1min_time().timestamp() < expected_exc_delay):
            if self.get_interval() == Interval.ONE_MINUTE:
                self.update_plot()
            self.save_log(self.rfm_deque.get_last_1min_time(), self.rfm_deque.get_last_data(), self.drc91c_deque.get_last_data())

        if (len(self.rfm_deque.time_10min) > 0 and
                loop_start_time - self.rfm_deque.get_last_10min_time().timestamp() < expected_exc_delay):
            if self.get_interval() == Interval.TEN_MINUTES:
                self.update_plot()
            GOOD_STATUS = "200"
            idle_statuses = ("Off", "Connecting")
            if (
                self.enable_rfm.get()
                and self.rfm_status_code != GOOD_STATUS
                and self.rfm_status_code not in idle_statuses
            ):
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                subject = f"{date_str} MKS247C is disconnected."
                contents = f"Plz check the MKS247C. MKS247C is disconnected at {date_str}."
                flog.caution(
                    f"MKS247C disconnect alert: status={self.rfm_status_code}, sending mail"
                )
                result, error_msg = send_mail(subject, contents)
                if result:
                    flog.info("MKS247C disconnect alert email sent")
                else:
                    flog.error(f"MKS247C disconnect alert email failed: {error_msg}")
            if (
                self.enable_drc91c.get()
                and self.drc91c_status_code != GOOD_STATUS
                and self.drc91c_status_code not in idle_statuses
            ):
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                subject = f"{date_str} Temperature controller is disconnected."
                contents = f"Plz check the temperature controller. Temperature controller is disconnected at {date_str}."
                flog.caution(
                    f"Temperature controller disconnect alert: status={self.drc91c_status_code}, sending mail"
                )
                result, error_msg = send_mail(subject, contents)
                if result:
                    flog.info("Temperature controller disconnect alert email sent")
                else:
                    flog.error(
                        f"Temperature controller disconnect alert email failed: {error_msg}"
                    )

        if (len(self.rfm_deque.time_1hour) > 0 and
                loop_start_time - self.rfm_deque.get_last_1hour_time().timestamp() < expected_exc_delay):
            if self.get_interval() == Interval.ONE_HOUR:
                self.update_plot()

        loop_end_time = time.time()
        execution_time = loop_end_time - loop_start_time

        # Calculate the time to wait before the next execution
        next_execution_delay = max(0, int((expected_exc_delay - execution_time) * 1000))

        self.master.after(next_execution_delay, self.main_loop)

    def fetch_loop(self):
        """Loop for continuously fetching data."""
        while True:
            loop_start_time = time.time()

            self.fetch_data()

            elapsed_time = time.time() - loop_start_time
            sleep_time = max(0, 1 - elapsed_time)

            time.sleep(sleep_time)

    def start(self):
        """Start the data fetching thread."""
        self.data_fetch_thread = threading.Thread(target=self.fetch_loop)
        self.data_fetch_thread.daemon = True
        self.data_fetch_thread.start()

    def _log_status_change(
        self,
        device: str,
        status,
        last_attr: str,
        message: str,
        *,
        level: str = "error",
    ) -> None:
        """Log fetch issues only when status changes (avoid 1 Hz spam)."""
        if status == getattr(self, last_attr):
            return
        setattr(self, last_attr, status)
        if level == "caution":
            flog.caution(message)
        elif level == "critical":
            flog.critical(message)
        elif level == "info":
            flog.info(message)
        else:
            flog.error(message)

    def parse_temperature(self, value: str) -> float:
        """Parse a temperature value from a string.

        Args:
            value (str): The temperature value as a string.

        Returns:
            float: The parsed temperature value.
        """
        return float(value[1:7])

    def get_data_from_rfm(self) -> List[float]:
        """Fetch data from the RFM local server.

        Returns:
            List[float]: The fetched data.
        """
        if self.enable_rfm.get() == 0:
            self.rfm_status_code = 'Off'
            return [0, 0, 0, 0]
        try:
            response = requests.get(f"http://127.0.0.1:{self.rfm_localserver_port}/get_value", timeout=1)
            self.rfm_status_code = str(response.status_code)
            if response.status_code != 200:
                self._log_status_change(
                    "RFM",
                    self.rfm_status_code,
                    "_last_logged_rfm_status",
                    f"RFM fetch failed: HTTP {response.status_code}",
                )
                return [0, 0, 0, 0]

            json = response.json()

            if time.time() - json['timestamp'] > 5:
                self.rfm_status_code = 'DataTooOld'
                self._log_status_change(
                    "RFM",
                    self.rfm_status_code,
                    "_last_logged_rfm_status",
                    "RFM data is too old",
                    level="caution",
                )
                return [0, 0, 0, 0]

            list_of_str = [json['Tip'], json['Shield'], json['Bypass'], json['Pumping']]
            result = [float(x) for x in list_of_str]
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                "RFM data fetch OK",
                level="info",
            )
            return result
        except requests.exceptions.ConnectionError as e:
            self.rfm_status_code = 'ConnectionError'
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                f"RFM connection error: {e}",
            )
        except requests.exceptions.Timeout as e:
            self.rfm_status_code = 'Timeout'
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                f"RFM timeout: {e}",
            )
        except requests.exceptions.HTTPError as e:
            self.rfm_status_code = 'HTTPError'
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                f"RFM HTTP error: {e}",
            )
        except requests.exceptions.RequestException as e:
            self.rfm_status_code = 'RequestException'
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                f"RFM request error: {e}",
            )
        except Exception as e:
            self.rfm_status_code = 'Critical'
            self._log_status_change(
                "RFM",
                self.rfm_status_code,
                "_last_logged_rfm_status",
                f"RFM critical error: {e}",
                level="critical",
            )
        return [0, 0, 0, 0]

    def get_data_from_drc91c(self) -> List[float]:
        """Fetch data from the DRC91C local server.

        Returns:
            List[float]: The fetched data.
        """
        if self.enable_drc91c.get() == 0:
            self.drc91c_status_code = 'Off'
            return [0, 0]
        try:
            response = requests.get(f"http://127.0.0.1:{self.drc91c_localserver_port}/sensor_pair", timeout=1)
            self.drc91c_status_code = str(response.status_code)
            if response.status_code != 200:
                self._log_status_change(
                    "DRC91C",
                    self.drc91c_status_code,
                    "_last_logged_drc91c_status",
                    f"DRC91C fetch failed: HTTP {response.status_code}",
                )
                return [0, 0]

            json = response.json()

            if time.time() - json['timestamp'] > 5:
                self.drc91c_status_code = 'DataTooOld'
                self._log_status_change(
                    "DRC91C",
                    self.drc91c_status_code,
                    "_last_logged_drc91c_status",
                    "DRC91C data is too old",
                    level="caution",
                )
                return [0, 0]

            list_of_str = [json['valueA'], json['valueB']]
            result = [self.parse_temperature(x) for x in list_of_str]
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                "DRC91C data fetch OK",
                level="info",
            )
            return result
        except requests.exceptions.ConnectionError as e:
            self.drc91c_status_code = 'ConnectionError'
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                f"DRC91C connection error: {e}",
            )
        except requests.exceptions.Timeout as e:
            self.drc91c_status_code = 'Timeout'
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                f"DRC91C timeout: {e}",
            )
        except requests.exceptions.HTTPError as e:
            self.drc91c_status_code = 'HTTPError'
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                f"DRC91C HTTP error: {e}",
            )
        except requests.exceptions.RequestException as e:
            self.drc91c_status_code = 'RequestException'
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                f"DRC91C request error: {e}",
            )
        except Exception as e:
            self.drc91c_status_code = 'Critical'
            self._log_status_change(
                "DRC91C",
                self.drc91c_status_code,
                "_last_logged_drc91c_status",
                f"DRC91C critical error: {e}",
                level="critical",
            )
        return [0, 0]

    def fetch_data(self):
        """Fetch data from RFM and DRC91C devices."""
        values_rfm = self.get_data_from_rfm()
        self.rfm_deque.update_data(values_rfm, time.time())

        values_drc91c = self.get_data_from_drc91c()
        self.drc91c_deque.update_data(values_drc91c, time.time())

    def get_interval(self) -> Interval:
        """Get the current interval for data plotting.

        Returns:
            Interval: The interval.
        """
        interval_str = self.interval_combo.get()
        if interval_str == "1 s":
            return Interval.ONE_SECOND
        elif interval_str == "1 min":
            return Interval.ONE_MINUTE
        elif interval_str == "10 min":
            return Interval.TEN_MINUTES
        elif interval_str == "1 hour":
            return Interval.ONE_HOUR
        raise ValueError("Invalid interval")

    def make_error_sentence(self, error_code: str) -> str:
        """Create an error sentence based on the error code.

        Args:
            error_code (str): The error code.

        Returns:
            str: The error sentence.
        """
        try:
            error_code = str(error_code)
            return f": Err({error_code})"
        except ValueError:
            return f": {error_code}"

    def update_display(self):
        """Update the display with the latest data."""
        self.tip_data_label.config(text=f": {self.rfm_deque.get_last_data()[0]:.2f} L/min")
        self.shield_data_label.config(text=f": {self.rfm_deque.get_last_data()[1]:.2f} L/min")
        self.bypass_data_label.config(text=f": {self.rfm_deque.get_last_data()[2]:.2f} L/min")
        self.pumping_data_label.config(text=f": {self.rfm_deque.get_last_data()[3]:.2f} L/min")
        self.head_data_label.config(text=f": {self.drc91c_deque.get_last_data()[0]:.2f} K")
        self.cold_tip_data_label.config(text=f": {self.drc91c_deque.get_last_data()[1]:.2f} K")
        self.current_time_label.config(text=f": {datetime.now().strftime('%H:%M:%S')}")
        self.rfm_status_label.config(text=f"{': Connected' if self.rfm_status_code == '200' else self.make_error_sentence(self.rfm_status_code)}")
        self.drc91c_status_label.config(text=f"{': Connected' if self.drc91c_status_code == '200' else self.make_error_sentence(self.drc91c_status_code)}")

    def update_plot(self):
        """Update the plot with the latest data."""
        if len(self.time_rfm_plot) <= 2:
            return

        self.ax.clear()
        self.ax2.clear()

        marker_size = 3

        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[0], marker='o', color='green', label="Tip", markersize=marker_size)
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[1], marker='o', color='blue', label="Shield", markersize=marker_size)
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[2], marker='o', color='purple', label="Bypass", markersize=marker_size)
        self.ax.plot(self.time_rfm_plot, self.data_rfm_plot[3], marker='o', color='skyblue', label="Pumping", markersize=marker_size)

        self.ax2.plot(self.time_drc91c_plot, self.data_drc91c_plot[0], marker='o', color='red', label="Head", markersize=marker_size)
        self.ax2.plot(self.time_drc91c_plot, self.data_drc91c_plot[1], marker='o', color='orange', label="Cold Tip", markersize=marker_size)

        ax2_color = 'red'

        self.ax.set_xlabel("")
        self.ax.set_ylabel("Flow Rate (L/min)")
        self.ax2.set_ylabel("Temperature (K)", color=ax2_color)

        # y축 레이블 위치 조정
        self.ax2.yaxis.set_label_position("right")  # y축 레이블을 오른쪽으로 이동
        self.ax2.yaxis.tick_right()  # y축 눈금을 오른쪽으로 이동

        # 그리드 추가
        self.ax.grid(True)  # RFM Plot에 그리드 추가
        self.ax2.grid(color=ax2_color)  # DRC91C Plot에 그리드 추가

        # ax2의 y축 색상을 변경
        self.ax2.tick_params(axis='y', colors=ax2_color)

        self.ax.relim()
        # y축 최소값을 0으로 설정
        if self.ax.get_ylim()[0] < 0:
            self.ax.set_ylim(bottom=0)  # RFM Plot의 y축 최소값을 0으로 설정
        if self.ax2.get_ylim()[0] < 0:
            self.ax2.set_ylim(bottom=0)  # DRC91C Plot의 y축 최소값을 0으로 설정 (필요한 경우)
        self.ax.autoscale_view()

        self.ax.legend(loc='lower left')  # RFM Plot의 legend를 오른쪽 위로 이동
        self.ax2.legend(loc='lower right')  # DRC91C Plot의 legend를 오른쪽 중앙으로 이동

        # x축 눈금 글자 대각선으로 회전
        for label in self.ax.get_xticklabels():
            label.set_rotation(30)  # 30도 회전
            label.set_horizontalalignment('right')  # 오른쪽 정렬

        self.update_xformatter(self.get_interval())
        self.set_axes_margin()
        self.canvas.draw()

    def set_axes_margin(self):
        """Set margins for the axes."""
        self.ax.margins(x=0.1, y=0.5)
        self.ax2.margins(x=0.1, y=0.5)

    def update_xformatter(self, interval: Interval):
        """Update the x-axis formatter based on the interval.

        Args:
            interval (Interval): The interval.
        """
        def format_date(x, pos=None):
            date = mdates.num2date(x)
            if interval == Interval.ONE_SECOND:
                return date.strftime("%H:%M:%S")
            elif interval == Interval.ONE_MINUTE:
                return date.strftime("%H:%M")
            elif interval == Interval.TEN_MINUTES:
                return date.strftime("%m-%d %H:%M")
            elif interval == Interval.ONE_HOUR:
                return date.strftime("%m-%d %H")
            else:
                raise ValueError("Invalid interval")

        locator = CustomDateLocator(interval)
        formatter = ticker.FuncFormatter(format_date)

        self.ax.xaxis.set_major_locator(locator)
        self.ax.xaxis.set_major_formatter(formatter)

        self.figure.autofmt_xdate()

    def _history_lookback_seconds(self) -> int:
        """Longest time window (N * T) across all interval buffers."""
        return MAXLEN * max(interval.value for interval in Interval)

    def _iter_log_file_paths(self, oldest: datetime):
        """Yield daily log file paths from ``oldest`` through today."""
        log_dir = writable_path(_LOG_DIR_NAME)
        if not os.path.isdir(log_dir):
            return

        current_day = oldest.date()
        end_day = datetime.now().date()
        one_day = timedelta(days=1)

        while current_day <= end_day:
            path = os.path.join(
                log_dir,
                f"{current_day.year:04d}",
                f"{current_day.month:02d}",
                f"{current_day.day:02d}.txt",
            )
            if os.path.isfile(path):
                yield path
            current_day += one_day

    def _parse_log_records(self, since: datetime) -> list[tuple[datetime, list[float], list[float]]]:
        """Read log files and return (time, rfm, drc91c) samples sorted by time."""
        records: list[tuple[datetime, list[float], list[float]]] = []

        for path in self._iter_log_file_paths(since):
            try:
                with open(path, "r", encoding="utf-8") as log_file:
                    for line in log_file:
                        match = _LOG_LINE_RE.match(line.strip())
                        if not match:
                            continue

                        dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                        if dt < since:
                            continue

                        rfm = [float(match.group(i)) for i in range(2, 6)]
                        drc = [float(match.group(i)) for i in range(6, 8)]
                        records.append((dt, rfm, drc))
            except OSError as e:
                flog.error(f"Failed to read data log {path}: {e}")

        records.sort(key=lambda item: item[0])
        return records

    def _ensure_live_sample_after_history_load(self) -> None:
        """Ensure 1 s buffers have a sample for display and fetch updates."""
        if len(self.rfm_deque.time_1s) == 0:
            for interval in (Interval.ONE_MINUTE, Interval.TEN_MINUTES, Interval.ONE_HOUR):
                data_deques = self.rfm_deque.get_data_deque(interval)
                if len(data_deques[0]) > 0:
                    values = [channel[-1] for channel in data_deques]
                    self.rfm_deque.update_data(values, time.time())
                    break
            else:
                self.rfm_deque.update_data([0] * 4, time.time())

        if len(self.drc91c_deque.time_1s) == 0:
            for interval in (Interval.ONE_MINUTE, Interval.TEN_MINUTES, Interval.ONE_HOUR):
                data_deques = self.drc91c_deque.get_data_deque(interval)
                if len(data_deques[0]) > 0:
                    values = [channel[-1] for channel in data_deques]
                    self.drc91c_deque.update_data(values, time.time())
                    break
            else:
                self.drc91c_deque.update_data([0] * 2, time.time())

    def _load_history_from_logs(self) -> int:
        """Restore deque buffers from log files within each buffer's N*T window."""
        now = datetime.now()
        since = now - timedelta(seconds=self._history_lookback_seconds())
        records = self._parse_log_records(since)
        if not records:
            return 0

        rfm_records = [(dt, rfm) for dt, rfm, _drc in records]
        drc_records = [(dt, drc) for dt, _rfm, drc in records]
        self.rfm_deque.load_historical(rfm_records, reference_time=now)
        self.drc91c_deque.load_historical(drc_records, reference_time=now)
        return len(records)

    def save_log(self, time: datetime, rfm_data: List[float], drc91c_data: List[float]):
        """Save the log data to a file.

        Args:
            time (datetime): The timestamp of the log entry.
            rfm_data (List[float]): The RFM data to log.
            drc91c_data (List[float]): The DRC91C data to log.
        """
        year = time.strftime('%Y')
        month = time.strftime('%m')
        day = time.strftime('%d')

        year_month_dir = writable_path(_LOG_DIR_NAME, year, month)
        os.makedirs(year_month_dir, exist_ok=True)

        log_file_path = os.path.join(year_month_dir, f"{day}.txt")

        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')}: "
                f"{rfm_data[0]:.2f}, {rfm_data[1]:.2f}, {rfm_data[2]:.2f}, {rfm_data[3]:.2f}, "
                f"{drc91c_data[0]:.2f}, {drc91c_data[1]:.2f}\n"
            )

<<<<<<< HEAD
=======
    def _on_close(self) -> None:
        """Handle window close: clean up matplotlib then force-exit.

        plt.close('all') must be called before root.destroy() to prevent
        matplotlib's atexit handler from trying to access the already-destroyed
        tkinter root, which causes the process to hang (especially in
        PyInstaller --noconsole builds).  os._exit() then bypasses the rest of
        Python's shutdown sequence entirely, guaranteeing the process exits.
        """
        plt.close('all')
        self.master.destroy()
        os._exit(0)


>>>>>>> 841c9b0e189c28352cdaca55029d8afc80931392
def open_config_file(file_path: str) -> tuple[int, int]:
    """Open and parse the configuration file.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        (int, int): The RFM and DRC91C local server ports.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        config_data = json.load(file)

        _rfm_localserver_port = config_data.get('rfm_localserver_port')
        _drc91c_localserver_port = config_data.get('drc91c_localserver_port')

        if not isinstance(_rfm_localserver_port, int) or not isinstance(_drc91c_localserver_port, int):
            raise ValueError("Invalid configuration data")

        return _rfm_localserver_port, _drc91c_localserver_port


if __name__ == "__main__":
    config_file_path = writable_path('flowtempplotter_config.json')
    try:
        rfm_localserver_port, drc91c_localserver_port = open_config_file(config_file_path)
    except Exception as e:
        flog.caution(f"Config load failed ({e}); writing default config")
        with open(config_file_path, 'w', encoding='utf-8') as file:
            json.dump({'rfm_localserver_port': 5000, 'drc91c_localserver_port': 5001}, file)
        rfm_localserver_port, drc91c_localserver_port = open_config_file(config_file_path)

    root = tk.Tk()
    root.iconbitmap(bundle_path("FlowTempPlotter.ico"))
    app = FlowTempPlotter(root, rfm_localserver_port, drc91c_localserver_port)
    app.start()
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()
