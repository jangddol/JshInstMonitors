from datetime import datetime
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import requests

# matplotlib 백엔드를 명시적으로 설정
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from CustomDateLocator import CustomDateLocator
from PressureLevelSetting import PressureLevelSetting
from VariousTimeDeque import VariousTimeDeque, Interval
from CustomMail import send_mail

MAXLEN = 100

# 테스트 모드 설정 (True로 설정하면 시뮬레이션 데이터 사용)
IS_TEST = False


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

        self.time_arduino_plot = self.arduino_deque.get_time_deque(Interval.ONE_SECOND)
        self.data_arduino_plot = self.arduino_deque.get_data_deque(Interval.ONE_SECOND)

        self.arduino_status_code = "Off"

        # Email alert notification window (non-modal)
        self.email_alert_window = None

        self.update_interval(None)
        self.main_loop()

    def create_widgets(self) -> None:
        # Top frame
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # IntVar를 사용하여 체크박스 상태를 저장
        self.enable_arduino = tk.IntVar()
        self.enable_localmaxmin = tk.IntVar()

        self.checkbox_arduino = tk.Checkbutton(self.top_frame, text="Enable Arduino", variable=self.enable_arduino, command=self.on_arduino_checkbox_change)
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

        self.ax2: plt.Axes = self.ax.twinx()

        # Right frame for displaying values and status
        self.right_frame = tk.Frame(self.bottom_frame, width=150)  # Fixed width for right_frame
        self.right_frame.grid(row=0, column=1, sticky='nsew')

        # Data frame
        self.data_frame = tk.Frame(self.right_frame)
        self.data_frame.pack(side=tk.TOP, fill=tk.Y)

        self.label_name_unit_pairs: list[tuple[str, str]] = [
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
        self.last_positions: list[int] = [0, 1, 2, 3]

        # plot setting
        self.is_plot: list[bool] = [True, True, True, True]

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
            if self.get_interval() == Interval.ONE_SECOND:
                self.update_plot()

        if loop_start_time - self.arduino_deque.get_last_1min_time().timestamp() < expected_exc_delay:
            if self.get_interval() == Interval.ONE_MINUTE:
                self.update_plot()
            self.save_log(self.arduino_deque.get_last_1min_time(), self.arduino_deque.get_last_data())

        if loop_start_time - self.arduino_deque.get_last_10min_time().timestamp() < expected_exc_delay:
            if self.get_interval() == Interval.TEN_MINUTES:
                self.update_plot()
            # Arduino 상태 체크를 더 안전하게 (활성화되어 있을 때만)
            if (self.enable_arduino.get() == 1 and 
                self.arduino_status_code != 200 and 
                self.arduino_status_code not in ['Off', 'Connecting']):
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                subject = f"{date_str} Arduino is disconnected."
                content = f"Plz check the Arduino. Arduino is disconnected at {date_str}."
                print(f"[EMAIL] Arduino 연결 문제 감지 - 상태 코드: {self.arduino_status_code}")
                print(f"[EMAIL] 메일 전송 시도 - 제목: {subject}")
                result, error_msg = send_mail(subject, content)
                if result:
                    print(f"[EMAIL] 메일 전송 성공 - Arduino 연결 문제 알림")
                else:
                    print(f"[EMAIL] 메일 전송 실패 - Arduino 연결 문제 알림")
                    print(f"[EMAIL] 실패 원인: {error_msg}")
                    alert_message = f"Failed to send Arduino disconnection alert email"
                    if error_msg:
                        alert_message += f"\n\nError: {error_msg}"
                    self.show_email_alert(alert_message)
            # 압력 체크를 더 안전하게 (활성화되어 있을 때만)
            if self.enable_arduino.get() == 1:
                try:
                    last_data = self.arduino_deque.get_last_data()
                    if len(last_data) >= 4 and (last_data[1] > 3.0 or last_data[0] > 9.0):
                        now = datetime.now()
                        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                        p_plant = last_data[1]
                        p_storage = last_data[0]
                        subject = f"{date_str} Pressure is too high : P_pl = {p_plant:.2f} psi, P_st = {p_storage:.2f} psi"
                        content = f"Plz check the Pressure. Pressure is too high at {date_str}. P_pl = {p_plant:.2f} psi, P_st = {p_storage:.2f} psi."
                        print(f"[EMAIL] 압력 임계값 초과 감지 - P_plant: {p_plant:.2f} psi, P_storage: {p_storage:.2f} psi")
                        print(f"[EMAIL] 메일 전송 시도 - 제목: {subject}")
                        result, error_msg = send_mail(subject, content)
                        if result:
                            print(f"[EMAIL] 메일 전송 성공 - 압력 임계값 초과 알림")
                        else:
                            print(f"[EMAIL] 메일 전송 실패 - 압력 임계값 초과 알림")
                            print(f"[EMAIL] 실패 원인: {error_msg}")
                            alert_message = f"Failed to send pressure alert email"
                            if error_msg:
                                alert_message += f"\n\nError: {error_msg}"
                            self.show_email_alert(alert_message)
                    if len(last_data) >= 4 and (last_data[1] < 0.25):
                        now = datetime.now()
                        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                        p_plant = last_data[1]
                        p_storage = last_data[0]
                        subject = f"{date_str} Storage Pressure is too low : P_pl = {p_plant:.2f} psi, P_st = {p_storage:.2f} psi"
                        content = f"Plz check the Pressure. Pressure is too low at {date_str}. P_pl = {p_plant:.2f} psi, P_st = {p_storage:.2f} psi."
                        print(f"[EMAIL] 압력 임계값 미만 감지 - P_plant: {p_plant:.2f} psi, P_storage: {p_storage:.2f} psi")
                        print(f"[EMAIL] 메일 전송 시도 - 제목: {subject}")
                        result, error_msg = send_mail(subject, content)
                        if result:
                            print(f"[EMAIL] 메일 전송 성공 - 압력 임계값 미만 알림")
                        else:
                            print(f"[EMAIL] 메일 전송 실패 - 압력 임계값 미만 알림")
                            print(f"[EMAIL] 실패 원인: {error_msg}")
                            alert_message = f"Failed to send pressure alert email"
                            if error_msg:
                                alert_message += f"\n\nError: {error_msg}"
                            self.show_email_alert(alert_message)
                except (IndexError, TypeError) as e:
                    print(f"Error checking pressure: {e}")

        if loop_start_time - self.arduino_deque.get_last_1hour_time().timestamp() < expected_exc_delay:
            if self.get_interval() == Interval.ONE_HOUR:
                self.update_plot()

        loop_end_time = time.time()
        execution_time = loop_end_time - loop_start_time

        # Calculate the time to wait before the next execution
        next_execution_delay = max(0, int((expected_exc_delay - execution_time) * 1000))

        self.master.after(next_execution_delay, self.main_loop)

    def fetch_loop(self):
        while True:
            try:
                loop_start_time = time.time()

                # 항상 fetch_data를 호출하여 플롯 업데이트가 되도록 함
                self.fetch_data()

                elapsed_time = time.time() - loop_start_time
                sleep_time = max(0, 1 - elapsed_time)

                time.sleep(sleep_time)

            except Exception as e:
                print(f"[ERROR] fetch_loop() 에러: {e}")
                time.sleep(1)  # 에러 발생 시 1초 대기

    def start(self):
        self.data_fetch_thread = threading.Thread(target=self.fetch_loop)
        self.data_fetch_thread.daemon = True
        self.data_fetch_thread.start()

    def get_simulation_data(self):
        """테스트용 시뮬레이션 데이터 생성"""
        import random
        import math

        # 시간에 따른 시뮬레이션 데이터 생성
        current_time = time.time()

        # 사인파 기반의 시뮬레이션 데이터
        time_factor = current_time * 0.1  # 시간에 따른 변화

        # P_storage (저장소 압력) - 5-8 psi 범위에서 사인파
        p_storage = 6.5 + 1.5 * math.sin(time_factor * 0.5)

        # P_plant (식물 압력) - 2-4 psi 범위에서 사인파
        p_plant = 3.0 + 1.0 * math.sin(time_factor * 0.3)

        # V_plant (식물 부피) - 50-80 L 범위에서 사인파
        v_plant = 65.0 + 15.0 * math.sin(time_factor * 0.2)

        # P_purifier (정화기 압력) - 1-3 psi 범위에서 사인파
        p_purifier = 2.0 + 1.0 * math.sin(time_factor * 0.4)

        # 약간의 랜덤 노이즈 추가
        noise = random.uniform(-0.1, 0.1)
        p_storage += noise
        p_plant += noise
        v_plant += noise * 5
        p_purifier += noise

        # 데이터를 문자열 형태로 반환 (실제 Arduino 응답과 동일한 형태)
        return {
            'P_st': f"{p_storage:.2f} psi",
            'P_pl': f"{p_plant:.2f} psi", 
            'V_pl': f"{v_plant:.2f} L",
            'P_pur': f"{p_purifier:.2f} psi",
            'timestamp': current_time
        }

    def get_data_from_arduino(self):
        # Arduino가 비활성화되어 있으면 즉시 [0,0,0,0] 반환
        if self.enable_arduino.get() == 0:
            self.arduino_status_code = 'Off'
            return [0, 0, 0, 0]

        # 테스트 모드일 때 시뮬레이션 데이터 사용 (Arduino가 활성화되어 있을 때만)
        if IS_TEST:
            try:
                simulation_data = self.get_simulation_data()
                self.arduino_status_code = 200  # 성공 상태
                list_of_str = [simulation_data['P_st'], simulation_data['P_pl'], simulation_data['V_pl'], simulation_data['P_pur']]
                result = [float(x.split(' ')[0]) for x in list_of_str]
                return result
            except Exception as e:
                self.arduino_status_code = 'SimulationError'
                print(f"[ERROR] 시뮬레이션 에러: {e}")
                return [0, 0, 0, 0]

        # 실제 Arduino 데이터 가져오기 (기존 코드)
        try:
            # timeout을 더 길게 설정하여 연결 안정성 향상
            response = requests.get("http://127.0.0.1:5003/Meas", timeout=3)
            self.arduino_status_code = response.status_code

            if response.status_code != 200:
                print(f"[ERROR] Arduino에서 데이터 가져오기 실패: {response.status_code}")
                return [0, 0, 0, 0]

            json_data = response.json()

            # 타임스탬프 검증을 더 안전하게
            if 'timestamp' not in json_data:
                self.arduino_status_code = 'InvalidData'
                print("[ERROR] 잘못된 데이터 형식")
                return [0, 0, 0, 0]

            if time.time() - json_data['timestamp'] > 5:
                self.arduino_status_code = 'DataTooOld'
                print("[ERROR] 데이터가 너무 오래됨")
                return [0, 0, 0, 0]

            # 데이터 파싱을 더 안전하게
            required_fields = ['P_st', 'P_pl', 'V_pl', 'P_pur']
            if not all(field in json_data for field in required_fields):
                self.arduino_status_code = 'MissingData'
                print("[ERROR] 필수 데이터 필드 누락")
                return [0, 0, 0, 0]

            list_of_str = [json_data['P_st'], json_data['P_pl'], json_data['V_pl'], json_data['P_pur']]

            # 문자열 파싱을 더 안전하게
            try:
                result = [float(x.split(' ')[0]) for x in list_of_str]
                return result
            except (ValueError, IndexError) as e:
                self.arduino_status_code = 'ParseError'
                print(f"[ERROR] 데이터 파싱 에러: {e}")
                return [0, 0, 0, 0]

        except requests.exceptions.ConnectionError as e:
            self.arduino_status_code = 'ConnectionError'
            print(f"[ERROR] Arduino 연결 에러: {e}")
        except requests.exceptions.Timeout as e:
            self.arduino_status_code = 'Timeout'
            print(f"[ERROR] Arduino 타임아웃 에러: {e}")
        except requests.exceptions.HTTPError as e:
            self.arduino_status_code = 'HTTPError'
            print(f"[ERROR] Arduino HTTP 에러: {e}")
        except requests.exceptions.RequestException as e:
            self.arduino_status_code = 'RequestException'
            print(f"[ERROR] Arduino 요청 에러: {e}")
        except Exception as e:
            self.arduino_status_code = 'Critical'
            print(f"[ERROR] Arduino 치명적 에러: {e}")

        return [0, 0, 0, 0]

    def fetch_data(self):
        values_arduino = self.get_data_from_arduino()
        self.arduino_deque.update_data(values_arduino, time.time())

        # 데이터가 있으면 플롯 업데이트 (Arduino 상태와 관계없이)
        data_length = len(self.arduino_deque.get_data_deque(Interval.ONE_SECOND))
        if data_length > 0:
            # GUI 스레드에서 안전하게 플롯 업데이트
            self.master.after(0, self.safe_update_plot)

    def get_interval(self):
        interval_str = self.interval_combo.get()
        if interval_str == "1 s":
            return Interval.ONE_SECOND
        if interval_str == "1 min":
            return Interval.ONE_MINUTE
        if interval_str == "10 min":
            return Interval.TEN_MINUTES
        if interval_str == "1 hour":
            return Interval.ONE_HOUR
        return Interval.ONE_SECOND

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
        # 더 강력한 데이터 검증
        if not hasattr(self, 'time_arduino_plot') or not hasattr(self, 'data_arduino_plot'):
            print("[ERROR] Plot 데이터가 초기화되지 않음")
            return

        if len(self.time_arduino_plot) <= 2:
            return

        # 데이터가 비어있는지 확인
        if not self.data_arduino_plot or any(len(data) == 0 for data in self.data_arduino_plot):
            return

        # 데이터 길이 검증
        if len(self.data_arduino_plot) < 4:
            print("[ERROR] 데이터 배열이 부족함")
            return

        # 각 데이터 배열의 길이 검증
        for i, data in enumerate(self.data_arduino_plot):
            if len(data) == 0:
                print(f"[ERROR] 데이터 배열 {i}가 비어있음")
                return
            if len(data) != len(self.time_arduino_plot):
                print(f"[ERROR] 데이터 배열 {i}의 길이가 시간 배열과 다름")
                return

        self.ax.clear()
        self.ax2.clear()

        marker_size = 3

        # is_plot 설정에 따라 각 채널 플롯 여부 결정
        # Volume (V_plant) - data_arduino_plot[2], label_name_unit_pairs[0]
        if self.is_plot[0]:  # V_plant 채널이 활성화되어 있으면
            self.ax.plot(self.time_arduino_plot, self.data_arduino_plot[2], marker='o', color='blue', label="Volume", markersize=marker_size)

        # Pressure 그래프들
        # P_plant - data_arduino_plot[1], label_name_unit_pairs[1]
        if self.is_plot[1]:  # P_plant 채널이 활성화되어 있으면
            self.ax2.plot(self.time_arduino_plot, self.data_arduino_plot[1], marker='o', color='green', label="P_plant", markersize=marker_size)

        # P_storage - data_arduino_plot[0], label_name_unit_pairs[2]
        if self.is_plot[2]:  # P_storage 채널이 활성화되어 있으면
            self.ax2.plot(self.time_arduino_plot, self.data_arduino_plot[0], marker='o', color='red', label="P_storage", markersize=marker_size)

        # P_purifier - data_arduino_plot[3], label_name_unit_pairs[3]
        if self.is_plot[3]:  # P_purifier 채널이 활성화되어 있으면
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

        # 안전한 max_pressure 계산 (활성화된 채널만 고려)
        try:
            pressure_values = []
            if self.is_plot[1]:  # P_plant - label_name_unit_pairs[1]
                pressure_values.extend(self.data_arduino_plot[1])
            if self.is_plot[2]:  # P_storage - label_name_unit_pairs[2]
                pressure_values.extend(self.data_arduino_plot[0])
            if self.is_plot[3]:  # P_purifier - label_name_unit_pairs[3]
                pressure_values.extend(self.data_arduino_plot[3])

            if pressure_values:
                max_pressure = max(10, max(pressure_values))
            else:
                max_pressure = 10  # 활성화된 압력 채널이 없으면 기본값
        except ValueError:
            max_pressure = 10  # 기본값 사용
            print("Warning: Could not calculate max_pressure, using default value")

        if self.enable_localmaxmin.get() == 1:
            self.draw_local_maxmin(self.ax2, max_pressure)

        # 안전한 y축 범위 설정 (활성화된 채널만 고려)
        try:
            if self.is_plot[0]:  # V_plant - label_name_unit_pairs[0]
                max_volume = max(100, max(self.data_arduino_plot[2]))
            else:
                max_volume = 100  # Volume 채널이 비활성화되어 있으면 기본값
        except ValueError:
            max_volume = 100  # 기본값 사용
            print("Warning: Could not calculate max_volume, using default value")

        self.ax.set_ylim(0, max_volume)
        self.ax2.set_ylim(0, max_pressure)

        # 활성화된 채널의 데이터만 고려하여 x축 범위 설정
        if len(self.time_arduino_plot) > 0 and any(self.is_plot):
            # 활성화된 채널의 시간 범위만 사용
            x_min = min(self.time_arduino_plot)
            x_max = max(self.time_arduino_plot)

            # autoscale_view()의 마진 로직을 수동으로 구현 (약 5% 여백)
            x_range = x_max - x_min
            if x_range.total_seconds() > 0:  # timedelta를 초 단위로 변환하여 비교
                margin = 0.05  # 5% 여백
                x_margin = x_range * margin
                self.ax.set_xlim(x_min - x_margin, x_max + x_margin)
                self.ax2.set_xlim(x_min - x_margin, x_max + x_margin)
            else:
                # 데이터가 하나뿐인 경우 기본 범위 설정
                self.ax.autoscale_view()
                self.ax2.autoscale_view()
        else:
            self.ax.autoscale_view()
            self.ax2.autoscale_view()

        self.ax.legend(loc='lower left')
        self.ax2.legend(loc='upper left')

        # x축 눈금 글자 대각선으로 회전
        for label in self.ax.get_xticklabels():
            label.set_rotation(30)  # 30도 회전
            label.set_horizontalalignment('right')  # 오른쪽 정렬

        try:
            self.update_xformatter(self.get_interval())
        except Exception as e:
            print(f"[ERROR] x축 포맷터 설정 에러: {e}")

        try:
            self.set_axes_margin()
        except Exception as e:
            print(f"[ERROR] 축 마진 설정 에러: {e}")

        if not self.safe_canvas_draw():
            print("[WARNING] Canvas 업데이트 실패, 그래프 업데이트 건너뜀")

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
        # 데이터가 충분한지 확인
        if len(self.data_arduino_plot[1]) < 10:  # 최소 데이터 포인트 필요
            return

        # Find local maxima and minima for plant pressure
        peaks = self.find_peaks(self.data_arduino_plot[1])
        valleys = self.find_peaks([-x for x in self.data_arduino_plot[1]])  # Invert data to find minima

        for peak in peaks: # Annotate local maxima
            if peak < len(self.time_arduino_plot) and peak < len(self.data_arduino_plot[1]) and peak < len(self.data_arduino_plot[0]):
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
            if valley < len(self.time_arduino_plot) and valley < len(self.data_arduino_plot[1]) and valley < len(self.data_arduino_plot[0]):
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
            if peak < len(self.time_arduino_plot) and peak < len(self.data_arduino_plot[1]) and peak < len(self.data_arduino_plot[0]):
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
            if valley < len(self.time_arduino_plot) and valley < len(self.data_arduino_plot[1]) and valley < len(self.data_arduino_plot[0]):
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
        try:
            # x축 마진은 이미 update_plot에서 수동으로 설정했으므로 제거
            # y축 마진만 설정
            self.ax.margins(y=0.1)
            self.ax2.margins(y=0.1)
        except Exception as e:
            print(f"[ERROR] set_axes_margin() 에러: {e}")

    def update_xformatter(self, interval: Interval):
        def format_date(x, pos=None):
            try:
                date = mdates.num2date(x)
                if interval == Interval.ONE_SECOND:
                    result = date.strftime("%H:%M:%S")
                elif interval == Interval.ONE_HOUR:
                    result = date.strftime("%m-%d %H:%M")
                else:
                    result = date.strftime("%H:%M")
                return result
            except Exception as e:
                print(f"[ERROR] format_date() 에러: {e}")
                return ""

        try:
            locator = CustomDateLocator(interval)
        except Exception as e:
            print(f"[ERROR] CustomDateLocator 생성 에러: {e}")
            from matplotlib.dates import AutoDateLocator
            locator = AutoDateLocator()

        try:
            formatter = ticker.FuncFormatter(format_date)
        except Exception as e:
            print(f"[ERROR] FuncFormatter 생성 에러: {e}")
            return

        try:
            self.ax.xaxis.set_major_locator(locator)
        except Exception as e:
            print(f"[ERROR] x축 locator 설정 에러: {e}")
            # 에러 발생 시 기본 locator 사용
            try:
                from matplotlib.dates import AutoDateLocator
                self.ax.xaxis.set_major_locator(AutoDateLocator())
            except Exception as e2:
                print(f"[ERROR] 기본 locator 설정도 실패: {e2}")
                return

        try:
            self.ax.xaxis.set_major_formatter(formatter)
        except Exception as e:
            print(f"[ERROR] x축 formatter 설정 에러: {e}")

        try:
            self.figure.autofmt_xdate()
        except Exception as e:
            print(f"[ERROR] autofmt_xdate() 에러: {e}")

    def save_log(self, time: datetime, arduino_data):
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
        print("=== 메인 창 - 위치 정보 적용 ===")
        print(f"이전 last_positions: {self.last_positions}")
        print(f"새로운 positions: {positions}")
        print("위치 변경 상세:")
        for i, (old_pos, new_pos) in enumerate(zip(self.last_positions, positions)):
            old_label = self.label_name_unit_pairs[old_pos][0]
            new_label = self.label_name_unit_pairs[new_pos][0]
            print(f"  행 {i}: {old_label} → {new_label}")
        print("=============================")

        self.last_positions = positions
        self.update_display()

    def update_is_plot(self, is_plot) -> None:

        """
        PressureLevelSetting 클래스로부터 반환받은 is_plot을 이 클래스에 적용합니다.
        """
        print("=== 메인 창 - 플롯 설정 적용 ===")
        print(f"이전 is_plot: {self.is_plot}")
        print(f"새로운 is_plot: {is_plot}")
        print("플롯 설정 변경 상세:")
        for i, (old_plot, new_plot) in enumerate(zip(self.is_plot, is_plot)):
            label = self.label_name_unit_pairs[i][0]
            print(f"  {label}: {'표시' if old_plot else '숨김'} → {'표시' if new_plot else '숨김'}")
        print("=============================")

        self.is_plot = is_plot
        
        # 설정 변경 시 즉시 플롯 업데이트
        if len(self.time_arduino_plot) > 2:
            self.update_plot()

    def safe_canvas_draw(self):
        """
        안전한 canvas 업데이트를 위한 함수
        """
        try:
            # GUI 이벤트 처리
            self.master.update_idletasks()
            
            # canvas 업데이트
            self.canvas.draw()
            return True
        except Exception as e:
            print(f"[ERROR] 안전한 canvas 업데이트 실패: {e}")
            try:
                # 대안 방법 시도
                self.canvas.flush_events()
                return True
            except Exception as e2:
                print(f"[ERROR] 대안 canvas 업데이트도 실패: {e2}")
                return False

    def on_arduino_checkbox_change(self):
        """
        Enable Arduino 체크박스의 상태가 변경될 때 호출됩니다.
        무한 루프를 방지하기 위해 안전하게 처리합니다.
        """
        try:
            # Arduino 상태가 변경되면 상태 코드를 초기화
            if self.enable_arduino.get() == 0:
                self.arduino_status_code = 'Off'
            else:
                self.arduino_status_code = 'Connecting'
                # Arduino 활성화 시 즉시 데이터 가져오기
                self.master.after(100, self.immediate_data_fetch)

            # UI 업데이트는 안전하게 처리
            self.update_display()

            # 플롯 업데이트는 데이터가 있을 때만 (Arduino 상태와 관계없이)
            if len(self.time_arduino_plot) > 2:
                self.update_plot()

        except Exception as e:
            print(f"[ERROR] Arduino checkbox change 에러: {e}")
            # 에러 발생 시 체크박스를 원래 상태로 되돌림
            self.enable_arduino.set(0)

    def immediate_data_fetch(self):
        """
        Arduino 활성화 시 즉시 데이터를 가져오는 함수
        """
        try:
            self.fetch_data()
        except Exception as e:
            print(f"[ERROR] immediate_data_fetch() 에러: {e}")

    def safe_update_plot(self):
        """
        GUI 스레드에서 안전하게 플롯을 업데이트하는 함수
        """
        try:
            # 데이터 간격 업데이트
            interval = self.get_interval()
            
            self.time_arduino_plot = self.arduino_deque.get_time_deque(interval)
            self.data_arduino_plot = self.arduino_deque.get_data_deque(interval)
            
            # 플롯 업데이트
            if len(self.time_arduino_plot) > 2:
                self.update_plot()
        except Exception as e:
            print(f"[ERROR] safe_update_plot() 에러: {e}")
            import traceback
            traceback.print_exc()

    def show_email_alert(self, message: str):
        """
        Show non-modal window for email alert failure notification.
        This window does not block program execution.
        
        Args:
            message: Alert message to display
        """
        try:
            # Close existing alert window if any
            if self.email_alert_window is not None:
                try:
                    self.email_alert_window.destroy()
                except:
                    pass

            # Create non-modal window
            self.email_alert_window = tk.Toplevel(self.master)
            self.email_alert_window.title("Email Alert")
            self.email_alert_window.geometry("500x200")
            self.email_alert_window.resizable(True, True)
            self.email_alert_window.minsize(400, 150)

            # Position window at top-right corner
            self.email_alert_window.update_idletasks()
            x = self.master.winfo_x() + self.master.winfo_width() - 420
            y = self.master.winfo_y() + 50
            self.email_alert_window.geometry(f"+{x}+{y}")

            # Make it non-modal (doesn't block interaction with main window)
            self.email_alert_window.transient(self.master)
            # No grab_set() - window is non-modal and doesn't block program execution

            # Content frame
            content_frame = tk.Frame(self.email_alert_window)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Warning icon label (optional)
            warning_label = tk.Label(content_frame, text="⚠", font=("Arial", 24), fg="orange")
            warning_label.pack(side=tk.LEFT, padx=(0, 10))

            # Message frame
            message_frame = tk.Frame(content_frame)
            message_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Title
            title_label = tk.Label(message_frame, text="Email Alert Failed", font=("Arial", 12, "bold"))
            title_label.pack(anchor=tk.W, pady=(0, 5))

            # Message with scrollable text widget for long error messages
            message_text = tk.Text(message_frame, font=("Arial", 10), wrap=tk.WORD, width=50, height=6)
            message_text.insert("1.0", message)
            message_text.config(state=tk.DISABLED)  # Make it read-only
            message_text.pack(anchor=tk.W, fill=tk.BOTH, expand=True)

            # Close button
            button_frame = tk.Frame(self.email_alert_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            close_button = tk.Button(button_frame, text="Close", command=self.email_alert_window.destroy, width=10)
            close_button.pack(side=tk.RIGHT)

        except Exception as e:
            print(f"[ERROR] Failed to show email alert window: {e}")

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
