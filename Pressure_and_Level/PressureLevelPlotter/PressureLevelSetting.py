import tkinter as tk

from CalibrationWindow import CalibrationWindow

# Maps label_name_unit_pairs index → arduino_deque channel index
# label 0: V_plant → deque[2], label 1: P_plant → deque[1],
# label 2: P_storage → deque[0], label 3: P_purifier → deque[3]
_LABEL_TO_DEQUE = [2, 1, 0, 3]


class PressureLevelSetting(tk.Toplevel):
    """
    PressureLevelSetting 클래스에 있는 메인 윈도우의 label 위젯의 위치를 조정하는 클래스입니다.
    이 PressureLevelSetting 창을 닫을 때, PressureLevelSetting 클래스는
        이 클래스로부터 반환받습니다.
    
    이 클래스는 4개의 위젯 세트로 이루어져 있습니다.
    각 위젯 세트는 항목 이름, 위 화살표 버튼, 아래 화살표 버튼으로 구성됩니다.
    위 화살표와 아래 화살표를 통해 항목의 위치를 조정할 수 있습니다.
    이를 통해 4개의 항목의 위치를 조절하고, 조절된 정보를 PressureLevelSetting 클래스로 반환합니다.
    """
    def __init__(self, mother):
        super().__init__(mother.master)
        self.mother = mother
        self.title("Pressure Level Setting")
        
        # Set the size of the window
        self.geometry("360x200")  # Width x Height
        
        self.label_name_unit_pairs = self.mother.label_name_unit_pairs
        self.is_plot = self.mother.is_plot  # is_plot 리스트를 가져옴
        
        self.pairs = []
        self.frames = []  # 데이터 프레임들
        self.checkboxes = []  # 체크박스 리스트 추가

        # 고정된 위치에 화살표 버튼들 생성
        self.up_buttons = []
        self.down_buttons = []

        # Tracks open CalibrationWindow instances keyed by arduino_deque channel index
        self._cal_windows: dict[int, CalibrationWindow] = {}

        # 데이터 프레임들과 체크박스 생성
        for i, (label, unit) in enumerate(self.label_name_unit_pairs):
            frame = tk.Frame(self)
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)

            lbl = tk.Label(frame, text=label)
            lbl.pack(side=tk.LEFT)

            # 체크박스 추가
            var = tk.BooleanVar(value=self.is_plot[i])
            checkbox = tk.Checkbutton(frame, variable=var, command=lambda i=i, var=var: self.update_is_plot(i, var))
            checkbox.pack(side=tk.LEFT)
            self.checkboxes.append(var)

            # Cal 버튼 — 해당 채널의 캘리브레이션 창 열기
            deque_ch = _LABEL_TO_DEQUE[i]
            cal_btn = tk.Button(
                frame, text="Cal",
                command=lambda ch=deque_ch: self._open_calibration(ch),
            )
            cal_btn.pack(side=tk.LEFT, padx=(4, 0))

            self.frames.append(frame)
            self.pairs.append((i, label, frame))
        
        # 고정된 위치에 화살표 버튼들 생성
        for i in range(len(self.label_name_unit_pairs)):
            up_button = tk.Button(self, text="↑", command=lambda row=i: self.move_up(row))
            up_button.grid(row=i, column=1, padx=2)
            self.up_buttons.append(up_button)
            
            down_button = tk.Button(self, text="↓", command=lambda row=i: self.move_down(row))
            down_button.grid(row=i, column=2, padx=2)
            self.down_buttons.append(down_button)
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def update_is_plot(self, index, var):
        """체크박스 상태를 업데이트하여 is_plot 리스트에 반영"""
        initial_index = self.pairs[index][0]
        self.is_plot[initial_index] = var.get()
    
    def move_up(self, row):
        """고정된 행의 데이터를 위로 이동"""
        if row > 0:
            # pairs 리스트의 순서만 변경 (is_plot은 고정)
            self.pairs[row], self.pairs[row - 1] = self.pairs[row - 1], self.pairs[row]
            # checkboxes 리스트도 함께 교환
            self.checkboxes[row], self.checkboxes[row - 1] = self.checkboxes[row - 1], self.checkboxes[row]
            self.update_widgets()
    
    def move_down(self, row):
        """고정된 행의 데이터를 아래로 이동"""
        if row < len(self.pairs) - 1:
            # pairs 리스트의 순서만 변경 (is_plot은 고정)
            self.pairs[row], self.pairs[row + 1] = self.pairs[row + 1], self.pairs[row]
            # checkboxes 리스트도 함께 교환
            self.checkboxes[row], self.checkboxes[row + 1] = self.checkboxes[row + 1], self.checkboxes[row]
            self.update_widgets()
    
    def update_widgets(self):
        """위젯의 위치를 업데이트 - 화살표는 고정, 데이터 프레임만 재배치"""
        for i, (initial_index, label, frame) in enumerate(self.pairs):
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)
            self.checkboxes[i].set(self.is_plot[initial_index])
    
    def _open_calibration(self, channel_index: int) -> None:
        """Open the CalibrationWindow for the given arduino_deque channel.

        If a window for that channel is already open, bring it to front instead
        of creating a duplicate.
        """
        existing = self._cal_windows.get(channel_index)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return
            except tk.TclError:
                pass
        win = CalibrationWindow(self, self.mother, channel_index)
        self._cal_windows[channel_index] = win

    def on_closing(self):
        """창을 닫을 때 현재 상태를 반환"""
        try:
            positions = [initial_index for initial_index, label, frame in self.pairs]
            self.mother.update_positions(positions)
            self.mother.update_is_plot(self.is_plot)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self.destroy()
