import time
import pyvisa
import enum
import json 
import atexit
from flask import Flask, jsonify


class Sensor(enum.Enum):
    A = 'A'
    B = 'B'
    
    def cmd(self):
        if self == Sensor.A:
            return 'F2A'
        elif self == Sensor.B:
            return 'F2B'


class DRC91C:
    def __init__(self, device_address: str):
        self.rm = pyvisa.ResourceManager()
        try:
            self.device = self.rm.open_resource(device_address)
        except pyvisa.VisaIOError as e:
            print(f"Error opening device: {e}")
            self.device = None
        self.control_sensor = self.get_current_control_sensor()
        self.set_proper_display_sensor()
        atexit.register(self.close)

    def close(self):
        self.device.close()

    def get_current_display_sensor(self):
        self.device.write('W1')
        result = self.device.read()
        display_sensor = Sensor(result[0])
        return display_sensor

    def get_current_control_sensor(self):
        self.device.write('W1')
        result = self.device.read()
        print(result)
        control_sensor = Sensor(result[3])
        return control_sensor

    def set_proper_display_sensor(self):
        if self.control_sensor == Sensor.A:
            self.select_sensor(Sensor.B)
        else:
            self.select_sensor(Sensor.A)

    def get_sensor_value(self):
        self.device.write('WS')
        result = self.device.read()
        return result

    def select_sensor(self, sensor: Sensor):
        self.device.write(sensor.cmd()+'0')
        while self.get_current_display_sensor() != sensor:
            time.sleep(0.001)

    def get_sensor_value_pair(self)-> tuple[str, str]:
        """
        Get the value of both sensors A and B.
        Note that after calling this method, the sensor will be set to B.

        Returns:
            tuple[str, str]: The value of sensor A and B. Each value is a string with the format '+XXX.XXK' where X is a digit.
        """
        self.device.write('W0')
        result = self.device.read()
        if self.control_sensor == Sensor.B:
            return result[:8], result[9:17]
        else:
            return result[9:17], result[:8]


def open_config_file(file_path: str):
    # json file has two keys: 'device_address' and 'port'
    # 'device_address' is the address of the GPIB address of the DRC91C·
    # 'port' is the port number of the server. It should be an integer in range of 0 to 65535.
    
    with open(file_path, 'r') as file: # open json from file_path
        config_data = json.load(file)
        device_address = config_data.get('device_address')
        port = config_data.get('port')
        
        if not isinstance(device_address, str) or not isinstance(port, int): # parsing json, check error from casting
            raise ValueError("Invalid configuration data")
        
        return device_address, port


if __name__ == '__main__':
    config_file_path = 'drc91c_config.json'
    # If loading fails, create a default config.json.
    try:
        device_address, port = open_config_file(config_file_path)
    except Exception as e:
        print(e)
        with open(config_file_path, 'w') as file:
            json.dump({'device_address': 'GPIB1::15::INSTR', 'port': 5001}, file)
        device_address, port = open_config_file(config_file_path)

    app = Flask(__name__)
    drc91c = DRC91C(device_address)

    @app.route('/sensor_pair')
    def get_sensor_value_pair():
        valueA, valueB = drc91c.get_sensor_value_pair()
        print(valueA, valueB)
        return jsonify({'valueA': valueA, 'valueB': valueB})

    app.run(host='0.0.0.0', port=port)
