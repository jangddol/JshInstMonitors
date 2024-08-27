import tkinter as tk
from channel import ChannelName
import enum

class Wday(enum.Enum):
    Mon = "Mon"
    Tue = "Tue"
    Wed = "Wed"
    Thu = "Thu"
    Fri = "Fri"
    Sat = "Sat"
    Sun = "Sun"
    
    def get_int(self):
        if self == Wday.Mon:
            return 0
        if self == Wday.Tue:
            return 1
        if self == Wday.Wed:
            return 2
        if self == Wday.Thu:
            return 3
        if self == Wday.Fri:
            return 4
        if self == Wday.Sat:
            return 5
        if self == Wday.Sun:
            return 6
        return -1

class Action(enum.Enum):
    On = "On"
    Off = "Off"
    Setpoint = "Setpoint 변경"

class ScheduleWidget:
    def __init__(self, parent, index):
        self.parent = parent
        self.index = index
        self.frame = tk.Frame(self.parent.schedule_frame)
        
        self.day_var = tk.StringVar(value=Wday.Mon.value)
        self.hour_var = tk.IntVar(value=12)
        self.minute_var = tk.IntVar(value=0)
        self.channel_var = tk.StringVar(value=ChannelName.Tip.value)
        self.action_var = tk.StringVar(value=Action.On.value)
        self.number_var = tk.StringVar(value="1")  # StringVar로 변경

        self.create_widgets()
    
    @property
    def day(self) -> Wday:
        return Wday(self.day_var.get())

    @property
    def hour(self) -> int:
        return self.hour_var.get()
    
    @property
    def minute(self) -> int:
        return self.minute_var.get()
    
    @property
    def channelname(self) -> ChannelName:
        return ChannelName(self.channel_var.get())
    
    @property
    def action(self) -> Action:
        return Action(self.action_var.get())
    
    @property
    def number(self) -> int:
        return int(self.number_var.get())
    
    def create_widgets(self):
        tk.Label(self.frame, text=f"스케줄 {self.index + 1}").grid(row=0, column=0, columnspan=5)

        tk.Label(self.frame, text="요일:").grid(row=1, column=0)
        tk.OptionMenu(self.frame, self.day_var, Wday.Mon.value, Wday.Tue.value, Wday.Wed.value, Wday.Thu.value, Wday.Fri.value, Wday.Sat.value, Wday.Sun.value).grid(row=1, column=1)

        tk.Label(self.frame, text="시간:").grid(row=1, column=2)
        self.hour_spinbox = tk.Spinbox(self.frame, from_=0, to=23, textvariable=self.hour_var, width=3, format="%02.0f", validate="key")
        self.hour_spinbox['validatecommand'] = (self.frame.register(self.validate_hour), '%P')
        self.hour_spinbox.grid(row=1, column=3)

        tk.Label(self.frame, text="분:").grid(row=1, column=4)
        self.minute_spinbox = tk.Spinbox(self.frame, from_=0, to=59, textvariable=self.minute_var, width=3, format="%02.0f", validate="key")
        self.minute_spinbox['validatecommand'] = (self.frame.register(self.validate_minute), '%P')
        self.minute_spinbox.grid(row=1, column=5)

        tk.Label(self.frame, text="채널:").grid(row=1, column=6)
        tk.OptionMenu(self.frame, self.channel_var, ChannelName.Tip.value, ChannelName.Shield.value, ChannelName.Vent.value).grid(row=1, column=7)

        tk.Label(self.frame, text="동작:").grid(row=1, column=8)
        action_menu = tk.OptionMenu(self.frame, self.action_var, Action.On.value, Action.Off.value, Action.Setpoint.value, command=self.update_number_entry)
        action_menu.grid(row=1, column=9)

        tk.Label(self.frame, text="숫자:").grid(row=1, column=10)
        self.number_entry = tk.Entry(self.frame, textvariable=self.number_var, validate="key")
        self.number_entry['validatecommand'] = (self.frame.register(self.validate_integer), '%P')
        self.number_entry.grid(row=1, column=11)
        self.update_number_entry()

        tk.Button(self.frame, text="위로", command=self.move_up).grid(row=1, column=12)
        tk.Button(self.frame, text="아래로", command=self.move_down).grid(row=1, column=13)
        tk.Button(self.frame, text="삭제", command=self.delete_schedule).grid(row=1, column=14)  # 삭제 버튼 추가

        self.frame.pack(fill=tk.X)

    def validate_hour(self, new_value):
        if new_value == "":
            return True
        try:
            int_value = int(new_value)
            return 0 <= int_value <= 23 and not new_value.startswith('0')
        except ValueError:
            return False

    def validate_minute(self, new_value):
        if new_value == "":
            return True
        try:
            int_value = int(new_value)
            return 0 <= int_value <= 59 and not new_value.startswith('0')
        except ValueError:
            return False

    def validate_integer(self, new_value):
        if new_value == "":
            return True  # 빈 문자열은 허용
        try:
            int_value = int(new_value)
            return True  # 정수로 변환 가능하면 허용
        except ValueError:
            return False  # 정수가 아니면 거부

    def update_number_entry(self, *args):
        if self.action_var.get() in ["On", "Off"]:
            self.number_entry.config(state='disabled')  # 비활성화
            self.number_var.set("")  # 비활성화 시 값 초기화
        else:
            self.number_entry.config(state='normal')  # 활성화

    def move_up(self):
        self.parent.move_schedule(self.index, -1)

    def move_down(self):
        self.parent.move_schedule(self.index, 1)
    
    def delete_schedule(self):
        self.parent.delete_schedule(self.index)  # 부모에게 삭제 요청
    
    def recreate_frame(self):
        self.frame.destroy()
        self.frame = tk.Frame(self.parent.schedule_frame)
        self.create_widgets()

class SchedularWindow:
    def __init__(self, mother):
        self.mother = mother
        self.root = None
        self.create_window()

    def create_window(self):
        if self.root and self.root.winfo_exists():
            self.root.lift()
            self.root.focus_force()
            return

        self.root = tk.Toplevel(self.mother)
        self.root.iconbitmap("MFC.ico")
        self.root.title("Schedular")
        self.root.geometry("700x300")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.schedule_widgets = []
        self.schedule_count = 0

        self.add_schedule_button = tk.Button(self.root, text="스케줄 추가", command=self.add_schedule)
        self.add_schedule_button.pack(pady=10)

        self.schedule_frame = tk.Frame(self.root)
        self.schedule_frame.pack(fill=tk.BOTH, expand=True)

    def add_schedule(self):
        schedule_widget = ScheduleWidget(self, self.schedule_count)
        self.schedule_widgets.append(schedule_widget)
        self.schedule_count += 1
        # self.update_schedule_display()  # 스케줄 추가 후 화면 업데이트
    
    def delete_schedule(self, index):
        if 0 <= index < len(self.schedule_widgets):
            del self.schedule_widgets[index]
            self.schedule_count -= 1
            self.update_schedule_display()  # 스케줄 삭제 후 화면 업데이트

    def move_schedule(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.schedule_widgets):
            self.schedule_widgets[index], self.schedule_widgets[new_index] = self.schedule_widgets[new_index], self.schedule_widgets[index]
            self.update_schedule_display()

    def update_schedule_display(self):
        for widget in self.schedule_frame.winfo_children():
            widget.destroy()
        for i, schedule_widget in enumerate(self.schedule_widgets):
            schedule_widget.index = i
            schedule_widget.recreate_frame()
            schedule_widget.frame.pack(fill=tk.X)

    def on_close(self):
        self.root.withdraw()
    
    def show(self):
        # 창을 다시 보이게 하는 메서드
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

# 메인 애플리케이션을 위한 코드
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Main Window")
    root.geometry("400x300")

    schedular_window = SchedularWindow(root)

    root.mainloop()
