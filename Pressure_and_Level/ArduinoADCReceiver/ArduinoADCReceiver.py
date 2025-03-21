import serial
import numpy as np
import time
from typing import Optional


class SerialMediator:
    def __init__(self, port: str = 'COM4', baud_rate: int = 9600):
        self.port = port
        self.baud_rate = baud_rate
        self.arduino: Optional[serial.Serial] = None
        self.cutoff_second = 10
        self.arduino_period = 0.5
        self.beta = np.exp(-2 * np.pi * self.arduino_period / self.cutoff_second)

        # Measurement values
        self.storage_pressure: Optional[float] = None
        self.plant_pressure: Optional[float] = None
        self.plant_volume: Optional[float] = None
        self.purifier_pressure: Optional[float] = None
        self.last_read_time = time.time()

        # Connection management
        self.is_running = True
        self.reconnect_delay = 1.0  # seconds

    def open_serial(self) -> None:
        """Safely open serial connection with proper error handling"""
        try:
            if self.arduino is not None and self.arduino.is_open:
                self.arduino.close()

            self.arduino = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.arduino.flushInput()
            self.arduino.flushOutput()
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            self.arduino = None

    def close(self) -> None:
        """Safely close all resources"""
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

    def update_measurement(self, name: str, new_value: float, 
                         calculation_func) -> None:
        """Update measurement with exponential filtering"""
        current_value = getattr(self, name)
        calculated_value = calculation_func(new_value)

        if current_value is None:
            setattr(self, name, calculated_value)
        else:
            filtered_value = (1 - self.beta) * calculated_value + self.beta * current_value
            setattr(self, name, filtered_value)

    def process_serial_data(self, data: str) -> None:
        """Process incoming serial data"""
        try:
            P_st_bit, P_pl_bit, V_pl_bit, P_pur_bit = map(float, data.strip().split(','))

            self.update_measurement('storage_pressure', P_st_bit, self.cal_pressure_storage)
            self.update_measurement('plant_pressure', P_pl_bit, self.cal_pressure_plant)
            self.update_measurement('plant_volume', V_pl_bit, self.cal_volume_plant)
            self.update_measurement('purifier_pressure', P_pur_bit, self.cal_pressure_purifier)

            self.last_read_time = time.time()

        except ValueError as e:
            print(f"Error processing serial data: {e}")

    def run(self) -> None:
        """Main loop for serial communication"""
        last_flush_time = time.time()
        
        while self.is_running:
            try:
                if self.arduino is None or not self.arduino.is_open:
                    self.open_serial()
                    time.sleep(self.reconnect_delay)
                    continue

                if self.arduino.in_waiting:
                    data = self.arduino.readline().decode()
                    self.process_serial_data(data)

                # 주기적으로 버퍼 비우기 (예: 30초마다)
                current_time = time.time()
                if current_time - last_flush_time > 30:
                    if self.arduino and self.arduino.is_open:
                        self.arduino.flushInput()
                        self.arduino.flushOutput()
                    last_flush_time = current_time

                time.sleep(0.1)

            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
                self.arduino = None
                time.sleep(self.reconnect_delay)

            except Exception as e:
                print(f"Unexpected error: {e}")
                self.arduino = None
                time.sleep(self.reconnect_delay)


def main():
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    mediator = SerialMediator()

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/Meas':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                data = {
                    'P_st': None if mediator.storage_pressure is None else f"{mediator.storage_pressure:.3f}",
                    'P_pl': None if mediator.plant_pressure is None else f"{mediator.plant_pressure:.3f}",
                    'V_pl': None if mediator.plant_volume is None else f"{mediator.plant_volume:.3f}",
                    'P_pur': None if mediator.purifier_pressure is None else f"{mediator.purifier_pressure:.3f}",
                    'timestamp': mediator.last_read_time
                }
                
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()

    def run_simple_server():
        server_address = ('', 5003)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        httpd.serve_forever()

    server_thread = threading.Thread(target=run_simple_server)
    server_thread.daemon = True
    server_thread.start()

    try:
        # Run the serial mediator
        mediator.run()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        mediator.close()

if __name__ == "__main__":
    main()
