import matplotlib.dates as mdates
from matplotlib.ticker import Locator
from datetime import timedelta
from VariousTimeDeque import Interval

class CustomDateLocator(Locator):
    def __init__(self, interval: Interval):
        self.interval: Interval = interval

    def __call__(self):
        try:
            vmin, vmax = self.axis.get_view_interval()

            start = mdates.num2date(vmin).replace(microsecond=0, tzinfo=None)
            end = mdates.num2date(vmax).replace(microsecond=0, tzinfo=None)
            
            # 시간 범위가 너무 짧은 경우 처리
            time_diff = (end - start).total_seconds()
            
            if time_diff < 5:  # 5초 미만이면 기본 locator 사용
                from matplotlib.dates import AutoDateLocator
                return AutoDateLocator().tick_values(vmin, vmax)
            
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
            max_iterations = 1000  # 무한 루프 방지
            iteration_count = 0
            
            while current <= end and iteration_count < max_iterations:
                dates.append(current)
                iteration_count += 1
                
                if self.interval == Interval.ONE_SECOND:
                    current += timedelta(seconds=20)
                elif self.interval == Interval.ONE_MINUTE:
                    current += timedelta(minutes=20)
                elif self.interval == Interval.TEN_MINUTES:
                    current += timedelta(minutes=120)
                elif self.interval == Interval.ONE_HOUR:
                    current += timedelta(hours=10)
            
            if iteration_count >= max_iterations:
                print(f"[WARNING] 최대 반복 횟수 도달, 기본 locator 사용")
                from matplotlib.dates import AutoDateLocator
                return AutoDateLocator().tick_values(vmin, vmax)
            
            result = [mdates.date2num(date) for date in dates]
            return result
            
        except Exception as e:
            print(f"[ERROR] CustomDateLocator.__call__() 에러: {e}")
            # 에러 발생 시 기본 locator 사용
            try:
                from matplotlib.dates import AutoDateLocator
                return AutoDateLocator().tick_values(vmin, vmax)
            except:
                return []