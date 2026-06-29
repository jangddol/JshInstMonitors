import time
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Sequence, Tuple

MAXLEN = 100

class Interval(Enum):
    ONE_SECOND = 1
    ONE_MINUTE = 60
    TEN_MINUTES = 600
    ONE_HOUR = 3600


_INTERVAL_LOAD_SPECS: List[Tuple[Interval, timedelta]] = [
    (Interval.ONE_SECOND, timedelta(seconds=1)),
    (Interval.ONE_MINUTE, timedelta(minutes=1)),
    (Interval.TEN_MINUTES, timedelta(minutes=10)),
    (Interval.ONE_HOUR, timedelta(hours=1)),
]


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

    def get_time_deque(self, interval: Interval):
        if interval == Interval.ONE_SECOND:
            return self.time_1s
        elif interval == Interval.ONE_MINUTE:
            return self.time_1min
        elif interval == Interval.TEN_MINUTES:
            return self.time_10min
        elif interval == Interval.ONE_HOUR:
            return self.time_1hour
        raise ValueError("Invalid interval")

    def get_data_deque(self, interval: Interval):
        if interval == Interval.ONE_SECOND:
            return self.data_1s
        elif interval == Interval.ONE_MINUTE:
            return self.data_1min
        elif interval == Interval.TEN_MINUTES:
            return self.data_10min
        elif interval == Interval.ONE_HOUR:
            return self.data_1hour
        raise ValueError("Invalid interval")

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

    def clear(self) -> None:
        """Remove all stored samples from every interval buffer."""
        self.time_1s.clear()
        self.time_1min.clear()
        self.time_10min.clear()
        self.time_1hour.clear()
        for channel in self.data_1s + self.data_1min + self.data_10min + self.data_1hour:
            channel.clear()

    def load_historical(
        self,
        records: Sequence[Tuple[datetime, Sequence[float]]],
        reference_time: datetime | None = None,
    ) -> None:
        """Populate buffers from past log records.

        For each interval with period T and maxlen N, only records at or after
        ``reference_time - N * T`` are considered. The 1 s buffer keeps every
        record in that window; coarser buffers subsample with the same spacing
        rules as :meth:`update_data`.
        """
        if reference_time is None:
            reference_time = datetime.now()

        self.clear()

        for interval, min_delta in _INTERVAL_LOAD_SPECS:
            window = timedelta(seconds=MAXLEN * interval.value)
            cutoff = reference_time - window
            time_deque = self.get_time_deque(interval)
            data_deques = self.get_data_deque(interval)

            last_time: datetime | None = None
            for dt, data in records:
                if dt < cutoff:
                    continue
                if interval != Interval.ONE_SECOND:
                    if last_time is not None and dt - last_time < min_delta:
                        continue

                time_deque.append(dt)
                for i in range(self.numdata):
                    data_deques[i].append(data[i])
                last_time = dt

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
