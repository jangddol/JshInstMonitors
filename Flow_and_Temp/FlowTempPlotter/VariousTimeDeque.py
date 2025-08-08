import time
from collections import deque
from datetime import datetime, timedelta
from typing import List, Deque, Union
from enum import Enum

MAXLEN = 100

class Interval(Enum):
    ONE_SECOND = 1
    ONE_MINUTE = 60
    TEN_MINUTES = 600
    ONE_HOUR = 3600

class VariousTimeDeque:
    def __init__(self, numdata: int):
        """Initialize the VariousTimeDeque with the specified number of data streams.

        Args:
            numdata (int): The number of data streams to manage.
        """
        self.numdata: int = numdata
        self.time_1s: Deque[datetime] = deque(maxlen=MAXLEN)
        self.data_1s: List[Deque[float]] = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1min: Deque[datetime] = deque(maxlen=MAXLEN)
        self.data_1min: List[Deque[float]] = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_10min: Deque[datetime] = deque(maxlen=MAXLEN)
        self.data_10min: List[Deque[float]] = [deque(maxlen=MAXLEN) for _ in range(numdata)]
        self.time_1hour: Deque[datetime] = deque(maxlen=MAXLEN)
        self.data_1hour: List[Deque[float]] = [deque(maxlen=MAXLEN) for _ in range(numdata)]

        self.update_data([0] * numdata, time.time())

    def update_data(self, data: List[float], timestamp: Union[float, datetime]):
        """Update the deque with new data and timestamp.

        Args:
            data (List[float]): A list of new data points.
            timestamp (Union[float, datetime]): The timestamp associated with the data.
        """
        if len(data) != self.numdata:
            raise ValueError("Data length mismatch")
        
        if isinstance(timestamp, datetime):
            _time = timestamp
        elif isinstance(timestamp, float):
            _time = datetime.fromtimestamp(timestamp)
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

    def get_time_deque(self, interval: Interval) -> Union[Deque[datetime], None]:
        """Retrieve the time deque for the specified interval.

        Args:
            interval (Interval): The interval as an Enum (ONE_SECOND, ONE_MINUTE, TEN_MINUTES, ONE_HOUR).

        Returns:
            Union[Deque[datetime], None]: The corresponding time deque or None if invalid interval.
        """
        if interval == Interval.ONE_SECOND:
            return self.time_1s
        elif interval == Interval.ONE_MINUTE:
            return self.time_1min
        elif interval == Interval.TEN_MINUTES:
            return self.time_10min
        elif interval == Interval.ONE_HOUR:
            return self.time_1hour
        return None
    
    def get_data_deque(self, interval: Interval) -> Union[List[Deque[float]], None]:
        """Retrieve the data deque for the specified interval.

        Args:
            interval (Interval): The interval as an Enum (ONE_SECOND, ONE_MINUTE, TEN_MINUTES, ONE_HOUR).

        Returns:
            Union[List[Deque[float]], None]: The corresponding data deque or None if invalid interval.
        """
        if interval == Interval.ONE_SECOND:
            return self.data_1s
        elif interval == Interval.ONE_MINUTE:
            return self.data_1min
        elif interval == Interval.TEN_MINUTES:
            return self.data_10min
        elif interval == Interval.ONE_HOUR:
            return self.data_1hour
        return None
    
    def get_last_time(self) -> datetime:
        return self.time_1s[-1]
    
    def get_last_1min_time(self) -> datetime:
        return self.time_1min[-1]
    
    def get_last_10min_time(self) -> datetime:
        return self.time_10min[-1]
    
    def get_last_1hour_time(self) -> datetime:
        return self.time_1hour[-1]
    
    def get_last_data(self) -> List[float]:
        return [x[-1] for x in self.data_1s]

    def set_test_data(self):
        """Populate the deques with test data for debugging purposes."""
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