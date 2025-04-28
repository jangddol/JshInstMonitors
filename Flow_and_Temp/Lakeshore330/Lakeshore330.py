import pyvisa
import json 
import atexit
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

class Lakeshore330:
    # Lakeshore330 클래스는 그대로 유지
    def __init__(self, device_address: str):
        self.rm = pyvisa.ResourceManager()
        try:
            self.device = self.rm.open_resource(device_address)
        except pyvisa.VisaIOError as e:
            print(f"Error opening device: {e}")
            self.device = None
        atexit.register(self.close)

    def close(self):
        self.device.close()

    def get_sensor_value_pair(self)-> tuple[str, str]:
        self.device.write('SDAT?')
        head_temp = str(self.device.read())[:7]
        self.device.write('CDAT?')
        tip_temp = str(self.device.read())[:7]

        if head_temp.replace(" ", "") == 'OL':
            head_temp = "00.000"
        if tip_temp.replace(" ", "") == 'OL':
            tip_temp = "00.000"

        head_temp = head_temp + " K"
        tip_temp = tip_temp + " K"
        return head_temp, tip_temp

class SensorHandler(BaseHTTPRequestHandler):
    lakeshore = None  # 전역 변수로 Lakeshore330 인스턴스를 저장할 변수

    def do_GET(self):
        if self.path == '/sensor_pair':
            try:
                valueA, valueB = self.lakeshore.get_sensor_value_pair()
                response = {
                    'valueA': valueA,
                    'valueB': valueB,
                    'timestamp': time.time()
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

def open_config_file(file_path: str):
    with open(file_path, 'r') as file:
        config_data = json.load(file)
        device_address = config_data.get('device_address')
        port = config_data.get('port')

        if not isinstance(device_address, str) or not isinstance(port, int):
            raise ValueError("Invalid configuration data")

        return device_address, port

if __name__ == '__main__':
    config_file_path = 'lakeshore330_config.json'
    try:
        device_address, port = open_config_file(config_file_path)
    except Exception as e:
        print(e)
        with open(config_file_path, 'w') as file:
            json.dump({'device_address': 'GPIB1::30::INSTR', 'port': 5001}, file)
        device_address, port = open_config_file(config_file_path)

    # Lakeshore330 인스턴스를 핸들러 클래스의 클래스 변수로 설정
    SensorHandler.lakeshore = Lakeshore330(device_address)

    server = HTTPServer(('0.0.0.0', port), SensorHandler)
    print(f'Server running on port {port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
