import time
import pyvisa
import enum


class Sensor(enum.Enum):
    A = 'A'
    B = 'B'
    
    def cmd(self):
        if self == Sensor.A:
            return 'F2A'
        elif self == Sensor.B:
            return 'F2B'


class DRC91C:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.device = self.rm.open_resource('GPIB1::15::INSTR')
        self.control_sensor = self.get_current_control_sensor()
        self.set_proper_display_sensor()

    def __del__(self):
        self.close()

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


if __name__ == '__main__':
    from flask import Flask, jsonify
    app = Flask(__name__)
    drc91c = DRC91C()

    @app.route('/sensor_pair')
    def get_sensor_value_pair():
        valueA, valueB = drc91c.get_sensor_value_pair()
        print(valueA, valueB)
        return jsonify({'valueA': valueA, 'valueB': valueB})

    app.run(host='0.0.0.0', port=5001)
