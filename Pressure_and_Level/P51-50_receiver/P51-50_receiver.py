import serial
import numpy as np
import time

storage_pressure = None
plant_pressure = None
plant_volume = None
last_read_time = time.time()

def open_serials():
    Arduino = serial.Serial('COM4', 9600, timeout=1)
    Arduino.flushInput()
    Arduino.flushOutput()
    return Arduino

def cal_pressure_storage(storage_pressure_bit):
    storage_pressure_bit = float(storage_pressure_bit)
    storage_pressure = 0.06104 * storage_pressure_bit - 5.82056
    return storage_pressure

def cal_pressure_plant(plant_pressure_bit):
    plant_pressure_bit = float(plant_pressure_bit)
    plant_pressure = 0.01865 * plant_pressure_bit - 3.40120
    return plant_pressure

def level_to_volume(x):
    x2 = x * x
    x3 = x2 * x
    x4 = x3 * x
    a0 = -7.70234
    a1 = 2.6769
    a2 = -0.00686
    a3 = 0.00048930
    a4 = -5.73005e-6
    return a0 + a1 * x + a2 * x2 + a3 * x3 + a4 * x4

def cal_volume_plant(plant_volume_bit):
    plant_volume_bit = float(plant_volume_bit)
    plant_volume_level = 0.06807 * plant_volume_bit - 0.81458
    plant_volume = level_to_volume(plant_volume_level)
    return plant_volume

def serial_mediator():
    cutoff_second = 10
    BETA = np.exp(-2 * np.pi * 0.1 / cutoff_second)
    Arduino = open_serials()
    while True:
        try:
            if Arduino.in_waiting:
                P_st_bit, P_pl_bit, V_pl_bit = Arduino.readline().decode().strip().split(',')
                print(f"P_st bit: {P_st_bit}, P_pl_bit: {P_pl_bit}, V_pl bit: {V_pl_bit}")
                global storage_pressure
                global plant_pressure
                global plant_volume
                global last_read_time
                if storage_pressure is None:
                    storage_pressure = cal_pressure_storage(P_st_bit)
                else:
                    storage_pressure = (1-BETA) * cal_pressure_storage(P_st_bit) + BETA * storage_pressure
                if plant_pressure is None:
                    plant_pressure = cal_pressure_plant(P_pl_bit)
                else:
                    plant_pressure = (1-BETA) * cal_pressure_plant(P_pl_bit) + BETA * plant_pressure
                if plant_volume is None:
                    plant_volume = cal_volume_plant(V_pl_bit)
                else:
                    plant_volume = (1-BETA) * cal_volume_plant(V_pl_bit) + BETA * plant_volume
                last_read_time = time.time()
            time.sleep(0.1)
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
        global plant_pressure
        global plant_volume
        global last_read_time
        P_st_string = 'None' if storage_pressure is None else f"{storage_pressure:.3f}"
        P_pl_string = 'None' if plant_pressure is None else f"{plant_pressure:.3f}"
        V_pl_string = 'None' if plant_volume is None else f"{plant_volume:.3f}"
        return jsonify({'P_st': P_st_string, 'P_pl': P_pl_string, 'V_pl': V_pl_string, 'timestamp': last_read_time})

    def run_flask():
        app.run(host='0.0.0.0', port=5003, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    serial_mediator()