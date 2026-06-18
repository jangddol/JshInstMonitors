import tkinter as tk
from tkinter import messagebox

# arduino_deque channel index → human-readable info
CHANNEL_KEYS = ["P_st", "P_pl", "V_pl", "P_pur"]
CHANNEL_NAMES = ["P_storage", "P_plant", "V_plant", "P_purifier"]
CHANNEL_UNITS = ["psi", "psi", "L", "psi"]


class CalibrationWindow(tk.Toplevel):
    """Per-channel calibration dialog.

    Shows the current raw value live and lets the user define two reference
    points (orig1, calib1) and (orig2, calib2) for a linear mapping:
        calibrated = slope * raw + offset
    where slope and offset are derived from the two points.

    Parameters
    ----------
    parent:
        Parent widget (typically the PressureLevelSetting window).
    plotter:
        The PressureLevelPlotter instance that owns calibration state.
    channel_index:
        arduino_deque channel index (0=P_st, 1=P_pl, 2=V_pl, 3=P_pur).
    """

    def __init__(self, parent: tk.BaseWidget, plotter, channel_index: int):
        super().__init__(parent)
        self.plotter = plotter
        self.channel_index = channel_index

        name = CHANNEL_NAMES[channel_index]
        self._unit = CHANNEL_UNITS[channel_index]

        self.title(f"Calibration — {name}")
        self.resizable(False, False)
        self.geometry("340x230")
        self.transient(parent)

        self._build_ui()
        self._populate_entries()
        self._schedule_raw_update()

    def _build_ui(self) -> None:
        # --- Raw value display ---
        self._raw_label = tk.Label(
            self,
            text=f"Current raw value: — {self._unit}",
            font=("Arial", 11),
        )
        self._raw_label.pack(pady=(14, 6))

        # --- 2×2 entry matrix ---
        matrix_frame = tk.Frame(self)
        matrix_frame.pack(pady=6)

        tk.Label(matrix_frame, text="", width=8).grid(row=0, column=0)
        tk.Label(matrix_frame, text="Original", width=14,
                 font=("Arial", 10, "bold")).grid(row=0, column=1)
        tk.Label(matrix_frame, text="Calibrated", width=14,
                 font=("Arial", 10, "bold")).grid(row=0, column=2)

        tk.Label(matrix_frame, text="Point 1", width=8).grid(row=1, column=0, pady=6)
        tk.Label(matrix_frame, text="Point 2", width=8).grid(row=2, column=0, pady=6)

        self._entries: dict[str, tk.Entry] = {}
        for row_i, suffix in enumerate(("1", "2")):
            orig_entry = tk.Entry(matrix_frame, width=14)
            orig_entry.grid(row=row_i + 1, column=1, padx=6, pady=4)

            calib_entry = tk.Entry(matrix_frame, width=14)
            calib_entry.grid(row=row_i + 1, column=2, padx=6, pady=4)

            self._entries[f"orig{suffix}"] = orig_entry
            self._entries[f"calib{suffix}"] = calib_entry

        # --- Apply button ---
        tk.Button(self, text="Apply", command=self._apply, width=10).pack(pady=(6, 14))

    def _populate_entries(self) -> None:
        cal = self.plotter.calibrations[self.channel_index]
        for suffix in ("1", "2"):
            self._entries[f"orig{suffix}"].delete(0, tk.END)
            self._entries[f"orig{suffix}"].insert(0, str(cal[f"orig{suffix}"]))
            self._entries[f"calib{suffix}"].delete(0, tk.END)
            self._entries[f"calib{suffix}"].insert(0, str(cal[f"calib{suffix}"]))

    def _schedule_raw_update(self) -> None:
        self._update_raw()

    def _update_raw(self) -> None:
        if not self.winfo_exists():
            return
        try:
            raw = self.plotter.arduino_deque.get_last_data()[self.channel_index]
            self._raw_label.config(
                text=f"Current raw value: {raw:.4f} {self._unit}"
            )
        except Exception:
            self._raw_label.config(
                text=f"Current raw value: — {self._unit}"
            )
        self.after(200, self._update_raw)

    def _apply(self) -> None:
        try:
            orig1 = float(self._entries["orig1"].get())
            calib1 = float(self._entries["calib1"].get())
            orig2 = float(self._entries["orig2"].get())
            calib2 = float(self._entries["calib2"].get())
        except ValueError:
            messagebox.showerror(
                "Invalid input", "All four fields must be numeric.", parent=self
            )
            return

        if orig1 == orig2:
            messagebox.showerror(
                "Invalid input",
                "Original Point 1 and Point 2 must be different.",
                parent=self,
            )
            return

        self.plotter.calibrations[self.channel_index] = {
            "orig1": orig1,
            "calib1": calib1,
            "orig2": orig2,
            "calib2": calib2,
        }
        self.plotter._save_config()
