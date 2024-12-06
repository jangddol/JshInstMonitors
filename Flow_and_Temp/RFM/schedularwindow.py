import json
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
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
        self.number_var = tk.IntVar(value=0)

        self.create_widgets()
    
    @property
    def day(self) -> Wday:
        return Wday(self.day_var.get())

    @property
    def hour(self) -> int:
        return int(str(self.hour_var.get()))
    
    @property
    def minute(self) -> int:
        return int(str(self.minute_var.get()))
    
    @property
    def channelname(self) -> ChannelName:
        return ChannelName(self.channel_var.get())
    
    @property
    def action(self) -> Action:
        return Action(self.action_var.get())
    
    @property
    def number(self) -> int:
        return int(str(self.number_var.get()))
    
    def create_widgets(self):
        tk.Label(self.frame, text=f"스케줄 {self.index + 1}").grid(row=0, column=0, columnspan=5)

        tk.Label(self.frame, text="요일:").grid(row=1, column=0)
        tk.OptionMenu(self.frame, self.day_var, Wday.Mon.value, Wday.Tue.value, Wday.Wed.value, Wday.Thu.value, Wday.Fri.value, Wday.Sat.value, Wday.Sun.value).grid(row=1, column=1)

        tk.Label(self.frame, text="시간:").grid(row=1, column=2)
        self.hour_spinbox = tk.Spinbox(self.frame, from_=0, to=23, textvariable=self.hour_var, width=3, validate="key")
        self.hour_spinbox['validatecommand'] = (self.frame.register(self.validate_hour), '%P')
        self.hour_spinbox.grid(row=1, column=3)

        tk.Label(self.frame, text="분:").grid(row=1, column=4)
        self.minute_spinbox = tk.Spinbox(self.frame, from_=0, to=59, textvariable=self.minute_var, width=3, validate="key")
        self.minute_spinbox['validatecommand'] = (self.frame.register(self.validate_minute), '%P')
        self.minute_spinbox.grid(row=1, column=5)

        tk.Label(self.frame, text="채널:").grid(row=1, column=6)
        tk.OptionMenu(self.frame, self.channel_var, ChannelName.Tip.value, ChannelName.Shield.value, ChannelName.Bypass.value).grid(row=1, column=7)

        tk.Label(self.frame, text="동작:").grid(row=1, column=8)
        action_menu = tk.OptionMenu(self.frame, self.action_var, Action.On.value, Action.Off.value, Action.Setpoint.value, command=self.update_number_entry)
        action_menu.grid(row=1, column=9)

        tk.Label(self.frame, text="숫자:").grid(row=1, column=10)
        self.number_spinbox = tk.Spinbox(self.frame, from_=0, to=99, textvariable=self.number_var, width=3, validate="key")
        self.number_spinbox['validatecommand'] = (self.frame.register(self.validate_integer), '%P')
        self.number_spinbox.grid(row=1, column=11)
        self.update_number_entry()

        tk.Button(self.frame, text="위로", command=self.move_up).grid(row=1, column=12)
        tk.Button(self.frame, text="아래로", command=self.move_down).grid(row=1, column=13)
        tk.Button(self.frame, text="삭제", command=self.delete_schedule).grid(row=1, column=14)  # 삭제 버튼 추가

        self.frame.pack(fill=tk.X)

    def validate_hour(self, value_if_allowed):
        value_if_allowed = str(value_if_allowed)
        if value_if_allowed.isdigit() and 0 <= int(value_if_allowed) <= 23:
            return True
        return False

    def validate_minute(self, value_if_allowed):
        value_if_allowed = str(value_if_allowed)
        if value_if_allowed.isdigit() and 0 <= int(value_if_allowed) <= 59:
            return True
        return False

    def validate_integer(self, value_if_allowed):
        value_if_allowed = str(value_if_allowed)
        if value_if_allowed.isdigit() and 0 <= int(value_if_allowed) <= 99:
            return True
        return False

    def update_number_entry(self, *args):
        if self.action_var.get() in ["On", "Off"]:
            self.number_spinbox.config(state='disabled')  # 비활성화
            self.number_var.set("")  # 비활성화 시 값 초기화
        else:
            self.number_spinbox.config(state='normal')  # 활성화

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

        # 버튼 프레임 생성
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X, pady=10)

        # 버튼들을 가로로 배열
        self.add_schedule_button = tk.Button(button_frame, text="스케줄 추가", command=self.add_schedule)
        self.add_schedule_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(button_frame, text="스케줄 저장", command=self.save_schedules)
        self.save_button.pack(side=tk.LEFT, padx=5)

        self.load_button = tk.Button(button_frame, text="스케줄 불러오기", command=self.load_schedules)
        self.load_button.pack(side=tk.LEFT, padx=5)

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

    def save_schedules(self):
        schedules_data = []
        for widget in self.schedule_widgets:
            schedule_data = {
                "day": widget.day.value,
                "hour": widget.hour,
                "minute": widget.minute,
                "channel": widget.channelname.value,
                "action": widget.action.value,
                "number": widget.number_var.get()
            }
            schedules_data.append(schedule_data)
        
        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")])
        if not file_path:  # 사용자가 취소를 누른 경우
            return

        with open(file_path, "w") as f:
            json.dump(schedules_data, f)
        
        messagebox.showinfo("저장 완료", f"스케줄이 성공적으로 저장되었습니다.\n파일: {file_path}")

    def load_schedules(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not file_path:  # 사용자가 취소를 누른 경우
            return
        
        try:
            with open(file_path, "r") as f:
                schedules_data = json.load(f)
            
            # 임시 리스트에 새 위젯 저장
            temp_widgets = []
            temp_count = 0

            # 불러온 데이터로 새 스케줄 위젯 생성
            for data in schedules_data:
                widget = ScheduleWidget(self, temp_count)
                widget.day_var.set(data["day"])
                widget.hour_var.set(data["hour"])
                widget.minute_var.set(data["minute"])
                widget.channel_var.set(data["channel"])
                widget.action_var.set(data["action"])
                widget.number_var.set(data["number"])
                widget.update_number_entry()
                
                temp_widgets.append(widget)
                temp_count += 1

            # 모든 위젯이 성공적으로 생성되면 기존 위젯 제거 및 새 위젯으로 교체
            for widget in self.schedule_widgets:
                widget.frame.destroy()
            self.schedule_widgets = temp_widgets
            self.schedule_count = temp_count

            self.update_schedule_display()
            messagebox.showinfo("불러오기 완료", f"스케줄이 성공적으로 불러와졌습니다.\n파일: {file_path}")
        
        except json.JSONDecodeError:
            messagebox.showerror("오류", "잘못된 JSON 파일 형식입니다. 파일을 확인해주세요.")
        except KeyError as e:
            messagebox.showerror("오류", f"필수 키가 누락되었습니다: {str(e)}")
        except Exception as e:
            messagebox.showerror("오류", f"파일을 불러오는 중 오류가 발생했습니다: {str(e)}")

    def on_close(self):
        for widget in self.schedule_widgets:
            try:
                if not widget.validate_hour(widget.hour_var.get()):
                    messagebox.showerror("오류", "시간 입력이 잘못되었습니다.")
                    return
            except Exception as e:
                messagebox.showerror("오류", f"시간 입력이 잘못되었습니다: {str(e)}")
                print(f"Exception during hour validation: {str(e)}")
                return
            try:
                if not widget.validate_minute(widget.minute_var.get()):
                    messagebox.showerror("오류", "분 입력이 잘못되었습니다.")
                    return
            except Exception as e:
                messagebox.showerror("오류", f"분 입력이 잘못되었습니다: {str(e)}")
                print(f"Exception during minute validation: {str(e)}")
                return
            if widget.action == Action.Setpoint:
                try:
                    if not widget.validate_integer(widget.number_var.get()):
                        messagebox.showerror("오류", "숫자 입력이 잘못되었습니다.")
                        return
                except Exception as e:
                    messagebox.showerror("오류", f"숫자 입력이 잘못되었습니다: {str(e)}")
                    print(f"Exception during number validation: {str(e)}")
                    return
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
