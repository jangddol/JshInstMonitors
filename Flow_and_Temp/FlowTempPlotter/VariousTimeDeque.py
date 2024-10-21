import time
from collections import deque
from datetime import datetime, timedelta

MAXLEN = 100

class VariousTimeDeque:
    def __init__(self, numdata):
        self.numdata = numdata
        self.time_1s = deque(maxlen=MAXLEN)
        self.data_1s = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1min = deque(maxlen=MAXLEN)
        self.data_1min = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_10min = deque(maxlen=MAXLEN)
        self.data_10min = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1hour = deque(maxlen=MAXLEN)
        self.data_1hour = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        
        self.update_data([0] * numdata, time.time())
        
    def update_data(self, data, time):
        if len(data) != self.numdata:
            raise ValueError("Data length mismatch")
        
        if isinstance(time, datetime):
            _time = time
        elif isinstance(time, float):
            _time = datetime.fromtimestamp(time)
        else:
            raise ValueError("Invalid time type")

        self.time_1s.append(_time)
        for i in range(self.numdata):
            self.data_1s[i].append(data[i])
        
        if len(self.time_1min) == 0 or _time - self.time_1min[-1] >= timedelta(minutes=1):
            self.time_1min.append(_time)
            for i in range(self.numdata):
                self.data_1min[i].append(data[i])
        
        if len(self.time_10min) == 0 or _time - self.time_10min[-1] >= timedelta(minutes=10):
            self.time_10min.append(_time)
            for i in range(self.numdata):
                self.data_10min[i].append(data[i])
        
        if len(self.time_1hour) == 0 or _time - self.time_1hour[-1] >= timedelta(hours=1):
            self.time_1hour.append(_time)
            for i in range(self.numdata):
                self.data_1hour[i].append(data[i])

    def get_time_deque(self, interval):
        if interval == 1:
            return self.time_1s
        elif interval == 60:
            return self.time_1min
        elif interval == 600:
            return self.time_10min
        elif interval == 3600:
            return self.time_1hour
        return None
    
    def get_data_deque(self, interval):
        if interval == 1:
            return self.data_1s
        elif interval == 60:
            return self.data_1min
        elif interval == 600:
            return self.data_10min
        elif interval == 3600:
            return self.data_1hour
        return None
    
    def get_last_time(self):
        return self.time_1s[-1]
    
    def get_last_1min_time(self):
        return self.time_1min[-1]
    
    def get_last_10min_time(self):
        return self.time_10min[-1]
    
    def get_last_1hour_time(self):
        return self.time_1hour[-1]
    
    def get_last_data(self):
        return [x[-1] for x in self.data_1s]

    def set_test_data(self):
        for _ in range(MAXLEN):
            for i in range(self.numdata):
                self.data_1s[i].append(0.5)
                self.data_1min[i].append(0.5)
                self.data_10min[i].append(0.5)
                self.data_1hour[i].append(0.5)
        
        end_time = time.time()
        for i in range(MAXLEN):
            self.time_1s.append(datetime.fromtimestamp(end_time - MAXLEN + i))
            self.time_1min.append(datetime.fromtimestamp(end_time - MAXLEN * 60 + 60 *i))
            self.time_10min.append(datetime.fromtimestamp(end_time - MAXLEN * 600 + 600 * i))
            self.time_1hour.append(datetime.fromtimestamp(end_time - MAXLEN * 3600 + 3600 * i))