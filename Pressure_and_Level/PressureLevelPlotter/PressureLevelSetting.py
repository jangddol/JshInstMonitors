import tkinter as tk

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
        self.geometry("200x160")  # Width x Height
        
        self.label_name_unit_pairs = self.mother.label_name_unit_pairs
        
        self.pairs = []
        self.up_buttons = []
        self.down_buttons = []
        
        for i, (label, unit) in enumerate(self.label_name_unit_pairs):
            frame = tk.Frame(self)
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)
            
            lbl = tk.Label(frame, text=label)
            lbl.pack(side=tk.LEFT)
            
            up_button = tk.Button(self, text="↑", command=lambda i=i: self.move_up(i))
            up_button.grid(row=i, column=1)
            self.up_buttons.append(up_button)
            
            down_button = tk.Button(self, text="↓", command=lambda i=i: self.move_down(i))
            down_button.grid(row=i, column=2)
            self.down_buttons.append(down_button)
            
            self.pairs.append((i, label, frame))
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def move_up(self, index):
        if index > 0:
            self.pairs[index], self.pairs[index - 1] = self.pairs[index - 1], self.pairs[index]
            self.update_widgets()
    
    def move_down(self, index):
        if index < len(self.pairs) - 1:
            self.pairs[index], self.pairs[index + 1] = self.pairs[index + 1], self.pairs[index]
            self.update_widgets()
    
    def update_widgets(self):
        for i, (initial_index, label, frame) in enumerate(self.pairs):
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)
            self.up_buttons[i].grid(row=i, column=1)
            self.down_buttons[i].grid(row=i, column=2)
    
    def on_closing(self):
        positions = [initial_index for initial_index, label, frame in self.pairs]
        self.mother.update_positions(positions)
        self.destroy()
