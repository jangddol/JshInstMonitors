"""RFMdaemon — Tk GUI shell for MFC control. Business logic lives in rfm_controller."""

import json
import os
import sys
import threading
import time
import tkinter as tk
from http.server import HTTPServer, SimpleHTTPRequestHandler
from tkinter import messagebox

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

SERIAL_ON = True

# graphic constants
COLUMNWIDTH = 235
HEIGHT = 385
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

    def __init__(self, master, port, pc_input_max, arduino_read_max):
        flog.info("RFMApp.__init__: start")
        self.master = master
        self.ctrl = RFMController(SERIAL_ON, port, pc_input_max, arduino_read_max, flog)

        self.highlighted_entry = ENTRY_HIGHLIGHTED_NONE
        self.mn = False
        self.lastwidth = 0
        self.lastheight = 0
        self.width = COLUMNNUM * COLUMNWIDTH
        self.height = HEIGHT
        self.flowSetPointBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.channelBkgColors = [COLOR_BLACK] * COLUMNNUM
        self.schedular_window = None
        # Same recurring error (e.g. serial timeout every tick) → one popup until cleared.
        self._last_popup_key = None

        flog.info("RFMApp.__init__: setup_ui")
        self.setup_ui()
        # Defer first tick so Tk can paint the window before any serial I/O.
        flog.info("RFMApp.__init__: schedule first main_loop via after(0)")
        self.master.after(0, self.main_loop)
        flog.info("RFMApp.__init__: done (mainloop next)")

    def show_error_popup(self, err: BaseException, *, title: str = "RFM Error") -> None:
        """Surface serial/controller errors to the user. Dedupes identical recurring errors."""
        key = f"{type(err).__name__}:{err}"
        if key == self._last_popup_key:
            return
        self._last_popup_key = key
        flog.error(f"GUI popup: {title}: {err}")
        try:
            messagebox.showerror(title, str(err), parent=self.master)
        except Exception as popup_err:
            flog.critical(f"messagebox failed: {popup_err}")

    def clear_error_popup_dedupe(self) -> None:
        self._last_popup_key = None

    # --- HTTP-facing properties (keep old attribute names for RFMHandler) ---
    @property
    def last_flow_values(self):
        return self.ctrl.last_flow_values

    @property
    def last_read_time(self):
        return self.ctrl.last_read_time

    def setup_ui(self):
        self.master.geometry(f"{self.width}x{self.height}")
        self.master.resizable(True, True)
        self.master.title("MFC Readout Reader")

        self.canvas = tk.Canvas(self.master, width=self.width, height=self.height, bg="black")
        self.canvas.pack()

        self.setup_buttons()
        self.setup_bindings()
        flog.info("setup_ui: canvas + buttons ready")

    def setup_buttons(self):
        self.switchs_toggle = [
            tk.Button(self.master, text="OFF", command=lambda i=i: self.on_switch_toggle(i))
            for i in range(COLUMNNUM)
        ]
        self.reset_button = tk.Button(self.master, text="RESET", command=self.on_reset_click)
        self.schedular_button = tk.Button(self.master, text="Schedular", command=self.on_schedular_click)
        self.mini_toggle = tk.Button(self.master, text="Mini", command=self.on_mini_toggle)
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

    def setup_bindings(self):
        self.master.bind("<Key>", self.key_pressed)
        self.master.bind("<Button-1>", self.mouse_pressed)
        self.master.bind("<Configure>", self.on_resize)

    def main_loop(self):
        try:
            self.update()
        except RFMError as e:
            title = "Serial Timeout" if isinstance(e, RFMSerialTimeout) else "RFM Error"
            self.show_error_popup(e, title=title)
        except Exception as e:
            flog.critical(f"main_loop update failed: {e}")
            self.show_error_popup(e, title="Unexpected Error")
        self.master.after(UPDATE_INTERVAL_MS, self.main_loop)

    def update(self):
        self.draw()
        try:
            self.ctrl.last_flow_values = self.ctrl.read_flow_values()
            self.clear_error_popup_dedupe()
        except RFMError:
            # Keep last values on screen; re-raise so main_loop can popup.
            raise
        self.displayFlowValues([f"{x:.2f}" for x in self.ctrl.last_flow_values])
        if self.schedular_window is not None:
            self.ctrl.handle_schedular(
                self.schedular_window.schedule_widgets,
                on_ui_toggle=self.on_switch_toggle,
            )

    def draw(self):
        self.master.configure(bg="black")
        self.width = self.master.winfo_width()
        self.height = self.master.winfo_height()
        self.fillEntryBkgColor()
        self.displayTexts()
        self.place_buttons()

    def on_resize(self, event):
        self.width = event.width
        self.height = event.height
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
            self.show_error_popup(e, title="Channel Toggle Error")
            return
        if state:
            self.switchs_toggle[index].config(relief="raised", text="OFF")
        else:
            # Only show ON if controller actually turned on (channel may be missing)
            if self.ctrl.toggleStates[index] == ToggleState.On:
                self.switchs_toggle[index].config(relief="sunken", text="ON")
            else:
                self.switchs_toggle[index].config(relief="raised", text="OFF")

    def on_mini_toggle(self):
        if self.mini_toggle.config("relief")[-1] == "sunken":
            self.mini_toggle.config(relief="raised")
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{HEIGHT}")
            self.mn = False
            flog.info("UI mini mode off")
        else:
            self.mini_toggle.config(relief="sunken")
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{MINIHEIGHT}")
            self.mn = True
            flog.info("UI mini mode on")

    def on_reset_click(self):
        flog.info("UI RESET clicked")
        try:
            self.ctrl.reset_hardware()
        except RFMError as e:
            self.show_error_popup(e, title="Reset Error")
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
            self.master.geometry(f"{COLUMNNUM * COLUMNWIDTH}x{MINIHEIGHT}")
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
        if key_code == "Tab":
            highlighted_entry = highlighted_entry + 1
        if highlighted_entry == COLUMNNUM * 2 + 1:
            highlighted_entry = 1
        return highlighted_entry

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
                    if self.highlighted_entry == entry_flowset and c.toggleStates[i] == ToggleState.On:
                        c.update_flow_setpoint(i)
                for i, entry_channel in enumerate(entry_channel_list):
                    if self.highlighted_entry == entry_channel and c.toggleStates[i] == ToggleState.Off:
                        c.apply_changed_channel(i)
            except RFMError as e:
                self.show_error_popup(e, title="Input Apply Error")
        else:
            for i, entry_flowset in enumerate(entry_flowset_list):
                if self.highlighted_entry == entry_flowset and c.toggleStates[i] == ToggleState.On:
                    c.flowSetPoint_Entry[i] = self.modify_number_string_by_key(
                        c.flowSetPoint_Entry[i], event.keysym, event.char
                    )
            for i, entry_channel in enumerate(entry_channel_list):
                if self.highlighted_entry == entry_channel and c.toggleStates[i] == ToggleState.Off:
                    c.channelsEntry[i] = self.modify_number_string_by_key(
                        c.channelsEntry[i], event.keysym, event.char
                    )

    def modify_number_string_by_key(self, number_string, key_code, key):
        if key_code == "BackSpace" and len(number_string) > 0:
            number_string = number_string[:-1]
        if key.isdigit():
            number_string += key
        return number_string

    def get_column_index_from_mouse(self, mouseX):
        columnwidth = COLUMNWIDTH
        if not self.mn:
            columnwidth = COLUMNWIDTH * self.width / (COLUMNNUM * COLUMNWIDTH)
        return np.floor(mouseX / columnwidth)

    def get_row_index_from_mouse(self, mouseY):
        SENTINAL_VALUE = -1
        if not self.mn:
            if (mouseY < self.height * 266 / HEIGHT) and (mouseY > 139 * self.height / HEIGHT):
                return 0
            elif mouseY > self.height * 320 / HEIGHT:
                return 1
            else:
                return SENTINAL_VALUE
        else:
            if (mouseY < 266) and (mouseY > 139):
                return 0
            elif mouseY > 320:
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
        c = self.ctrl

        for i, entry_flowset in enumerate(entry_flowset_list):
            if entry == entry_flowset:
                self.flowSetPointBkgColors[i] = COLOR_HIGHLIGHTED
            else:
                self.flowSetPointBkgColors[i] = COLOR_BLACK
                c.flowSetPoint_Entry[i] = ""

        for i, entry_channel in enumerate(entry_channel_list):
            if entry == entry_channel:
                self.channelBkgColors[i] = COLOR_HIGHLIGHTED
            else:
                self.channelBkgColors[i] = COLOR_BLACK
                c.channelsEntry[i] = ""


def open_config_file(file_path: str):
    with open(file_path, "r") as file:
        config_data = json.load(file)
        arduino_port = config_data.get("arduino_port")
        localserver_port = config_data.get("localserver_port")
        pc_input_max = config_data.get("pc_input_max")
        arduino_read_max = config_data.get("arduino_read_max")

        if (
            not isinstance(arduino_port, str)
            or not isinstance(localserver_port, int)
            or not isinstance(pc_input_max, int)
            or not isinstance(arduino_read_max, int)
        ):
            raise ValueError("Invalid configuration data")

        return arduino_port, localserver_port, pc_input_max, arduino_read_max


def resource_path(relative_path):
    return bundle_path(relative_path)


if __name__ == "__main__":
    rfmapp = None

    flog.info("=== RFMdaemon process start ===")
    config_file_path = writable_path("rfm_config.json")
    try:
        flog.info(f"Loading config: {config_file_path}")
        arduino_port, localserver_port, pc_input_max, arduino_read_max = open_config_file(config_file_path)
        flog.info(
            f"Config ok: port={arduino_port} http={localserver_port} "
            f"pc_max={pc_input_max} adc_max={arduino_read_max}"
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
                },
                file,
            )
        arduino_port, localserver_port, pc_input_max, arduino_read_max = open_config_file(config_file_path)

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

    def run_app(port, pc_input_max, arduino_read_max):
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
            rfmapp = RFMApp(master, port, pc_input_max, arduino_read_max)
            flog.info("RFMdaemon GUI started (entering mainloop)")
            rfmapp.master.mainloop()
            flog.info("RFMdaemon mainloop exited")
        except RFMError as e:
            flog.critical(f"Application RFM error: {e}")
            try:
                messagebox.showerror("RFM Startup Error", str(e), parent=master)
            except Exception:
                pass
            rfmapp = None
            try:
                master.destroy()
            except Exception:
                pass
        except Exception as e:
            flog.critical(f"Application error: {e}")
            try:
                messagebox.showerror("Unexpected Error", str(e), parent=master)
            except Exception:
                pass
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
    run_app(arduino_port, pc_input_max, arduino_read_max)
