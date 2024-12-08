import pyvisa
import json 
import atexit
from flask import Flask, jsonify


class Lakeshore330:
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
        head_temp = str(self.device.read())[:7] + " K"
        self.device.write('CDAT?')
        tip_temp = str(self.device.read())[:7] + " K"
        return head_temp, tip_temp


def open_config_file(file_path: str):
    with open(file_path, 'r') as file: # open json from file_path
        config_data = json.load(file)
        device_address = config_data.get('device_address')
        port = config_data.get('port')
        
        if not isinstance(device_address, str) or not isinstance(port, int): # parsing json, check error from casting
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

    app = Flask(__name__)
    drc91c = Lakeshore330(device_address)

    @app.route('/sensor_pair')
    def get_sensor_value_pair():
        valueA, valueB = drc91c.get_sensor_value_pair()
        print(valueA, valueB)
        return jsonify({'valueA': valueA, 'valueB': valueB})

    app.run(host='0.0.0.0', port=port)
