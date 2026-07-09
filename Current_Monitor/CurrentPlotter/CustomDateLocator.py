import matplotlib.dates as mdates
from matplotlib.ticker import Locator
from datetime import timedelta
from typing import List

from VariousTimeDeque import Interval


class CustomDateLocator(Locator):
    def __init__(self, interval: Interval):
        self.interval: Interval = interval

    def __call__(self) -> List[float]:
        vmin, vmax = self.axis.get_view_interval()
        start = mdates.num2date(vmin).replace(microsecond=0)
        end = mdates.num2date(vmax).replace(microsecond=0)

        if self.interval == Interval.ONE_SECOND:
            start = start.replace(second=start.second - start.second % 20)
        elif self.interval == Interval.ONE_MINUTE:
            start = start.replace(minute=start.minute - start.minute % 20, second=0)
        elif self.interval == Interval.TEN_MINUTES:
            start = start.replace(minute=start.minute - start.minute % 120, second=0)
        elif self.interval == Interval.ONE_HOUR:
            start = start.replace(hour=start.hour - start.hour % 10, minute=0, second=0)

        dates = []
        current = start
        while current <= end:
            dates.append(current)
            if self.interval == Interval.ONE_SECOND:
                current += timedelta(seconds=20)
            elif self.interval == Interval.ONE_MINUTE:
                current += timedelta(minutes=20)
            elif self.interval == Interval.TEN_MINUTES:
                current += timedelta(minutes=120)
            elif self.interval == Interval.ONE_HOUR:
                current += timedelta(hours=10)

        return [mdates.date2num(date) for date in dates]
