import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

import numpy as np
import serial

CONFIG_FILENAME = "arduinoadcreceiver_config.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "arduino_port": "COM4",
    "localserver_port": 5003,
    "baud_rate": 9600,
    "serial_timeout": 1,
    "reconnect_delay": 1.0,
    "loop_sleep": 0.1,
    "buffer_flush_interval": 30,
    "filter_cutoff_second": 10,
    "arduino_period": 0.5,
}


def _get_config_path() -> str:
    """Return a writable path next to the exe (frozen) or this script (dev)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, CONFIG_FILENAME)


def _validate_config(config_data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(_DEFAULT_CONFIG)
    merged.update(config_data)

    if not isinstance(merged["arduino_port"], str):
        raise ValueError("arduino_port must be a string")
    if not isinstance(merged["localserver_port"], int):
        raise ValueError("localserver_port must be an integer")
    if not isinstance(merged["baud_rate"], int):
        raise ValueError("baud_rate must be an integer")
    if not isinstance(merged["serial_timeout"], (int, float)):
        raise ValueError("serial_timeout must be a number")
    if not isinstance(merged["reconnect_delay"], (int, float)):
        raise ValueError("reconnect_delay must be a number")
    if not isinstance(merged["loop_sleep"], (int, float)):
        raise ValueError("loop_sleep must be a number")
    if not isinstance(merged["buffer_flush_interval"], (int, float)):
        raise ValueError("buffer_flush_interval must be a number")
    if not isinstance(merged["filter_cutoff_second"], (int, float)):
        raise ValueError("filter_cutoff_second must be a number")
    if not isinstance(merged["arduino_period"], (int, float)):
        raise ValueError("arduino_period must be a number")

    if merged["filter_cutoff_second"] <= 0 or merged["arduino_period"] <= 0:
        raise ValueError("filter_cutoff_second and arduino_period must be positive")

    return merged


def load_config() -> dict[str, Any]:
    """Load config from disk, creating a default file if missing or invalid."""
    config_path = _get_config_path()

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config_data = json.load(file)
        config = _validate_config(config_data)
        print(f"[CONFIG] Loaded {config_path}")
        return config
    except Exception as e:
        print(f"[CONFIG] {e}; writing default config to {config_path}")
        config = dict(_DEFAULT_CONFIG)
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=2)
        print(f"[CONFIG] Created default config at {config_path}")
        return config


class SerialMediator:
    def __init__(self, config: dict[str, Any]):
        self.port = config["arduino_port"]
        self.baud_rate = config["baud_rate"]
        self.serial_timeout = float(config["serial_timeout"])
        self.reconnect_delay = float(config["reconnect_delay"])
        self.loop_sleep = float(config["loop_sleep"])
        self.buffer_flush_interval = float(config["buffer_flush_interval"])

        arduino_period = float(config["arduino_period"])
        cutoff_second = float(config["filter_cutoff_second"])
        self.beta = np.exp(-2 * np.pi * arduino_period / cutoff_second)

        self.arduino: Optional[serial.Serial] = None

        # Measurement values
        self.storage_pressure: Optional[float] = None
        self.plant_pressure: Optional[float] = None
        self.plant_volume: Optional[float] = None
        self.purifier_pressure: Optional[float] = None
        self.last_read_time = time.time()

        # Connection management
        self.is_running = True

    def open_serial_connection(self):
        """Safely open a serial connection with proper error handling."""
        try:
            if self.arduino is not None and self.arduino.is_open:
                self.arduino.close()

            self.arduino = serial.Serial(
                self.port,
                self.baud_rate,
                timeout=self.serial_timeout,
            )
            self.arduino.flushInput()
            self.arduino.flushOutput()
            print(f"[SERIAL] Connected to {self.port} @ {self.baud_rate} baud")
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            self.arduino = None

    def close_resources(self):
        """Safely close all resources."""
        self.is_running = False
        if self.arduino is not None and self.arduino.is_open:
            self.arduino.close()

    @staticmethod
    def cal_pressure_storage(bit_value: float) -> float:
        return 0.06104 * bit_value - 5.82056

    @staticmethod
    def cal_pressure_plant(bit_value: float) -> float:
        return 0.01865 * bit_value - 3.40120

    @staticmethod
    def cal_pressure_purifier(bit_value: float) -> float:
        return 0.06104 * bit_value - 5.82056

    @staticmethod
    def level_to_volume(x: float) -> float:
        x2 = x * x
        x3 = x2 * x
        x4 = x3 * x
        return -7.70234 + 2.6769 * x - 0.00686 * x2 + 0.00048930 * x3 - 5.73005e-6 * x4

    def cal_volume_plant(self, bit_value: float) -> float:
        level = 0.06807 * bit_value - 0.81458
        return self.level_to_volume(level)

    def update_measurement(
        self, name: str, new_value: float, calculation_func
    ) -> None:
        """Update measurement with exponential filtering."""
        current_value = getattr(self, name)
        calculated_value = calculation_func(new_value)

        if current_value is None:
            setattr(self, name, calculated_value)
        else:
            filtered_value = (1 - self.beta) * calculated_value + self.beta * current_value
            setattr(self, name, filtered_value)

    def process_serial_data(self, data: str) -> None:
        """Process incoming serial data."""
        try:
            P_st_bit, P_pl_bit, V_pl_bit, P_pur_bit = map(float, data.strip().split(","))

            self.update_measurement("storage_pressure", P_st_bit, self.cal_pressure_storage)
            self.update_measurement("plant_pressure", P_pl_bit, self.cal_pressure_plant)
            self.update_measurement("plant_volume", V_pl_bit, self.cal_volume_plant)
            self.update_measurement("purifier_pressure", P_pur_bit, self.cal_pressure_purifier)

            self.last_read_time = time.time()

        except ValueError as e:
            print(f"Error processing serial data: {e}")

    def run(self) -> None:
        """Main loop for serial communication."""
        last_flush_time = time.time()

        while self.is_running:
            try:
                if self.arduino is None or not self.arduino.is_open:
                    self.open_serial_connection()
                    time.sleep(self.reconnect_delay)
                    continue

                if self.arduino.in_waiting:
                    data = self.arduino.readline().decode()
                    self.process_serial_data(data)

                current_time = time.time()
                if current_time - last_flush_time > self.buffer_flush_interval:
                    if self.arduino and self.arduino.is_open:
                        self.arduino.flushInput()
                        self.arduino.flushOutput()
                    last_flush_time = current_time

                time.sleep(self.loop_sleep)

            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
                self.arduino = None
                time.sleep(self.reconnect_delay)

            except Exception as e:
                print(f"Unexpected error: {e}")
                self.arduino = None
                time.sleep(self.reconnect_delay)


def main():
    config = load_config()
    mediator = SerialMediator(config)
    localserver_port = config["localserver_port"]

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/Meas":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                data = {
                    "P_st": None if mediator.storage_pressure is None else f"{mediator.storage_pressure:.3f}",
                    "P_pl": None if mediator.plant_pressure is None else f"{mediator.plant_pressure:.3f}",
                    "V_pl": None if mediator.plant_volume is None else f"{mediator.plant_volume:.3f}",
                    "P_pur": None if mediator.purifier_pressure is None else f"{mediator.purifier_pressure:.3f}",
                    "timestamp": mediator.last_read_time,
                }

                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return

    def run_simple_server():
        server_address = ("", localserver_port)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        print(f"[HTTP] Server started on localhost:{localserver_port}")
        httpd.serve_forever()

    server_thread = threading.Thread(target=run_simple_server)
    server_thread.daemon = True
    server_thread.start()

    try:
        mediator.run()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        mediator.close_resources()


if __name__ == "__main__":
    main()
