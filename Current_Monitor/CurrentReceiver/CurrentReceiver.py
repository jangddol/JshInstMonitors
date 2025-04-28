import serial
import numpy as np
import time
from typing import Optional


class SerialMediator:
    def __init__(self, port: str = 'COM5', baud_rate: int = 9600):
        self.port = port
        self.baud_rate = baud_rate
        self.arduino: Optional[serial.Serial] = None

        # Measurement values
        self.current: Optional[float] = None
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
    def cal_current(bit_value: float) -> float:
        """Convert ADC bit value to current"""
        resistor = 3.0 # Ohm
        arduino_max_bit = 1023.0
        arduino_max_voltage = 5.0 # V
        return bit_value * arduino_max_voltage / arduino_max_bit / resistor

    def process_serial_data(self, data: str) -> None:
        """Process incoming serial data"""
        try:
            current_bit = map(float, data.strip().split(','))
            self.current = SerialMediator.cal_current(current_bit)
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
                    'Current': None if mediator.current is None else f"{mediator.current:.3f}",
                    'timestamp': mediator.last_read_time
                }
                
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()

    def run_simple_server():
        server_address = ('', 5005)
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
