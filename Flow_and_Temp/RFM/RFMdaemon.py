"""RFMdaemon — Tk GUI shell for MFC control. Business logic lives in rfm_controller."""

import json
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

import numpy as np

_COMMON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "common"))
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from channel import ChannelName
from FuncLogger import FuncLogger
from paths import bundle_path, writable_path
from rfm_controller import COLUMNNUM, RFMController, ToggleState
from rfm_errors import RFMError, RFMSerialTimeout
from schedularwindow import SchedularWindow

flog = FuncLogger("flowtemp", "RFMdaemon")

# Default when config omits serial_on. Prefer rfm_config.json "serial_on".
DEFAULT_SERIAL_ON = True

# graphic constants
COLUMNWIDTH = 235
HEIGHT = 385
STATUS_DEFAULT_HEIGHT = 120
STATUS_MIN_HEIGHT = 60
STATUS_MAX_LINES = 200
FONT_SIZE = 15
SWITCH_XOFFSET = 10
SWITCH_YOFFSET = 240
SWITCH_WIDTH = 100
SWITCH_HEIGHT = 30
RESET_XOFFSET = 120
RESET_YOFFSET = 5
RESET_WIDTH = 50
RESET_HEIGHT = 15
SCHEDULAR_XOFFSET = RESET_XOFFSET
SCHEDULAR_YOFFSET = 30
SCHEDULAR_WIDTH = RESET_WIDTH
SCHEDULAR_HEIGHT = RESET_HEIGHT
MINITOGGLE_XOFFSET = RESET_XOFFSET + 60
MINITOGGLE_YOFFSET = SCHEDULAR_YOFFSET
MINITOGGLE_WIDTH = RESET_WIDTH
MINITOGGLE_HEIGHT = RESET_HEIGHT
MINIHEIGHT = 130

COLOR_WHITE = "white"
COLOR_BLACK = "black"
COLOR_HIGHLIGHTED = "gray"

ENTRY_HIGHLIGHTED_NONE = 0
ENTRY_HIGHLIGHTED_FLOWSET_TIP = 1
ENTRY_HIGHLIGHTED_FLOWSET_SHIELD = 2
ENTRY_HIGHLIGHTED_FLOWSET_BYPASS = 3
ENTRY_HIGHLIGHTED_FLOWSET_PUMPING = 4
ENTRY_HIGHLIGHTED_CH_TIP = 5
ENTRY_HIGHLIGHTED_CH_SHIELD = 6
ENTRY_HIGHLIGHTED_CH_BYPASS = 7
ENTRY_HIGHLIGHTED_CH_PUMPING = 8

UPDATE_INTERVAL_MS = 100


class RFMApp:
    """Tk view + input handlers. All MFC/serial/schedule logic is in self.ctrl."""

    def __init__(self, master, port, pc_input_max, arduino_read_max, serial_on=DEFAULT_SERIAL_ON):
        flog.info("RFMApp.__init__: start")
        self.master = master
        self.ctrl = RFMController(serial_on, port, pc_input_max, arduino_read_max, flog)

        self.highlighted_entry = ENTRY_HIGHLIGHTED_NONE
        self.mn = False
        self.lastwidth = 0
        self.lastheight = 0
        self.width = COLUMNNUM * COLUMNWIDTH
        self.height = HEIGHT
        self.flowSetPointBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.channelBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.schedular_window = None
        # Dedupe identical consecutive status lines (serial timeout spam).
        self._last_status_key = None
        self._status_line_count = 0

        flog.info("RFMApp.__init__: setup_ui")
        self.setup_ui()
        # Surface any controller startup serial errors before the first tick.
        for level, message in self.ctrl.drain_ui_events():
            self.append_status(level, message, to_flog=False)
        self.ctrl.start_reader()
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        # Defer first tick so Tk can paint the window before drawing.
        flog.info("RFMApp.__init__: schedule first main_loop via after(0)")
        self.master.after(0, self.main_loop)
        flog.info("RFMApp.__init__: done (mainloop next)")

    def on_close(self) -> None:
        flog.info("RFMApp.on_close: stopping serial reader")
        try:
            self.ctrl.stop_reader()
        except Exception as e:
            flog.caution(f"on_close stop_reader: {e}")
        self.master.destroy()

    def append_status(self, level: str, message: str, *, to_flog: bool = True) -> None:
        """Append a critical event to the bottom status pane (scrollable, non-modal)."""
        key = f"{level}:{message}"
        if key == self._last_status_key:
            return
        self._last_status_key = key
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {message}\n"
        level_u = level.upper()
        if to_flog:
            if level_u == "CRITICAL":
                flog.critical(message)
            elif level_u == "ERROR":
                flog.error(message)
            elif level_u == "CAUTION":
                flog.caution(message)
            else:
                flog.info(message)

        self.status_text.configure(state=tk.NORMAL)
        tag = level_u if level_u in ("INFO", "CAUTION", "ERROR", "CRITICAL") else "INFO"
        self.status_text.insert(tk.END, line, tag)
        self._status_line_count += 1
        while self._status_line_count > STATUS_MAX_LINES:
            self.status_text.delete("1.0", "2.0")
            self._status_line_count -= 1
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED)

    def clear_status_dedupe(self) -> None:
        """Allow the next identical status line after a successful recovery."""
        self._last_status_key = None

    def show_status_error(self, err: BaseException, *, title: str = "RFM Error") -> None:
        """Non-modal replacement for messagebox errors (user actions / unexpected)."""
        level = "CAUTION" if isinstance(err, RFMSerialTimeout) else "ERROR"
        self.append_status(level, f"{title}: {err}")

    # --- HTTP-facing properties (keep old attribute names for RFMHandler) ---
    @property
    def last_flow_values(self):
        return self.ctrl.get_last_flow_values()

    @property
    def last_read_time(self):
        return self.ctrl.get_last_read_time()

    def setup_ui(self):
        total_h = HEIGHT + STATUS_DEFAULT_HEIGHT
        self.master.geometry(f"{self.width}x{total_h}")
        self.master.resizable(True, True)
        self.master.title("MFC Readout Reader")
        self.master.minsize(COLUMNNUM * COLUMNWIDTH // 2, MINIHEIGHT + STATUS_MIN_HEIGHT)

        self.paned = tk.PanedWindow(
            self.master,
            orient=tk.VERTICAL,
            sashrelief=tk.RAISED,
            sashwidth=6,
            bg="#444444",
            opaqueresize=True,
        )
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.control_frame = tk.Frame(self.paned, bg=COLOR_BLACK)
        self.status_frame = tk.Frame(self.paned, bg="#1a1a1a")
        self.paned.add(self.control_frame, minsize=MINIHEIGHT, stretch="always")
        self.paned.add(self.status_frame, minsize=STATUS_MIN_HEIGHT, stretch="never")

        self.canvas = tk.Canvas(
            self.control_frame,
            width=self.width,
            height=HEIGHT,
            bg=COLOR_BLACK,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        status_bar = tk.Frame(self.status_frame, bg="#1a1a1a")
        status_bar.pack(fill=tk.BOTH, expand=True)
        self.status_scroll = tk.Scrollbar(status_bar, orient=tk.VERTICAL)
        self.status_text = tk.Text(
            status_bar,
            height=6,
            wrap=tk.WORD,
            bg="#111111",
            fg="#dddddd",
            insertbackground="#dddddd",
            font=("Consolas", 9),
            yscrollcommand=self.status_scroll.set,
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=0,
            padx=6,
            pady=4,
        )
        self.status_scroll.config(command=self.status_text.yview)
        self.status_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_text.tag_configure("INFO", foreground="#7dcea0")
        self.status_text.tag_configure("CAUTION", foreground="#f5b041")
        self.status_text.tag_configure("ERROR", foreground="#ec7063")
        self.status_text.tag_configure("CRITICAL", foreground="#ff3355")

        self.setup_buttons()
        self.setup_bindings()
        self.master.update_idletasks()
        try:
            self.paned.sash_place(0, 0, HEIGHT)
        except tk.TclError:
            pass
        flog.info("setup_ui: paned control + status log ready")

    def setup_buttons(self):
        parent = self.control_frame
        self.switchs_toggle = [
            tk.Button(parent, text="OFF", command=lambda i=i: self.on_switch_toggle(i))
            for i in range(COLUMNNUM)
        ]
        self.reset_button = tk.Button(parent, text="RESET", command=self.on_reset_click)
        self.schedular_button = tk.Button(parent, text="Schedular", command=self.on_schedular_click)
        self.mini_toggle = tk.Button(parent, text="Mini", command=self.on_mini_toggle)
        self.place_buttons()

    def place_buttons(self):
        if not self.mn:
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            for i in range(COLUMNNUM):
                self.switchs_toggle[i].place(
                    x=(SWITCH_XOFFSET + i * COLUMNWIDTH) * resize_ratio_x,
                    y=SWITCH_YOFFSET * resize_ratio_y,
                    width=SWITCH_WIDTH * resize_ratio_x,
                    height=SWITCH_HEIGHT * resize_ratio_y,
                )
            self.reset_button.place(
                x=RESET_XOFFSET * resize_ratio_x,
                y=RESET_YOFFSET * resize_ratio_y,
                width=RESET_WIDTH * resize_ratio_x,
                height=RESET_HEIGHT * resize_ratio_y,
            )
            self.schedular_button.place(
                x=SCHEDULAR_XOFFSET * resize_ratio_x,
                y=SCHEDULAR_YOFFSET * resize_ratio_y,
                width=SCHEDULAR_WIDTH * resize_ratio_x,
                height=SCHEDULAR_HEIGHT * resize_ratio_y,
            )
            self.mini_toggle.place(
                x=MINITOGGLE_XOFFSET * resize_ratio_x,
                y=MINITOGGLE_YOFFSET * resize_ratio_y,
                width=MINITOGGLE_WIDTH * resize_ratio_x,
                height=MINITOGGLE_HEIGHT * resize_ratio_y,
            )
        else:
            self.reset_button.place(x=RESET_XOFFSET, y=RESET_YOFFSET, width=RESET_WIDTH, height=RESET_HEIGHT)
            self.schedular_button.place(
                x=SCHEDULAR_XOFFSET, y=SCHEDULAR_YOFFSET, width=SCHEDULAR_WIDTH, height=SCHEDULAR_HEIGHT
            )
            self.mini_toggle.place(
                x=MINITOGGLE_XOFFSET, y=MINITOGGLE_YOFFSET, width=MINITOGGLE_WIDTH, height=MINITOGGLE_HEIGHT
            )
            for btn in self.switchs_toggle:
                btn.place_forget()

    def setup_bindings(self):
        self.master.bind("<Key>", self.key_pressed)
        self.canvas.bind("<Button-1>", self.mouse_pressed)
        self.control_frame.bind("<Configure>", self.on_control_resize)

    def main_loop(self):
        # Serial reads run on a background thread — this tick only paints + drains status.
        try:
            self.update()
        except Exception as e:
            flog.critical(f"main_loop update failed: {e}")
            self.append_status("CRITICAL", f"Unexpected error: {e}")
        for level, message in self.ctrl.drain_ui_events():
            # Controller already wrote flog; UI pane only.
            self.append_status(level, message, to_flog=False)
        self.master.after(UPDATE_INTERVAL_MS, self.main_loop)

    def update(self):
        self.draw()
        if self.ctrl.consume_clear_status_dedupe():
            self.clear_status_dedupe()
        flow_values = self.ctrl.get_last_flow_values()
        self.displayFlowValues([f"{x:.2f}" for x in flow_values])
        if self.schedular_window is not None:
            try:
                self.ctrl.handle_schedular(
                    self.schedular_window.schedule_widgets,
                    on_ui_toggle=self.on_switch_toggle,
                )
            except RFMError as e:
                self.show_status_error(e, title="Schedular Error")

    def draw(self):
        self.master.configure(bg=COLOR_BLACK)
        self.control_frame.configure(bg=COLOR_BLACK)
        self.width = max(self.control_frame.winfo_width(), 1)
        self.height = max(self.control_frame.winfo_height(), 1)
        self.fillEntryBkgColor()
        self.displayTexts()
        self.place_buttons()

    def on_control_resize(self, event):
        if event.widget is not self.control_frame:
            return
        self.width = max(event.width, 1)
        self.height = max(event.height, 1)
        if self.width != self.lastwidth or self.height != self.lastheight:
            self.draw()
            self.lastwidth = self.width
            self.lastheight = self.height
        self.canvas.config(width=self.width, height=self.height)

    def on_switch_toggle(self, index):
        state = self.switchs_toggle[index].config("relief")[-1] == "sunken"
        flog.info(f"UI toggle col{index} (was_on={state})")
        try:
            self.ctrl.toggle_switch(index, state)
        except RFMError as e:
            self.show_status_error(e, title="Channel Toggle Error")
            return
        if state:
            self.switchs_toggle[index].config(relief="raised", text="OFF")
        else:
            if self.ctrl.toggleStates[index] == ToggleState.On:
                self.switchs_toggle[index].config(relief="sunken", text="ON")
            else:
                self.switchs_toggle[index].config(relief="raised", text="OFF")
                # Need channel first: focus that column's channel entry for typing.
                if self.ctrl.toggleStates[index] == ToggleState.SelectChannel:
                    self.change_highlight_entry_to(ENTRY_HIGHLIGHTED_CH_TIP + index)

    def on_mini_toggle(self):
        status_h = STATUS_DEFAULT_HEIGHT
        try:
            sash_y = self.paned.sash_coord(0)[1]
            total = max(self.master.winfo_height(), 1)
            status_h = max(STATUS_MIN_HEIGHT, total - sash_y)
        except tk.TclError:
            pass
        if self.mini_toggle.config("relief")[-1] == "sunken":
            self.mini_toggle.config(relief="raised")
            self.mn = False
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{HEIGHT + status_h}")
            self.master.update_idletasks()
            try:
                self.paned.sash_place(0, 0, HEIGHT)
            except tk.TclError:
                pass
            flog.info("UI mini mode off")
        else:
            self.mini_toggle.config(relief="sunken")
            self.mn = True
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{MINIHEIGHT + status_h}")
            self.master.update_idletasks()
            try:
                self.paned.sash_place(0, 0, MINIHEIGHT)
            except tk.TclError:
                pass
            flog.info("UI mini mode on")

    def on_reset_click(self):
        flog.info("UI RESET clicked")
        try:
            self.ctrl.reset_hardware()
        except RFMError as e:
            self.show_status_error(e, title="Reset Error")
            return
        self.highlighted_entry = ENTRY_HIGHLIGHTED_NONE
        self.flowSetPointBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.channelBkgColors = [COLOR_BLACK] * COLUMNNUM
        for btn in self.switchs_toggle:
            btn.config(relief="raised", text="OFF")

    def on_schedular_click(self):
        flog.info("UI Schedular opened")
        if self.schedular_window is None:
            self.schedular_window = SchedularWindow(self.master)
        self.schedular_window.show()

    def fillEntryBkgColor(self):
        self.canvas.delete("all")
        if not self.mn:
            for i in range(COLUMNNUM):
                x1 = (60 + i * COLUMNWIDTH) * self.width / (COLUMNNUM * COLUMNWIDTH)
                y1 = 167 * self.height / HEIGHT
                x2 = x1 + 160 * self.width / (COLUMNNUM * COLUMNWIDTH)
                y2 = y1 + 18 * self.height / HEIGHT
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.flowSetPointBkgColors[i], outline="")

                y1 = 337 * self.height / HEIGHT
                y2 = y1 + 18 * self.height / HEIGHT
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.channelBkgColors[i], outline="")

    def displayTexts(self):
        COLUMNNAME = [
            ChannelName.Tip.value,
            ChannelName.Shield.value,
            ChannelName.Bypass.value,
            ChannelName.Pumping.value,
        ]
        c = self.ctrl
        if not self.mn:
            line = "." * 300
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            resize_ratio_tot = (self.height + self.width) / (COLUMNNUM * COLUMNWIDTH + HEIGHT)
            font_size = int(FONT_SIZE * resize_ratio_tot)
            font = ("Calibri Light", font_size)

            self.canvas.create_text(0, resize_ratio_y * 125, text=line, fill="white", font=font, anchor="w")
            self.canvas.create_text(0, resize_ratio_y * 210, text=line, fill="white", font=font, anchor="w")
            self.canvas.create_text(0, resize_ratio_y * 305, text=line, fill="white", font=font, anchor="w")

            for i in range(COLUMNNUM):
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 20,
                    text=f"({COLUMNNAME[i]}) Ch  {c.channels[i].value}",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 55,
                    text="Sensing Output",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 150,
                    text="Setting Input",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 175,
                    text=f"Input: {c.flowSetPoint_Entry[i]}",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * i * COLUMNWIDTH,
                    resize_ratio_y * 200,
                    text=f"  {c.flowSetPoints_Shown[i]}",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 325,
                    text=f"Setting {COLUMNNAME[i]} Ch.",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 345,
                    text=f"Input: {c.channelsEntry[i]}",
                    fill="white",
                    font=font,
                    anchor="w",
                )
        else:
            font = ("Calibri Light", FONT_SIZE)
            for i in range(COLUMNNUM):
                self.canvas.create_text(
                    10 + i * COLUMNWIDTH,
                    20,
                    text=f"({COLUMNNAME[i]}) Ch  {c.channels[i].value}",
                    fill="white",
                    font=font,
                    anchor="w",
                )
                self.canvas.create_text(
                    10 + i * COLUMNWIDTH,
                    55,
                    text="Sensing Output",
                    fill="white",
                    font=font,
                    anchor="w",
                )

    def displayFlowValues(self, flowValues):
        if not self.mn:
            resize_ratio_x = self.width / (COLUMNNUM * COLUMNWIDTH)
            resize_ratio_y = self.height / HEIGHT
            resize_ratio_tot = (self.height + self.width) / (COLUMNNUM * COLUMNWIDTH + HEIGHT)
            font_size = int(FONT_SIZE * resize_ratio_tot)
            font = ("Calibri Light", font_size)
            for i in range(COLUMNNUM):
                self.canvas.create_text(
                    resize_ratio_x * (10 + i * COLUMNWIDTH),
                    resize_ratio_y * 80,
                    text=flowValues[i],
                    fill="white",
                    font=font,
                    anchor="w",
                )
        else:
            font = ("Calibri Light", FONT_SIZE)
            for i in range(COLUMNNUM):
                self.canvas.create_text(
                    10 + i * COLUMNWIDTH,
                    80,
                    text=flowValues[i],
                    fill="white",
                    font=font,
                    anchor="w",
                )

    def is_key_code_change_highlight_entry(self, key_code):
        return key_code in ("Tab", "Left", "Right", "Up", "Down")

    def get_highlight_entry_using_keycode(self, key_code, highlighted_entry):
        """Navigate the 8 editable fields: setpoint row 1-4, channel row 5-8."""
        n = COLUMNNUM * 2
        if highlighted_entry < 1 or highlighted_entry > n:
            return 1

        if key_code in ("Tab", "Right"):
            return 1 if highlighted_entry >= n else highlighted_entry + 1
        if key_code == "Left":
            return n if highlighted_entry <= 1 else highlighted_entry - 1
        if key_code == "Down":
            if highlighted_entry <= COLUMNNUM:
                return highlighted_entry + COLUMNNUM
            return highlighted_entry
        if key_code == "Up":
            if highlighted_entry > COLUMNNUM:
                return highlighted_entry - COLUMNNUM
            return highlighted_entry
        return highlighted_entry

    def _can_edit_setpoint(self, index: int) -> bool:
        return self.ctrl.toggleStates[index] == ToggleState.On

    def _can_edit_channel(self, index: int) -> bool:
        # Off: normal channel assign. SelectChannel: recover from need-channel-first.
        return self.ctrl.toggleStates[index] in (ToggleState.Off, ToggleState.SelectChannel)

    def _setpoint_max_len(self) -> int:
        return max(1, len(str(self.ctrl.pc_input_max)))

    def key_pressed(self, event):
        entry_flowset_list = [
            ENTRY_HIGHLIGHTED_FLOWSET_TIP,
            ENTRY_HIGHLIGHTED_FLOWSET_SHIELD,
            ENTRY_HIGHLIGHTED_FLOWSET_BYPASS,
            ENTRY_HIGHLIGHTED_FLOWSET_PUMPING,
        ]
        entry_channel_list = [
            ENTRY_HIGHLIGHTED_CH_TIP,
            ENTRY_HIGHLIGHTED_CH_SHIELD,
            ENTRY_HIGHLIGHTED_CH_BYPASS,
            ENTRY_HIGHLIGHTED_CH_PUMPING,
        ]
        c = self.ctrl
        if self.is_key_code_change_highlight_entry(event.keysym):
            highlight_entry = self.get_highlight_entry_using_keycode(event.keysym, self.highlighted_entry)
            self.change_highlight_entry_to(highlight_entry)
        elif event.keysym in ("Return", "Enter"):
            try:
                for i, entry_flowset in enumerate(entry_flowset_list):
                    if self.highlighted_entry == entry_flowset and self._can_edit_setpoint(i):
                        c.update_flow_setpoint(i)
                for i, entry_channel in enumerate(entry_channel_list):
                    if self.highlighted_entry == entry_channel and self._can_edit_channel(i):
                        ok = c.apply_changed_channel(i)
                        if not ok:
                            self.show_status_error(
                                ValueError("Channel must be an integer 1-4"),
                                title="Channel Input Error",
                            )
            except RFMError as e:
                self.show_status_error(e, title="Input Apply Error")
        else:
            for i, entry_flowset in enumerate(entry_flowset_list):
                if self.highlighted_entry == entry_flowset and self._can_edit_setpoint(i):
                    c.flowSetPoint_Entry[i] = self.modify_number_string_by_key(
                        c.flowSetPoint_Entry[i],
                        event.keysym,
                        event.char,
                        max_len=self._setpoint_max_len(),
                    )
            for i, entry_channel in enumerate(entry_channel_list):
                if self.highlighted_entry == entry_channel and self._can_edit_channel(i):
                    c.channelsEntry[i] = self.modify_number_string_by_key(
                        c.channelsEntry[i],
                        event.keysym,
                        event.char,
                        max_len=1,
                    )

    def modify_number_string_by_key(self, number_string, key_code, key, max_len=None):
        if key_code == "BackSpace" and len(number_string) > 0:
            return number_string[:-1]
        if key.isdigit():
            if max_len is not None and len(number_string) >= max_len:
                return number_string
            return number_string + key
        return number_string

    def get_column_index_from_mouse(self, mouseX):
        columnwidth = COLUMNWIDTH
        if not self.mn:
            columnwidth = COLUMNWIDTH * self.width / (COLUMNNUM * COLUMNWIDTH)
        return np.floor(mouseX / columnwidth)

    def get_row_index_from_mouse(self, mouseY):
        # Mini mode only shows sensing readout — no setpoint/channel hit targets.
        if self.mn:
            return -1
        SENTINAL_VALUE = -1
        if (mouseY < self.height * 266 / HEIGHT) and (mouseY > 139 * self.height / HEIGHT):
            return 0
        elif mouseY > self.height * 320 / HEIGHT:
            return 1
        else:
            return SENTINAL_VALUE

    def get_highlited_entry_from_mouse(self, mouseX, mouseY):
        if self.get_row_index_from_mouse(mouseY) == -1:
            return ENTRY_HIGHLIGHTED_NONE
        return 1 + self.get_column_index_from_mouse(mouseX) + COLUMNNUM * self.get_row_index_from_mouse(mouseY)

    def mouse_pressed(self, event):
        highlighted_entry = self.get_highlited_entry_from_mouse(event.x, event.y)
        self.change_highlight_entry_to(highlighted_entry)

    def change_highlight_entry_to(self, entry):
        """Move focus highlight. Draft digit buffers are kept (not cleared on blur)."""
        self.highlighted_entry = entry
        entry_flowset_list = [
            ENTRY_HIGHLIGHTED_FLOWSET_TIP,
            ENTRY_HIGHLIGHTED_FLOWSET_SHIELD,
            ENTRY_HIGHLIGHTED_FLOWSET_BYPASS,
            ENTRY_HIGHLIGHTED_FLOWSET_PUMPING,
        ]
        entry_channel_list = [
            ENTRY_HIGHLIGHTED_CH_TIP,
            ENTRY_HIGHLIGHTED_CH_SHIELD,
            ENTRY_HIGHLIGHTED_CH_BYPASS,
            ENTRY_HIGHLIGHTED_CH_PUMPING,
        ]

        for i, entry_flowset in enumerate(entry_flowset_list):
            if entry == entry_flowset:
                self.flowSetPointBkgColors[i] = COLOR_HIGHLIGHTED
            else:
                self.flowSetPointBkgColors[i] = COLOR_BLACK

        for i, entry_channel in enumerate(entry_channel_list):
            if entry == entry_channel:
                self.channelBkgColors[i] = COLOR_HIGHLIGHTED
            else:
                self.channelBkgColors[i] = COLOR_BLACK


def open_config_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as file:
        config_data = json.load(file)
        arduino_port = config_data.get("arduino_port")
        localserver_port = config_data.get("localserver_port")
        pc_input_max = config_data.get("pc_input_max")
        arduino_read_max = config_data.get("arduino_read_max")
        serial_on = config_data.get("serial_on", DEFAULT_SERIAL_ON)

        if (
            not isinstance(arduino_port, str)
            or not isinstance(localserver_port, int)
            or not isinstance(pc_input_max, int)
            or not isinstance(arduino_read_max, int)
            or not isinstance(serial_on, bool)
        ):
            raise ValueError("Invalid configuration data")

        return arduino_port, localserver_port, pc_input_max, arduino_read_max, serial_on


def resource_path(relative_path):
    return bundle_path(relative_path)


if __name__ == "__main__":
    rfmapp = None

    flog.info("=== RFMdaemon process start ===")
    config_file_path = writable_path("rfm_config.json")
    try:
        flog.info(f"Loading config: {config_file_path}")
        arduino_port, localserver_port, pc_input_max, arduino_read_max, serial_on = open_config_file(
            config_file_path
        )
        flog.info(
            f"Config ok: port={arduino_port} http={localserver_port} "
            f"pc_max={pc_input_max} adc_max={arduino_read_max} serial_on={serial_on}"
        )
    except Exception as e:
        flog.caution(f"Config load failed ({e}); writing default config")
        with open(config_file_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "arduino_port": "COM3",
                    "localserver_port": 5000,
                    "pc_input_max": 99,
                    "arduino_read_max": 4095,
                    "serial_on": True,
                },
                file,
            )
        arduino_port, localserver_port, pc_input_max, arduino_read_max, serial_on = open_config_file(
            config_file_path
        )

    class RFMHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/get_value":
                if "rfmapp" not in globals() or rfmapp is None:
                    self.send_error(404, "Application not ready")
                    return

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()

                response = {
                    "Tip": rfmapp.last_flow_values[0],
                    "Shield": rfmapp.last_flow_values[1],
                    "Bypass": rfmapp.last_flow_values[2],
                    "Pumping": rfmapp.last_flow_values[3],
                    "timestamp": rfmapp.last_read_time,
                }
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            # Quiet default HTTP access spam; functional log covers server lifecycle.
            return

    def run_app(port, pc_input_max, arduino_read_max, serial_on):
        flog.info("run_app: creating Tk root")
        master = tk.Tk()
        try:
            master.iconbitmap(resource_path("MFC.ico"))
            flog.info("run_app: icon set")
        except Exception as e:
            flog.caution(f"run_app: icon failed: {e}")

        global rfmapp
        try:
            flog.info("run_app: constructing RFMApp")
            rfmapp = RFMApp(master, port, pc_input_max, arduino_read_max, serial_on=serial_on)
            flog.info("RFMdaemon GUI started (entering mainloop)")
            rfmapp.master.mainloop()
            flog.info("RFMdaemon mainloop exited")
            try:
                rfmapp.ctrl.stop_reader()
            except Exception as e:
                flog.caution(f"post-mainloop stop_reader: {e}")
        except RFMError as e:
            flog.critical(f"Application RFM error: {e}")
            # Startup failed before / without a usable status pane.
            rfmapp = None
            try:
                master.destroy()
            except Exception:
                pass
        except Exception as e:
            flog.critical(f"Application error: {e}")
            rfmapp = None
            try:
                master.destroy()
            except Exception:
                pass

    def run_server():
        try:
            server = HTTPServer(("localhost", localserver_port), RFMHandler)
            flog.info(f"HTTP server started on localhost:{localserver_port}")
            server.serve_forever()
        except Exception as e:
            flog.error(f"Server error: {e}")

    flog.info("Starting HTTP server thread")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)
    flog.info("HTTP wait done; launching GUI")
    run_app(arduino_port, pc_input_max, arduino_read_max, serial_on)
