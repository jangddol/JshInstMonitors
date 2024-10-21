import matplotlib.dates as mdates
from matplotlib.ticker import Locator
from datetime import timedelta

class CustomDateLocator(Locator):
    def __init__(self, interval):
        self.interval = interval

    def __call__(self):
        vmin, vmax = self.axis.get_view_interval()
        start = mdates.num2date(vmin).replace(microsecond=0)
        end = mdates.num2date(vmax).replace(microsecond=0)
        
        if self.interval == 1:
            start = start.replace(second=start.second - start.second % 20)
        elif self.interval == 60:
            start = start.replace(minute=start.minute - start.minute % 20, second=0)
        elif self.interval == 600:
            start = start.replace(minute=start.minute - start.minute % 120, second=0)
        elif self.interval == 3600:
            start = start.replace(hour=start.hour - start.hour % 10, minute=0, second=0)
        
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            if self.interval == 1:
                current += timedelta(seconds=20)
            elif self.interval == 60:
                current += timedelta(minutes=20)
            elif self.interval == 600:
                current += timedelta(minutes=120)
            elif self.interval == 3600:
                current += timedelta(hours=10)
        
        return [mdates.date2num(date) for date in dates]