import serial
import numpy as np

storage_pressure = None

def open_serials():
    Arduino = serial.Serial('COM4', 9600, timeout=1)
    Arduino.flushInput()
    Arduino.flushOutput()
    return Arduino

def cal_pressure(pressure_bit):
    pressure_bit = float(pressure_bit)
    pressure = 0.06104 * pressure_bit - 5.82056
    return pressure

def serial_mediator():
    cutoff_second = 10
    BETA = np.exp(-2 * np.pi * 0.1 / cutoff_second)
    Arduino = open_serials()
    while True:
        try:
            if Arduino.in_waiting:
                pressure_bit = Arduino.readline().decode().strip()
                print(f"Pressure bit: {pressure_bit}")
                global storage_pressure
                if storage_pressure is None:
                    storage_pressure = cal_pressure(pressure_bit)
                else:
                    storage_pressure = (1-BETA) * cal_pressure(pressure_bit) + BETA * storage_pressure
        except Exception as e:
            print(f"Error : {e}")
            Arduino.close()
            Arduino = open_serials()


if __name__ == "__main__":
    import threading
    from flask import Flask, jsonify
    import logging

    app = Flask(__name__)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    @app.route('/Meas', methods=['GET'])
    def Meas():
        global storage_pressure
        if storage_pressure is None:
            return jsonify({'StoragePressure': 'None'})
        return jsonify({'StoragePressure': f"{storage_pressure:.3f}"})

    def run_flask():
        app.run(host='0.0.0.0', port=5003, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    serial_mediator()