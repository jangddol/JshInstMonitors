"""Headless verification of RFM GUI/logic split, serial timeout, and error propagation."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import time
import traceback

RFM_DIR = os.path.dirname(os.path.abspath(__file__))
COMMON_DIR = os.path.abspath(os.path.join(RFM_DIR, "..", "..", "common"))
sys.path.insert(0, RFM_DIR)
sys.path.insert(0, COMMON_DIR)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def test_error_hierarchy() -> None:
    print("\n[1] Error hierarchy")
    from rfm_errors import RFMControllerError, RFMError, RFMSerialError, RFMSerialTimeout

    check("RFMSerialError is RFMError", issubclass(RFMSerialError, RFMError))
    check("RFMSerialTimeout is RFMSerialError", issubclass(RFMSerialTimeout, RFMSerialError))
    check("RFMControllerError is RFMError", issubclass(RFMControllerError, RFMError))
    check("timeout catchable as RFMError", isinstance(RFMSerialTimeout("t"), RFMError))


def test_controller_no_tk() -> None:
    print("\n[2] GUI / logic separation")
    import rfm_controller

    src = open(os.path.join(RFM_DIR, "rfm_controller.py"), encoding="utf-8").read()
    check("rfm_controller has no tkinter import", "tkinter" not in src and "import tk" not in src)
    check("RFMController class exists", hasattr(rfm_controller, "RFMController"))

    daemon_src = open(os.path.join(RFM_DIR, "RFMdaemon.py"), encoding="utf-8").read()
    check("RFMdaemon imports RFMController", "from rfm_controller import" in daemon_src)
    check("RFMdaemon imports rfm_errors", "from rfm_errors import" in daemon_src)
    check("RFMdaemon uses messagebox", "messagebox" in daemon_src)


def test_sim_controller_happy_path() -> None:
    print("\n[3] Controller + sim serial happy path")
    from FuncLogger import FuncLogger
    from rfm_controller import RFMController, ToggleState
    from channel import Channel

    with tempfile.TemporaryDirectory() as tmp:
        # FuncLogger writes under writable_path; just exercise API
        flog = FuncLogger("flowtemp", "RFM_test")
        c = RFMController(False, "COM99", 99, 4095, flog)
        vals = c.read_flow_values()
        check("sim read returns 4 channels", len(vals) == 4, str(vals))
        check("sim read all zero initially", vals == [0.0, 0.0, 0.0, 0.0], str(vals))

        c.channelsEntry[0] = "1"
        c.apply_changed_channel(0)
        check("channel map col0 -> CH1", c.channels[0] == Channel.CH1)

        c.toggle_switch(0, last_switch_state=False)
        check("toggle On sets ToggleState.On", c.toggleStates[0] == ToggleState.On)

        vals2 = c.read_flow_values()
        check("sim read after On still 4 floats", len(vals2) == 4 and all(isinstance(x, float) for x in vals2))

        c.flowSetPoint_Entry[0] = "10"
        c.update_flow_setpoint(0)
        check("setpoint shown updated", c.flowSetPoints_Shown[0] == "10")

        c.reset_hardware()
        check("reset clears channel", c.channels[0] == Channel.CH_UNKNOWN)
        check("reset clears toggle", c.toggleStates[0] == ToggleState.Off)


def test_serial_timeout_raises() -> None:
    print("\n[4] Serial timeout (no infinite hang)")
    from rfm_errors import RFMSerialTimeout
    from RFMserial import (
        DEFAULT_OVERALL_READ_TIMEOUT_S,
        DEFAULT_READ_TIMEOUT_S,
        EXPECTED_LINE_LEN,
        RFMserial_Real,
    )

    check("read timeout configured", DEFAULT_READ_TIMEOUT_S > 0 and DEFAULT_READ_TIMEOUT_S <= 1.0)
    check("overall timeout configured", DEFAULT_OVERALL_READ_TIMEOUT_S > DEFAULT_READ_TIMEOUT_S)
    check("expected line len is 34", EXPECTED_LINE_LEN == 34)

    # Fake Real-like object: empty reads until deadline → RFMSerialTimeout
    class EmptyPort:
        def read_until(self, expected=b"\n"):
            time.sleep(0.05)
            return b""

    fake = RFMserial_Real.__new__(RFMserial_Real)
    fake.port = "FAKE"
    fake.baudrate = 9600
    fake.ser = EmptyPort()

    t0 = time.monotonic()
    raised = None
    try:
        fake.readline_serial(overall_timeout=0.35)
    except RFMSerialTimeout as e:
        raised = e
    except Exception as e:
        raised = e
    elapsed = time.monotonic() - t0

    check("readline raises RFMSerialTimeout", isinstance(raised, RFMSerialTimeout), repr(raised))
    check("timeout completes under 2s (no hang)", elapsed < 2.0, f"elapsed={elapsed:.2f}s")
    check("timeout waited roughly overall_timeout", 0.25 <= elapsed <= 1.5, f"elapsed={elapsed:.2f}s")


def test_error_propagation_controller() -> None:
    print("\n[5] Error propagation serial → controller")
    from FuncLogger import FuncLogger
    from rfm_controller import RFMController
    from rfm_errors import RFMError, RFMSerialError, RFMSerialTimeout

    class FakeSerial:
        def __init__(self):
            self.mode = "timeout"

        def readline_serial(self, overall_timeout=0.8):
            if self.mode == "timeout":
                raise RFMSerialTimeout("no line")
            if self.mode == "io":
                raise RFMSerialError("port gone")
            if self.mode == "bad":
                return "not-a-valid-payload"
            return "0000000000000000000000000000000000"

        def writeFlowSetpoint_serial(self, *a, **k):
            raise RFMSerialError("write fail")

        def writeChannelOn_serial(self, *a, **k):
            pass

        def writeChannelOff_serial(self, *a, **k):
            pass

        def reset_serial(self):
            raise RFMSerialError("reset fail")

    flog = FuncLogger("flowtemp", "RFM_test")
    c = RFMController(False, "COM99", 99, 4095, flog)
    fake = FakeSerial()
    c.serial = fake

    fake.mode = "timeout"
    try:
        c.read_flow_values()
        check("timeout re-raised", False, "no exception")
    except RFMSerialTimeout:
        check("timeout re-raised as RFMSerialTimeout", True)
    except Exception as e:
        check("timeout re-raised as RFMSerialTimeout", False, repr(e))

    fake.mode = "io"
    try:
        c.read_flow_values()
        check("serial I/O re-raised", False)
    except RFMSerialError as e:
        check("serial I/O re-raised as RFMSerialError", not isinstance(e, RFMSerialTimeout))
    except Exception as e:
        check("serial I/O re-raised as RFMSerialError", False, repr(e))

    fake.mode = "bad"
    try:
        c.read_flow_values()
        check("parse error raised", False)
    except RFMError:
        check("parse error raised as RFMError", True)
    except Exception as e:
        check("parse error raised as RFMError", False, repr(e))

    c.channelsEntry[0] = "1"
    c.apply_changed_channel(0)
    try:
        c.toggle_switch(0, False)
        check("toggle write error raised", False)
    except RFMSerialError:
        check("toggle write error propagates", True)
    except Exception as e:
        check("toggle write error propagates", False, repr(e))

    try:
        c.reset_hardware()
        check("reset error raised", False)
    except RFMSerialError:
        check("reset error propagates", True)
    except Exception as e:
        check("reset error propagates", False, repr(e))


def test_gui_error_helpers_exist() -> None:
    print("\n[6] GUI error popup wiring (source-level)")
    src = open(os.path.join(RFM_DIR, "RFMdaemon.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    check("show_error_popup defined", "show_error_popup" in methods)
    check("clear_error_popup_dedupe defined", "clear_error_popup_dedupe" in methods)
    check("main_loop catches RFMError", "except RFMError" in src)
    check("run_app catches RFMError on startup", src.count("except RFMError") >= 2)


def test_makefile_and_conflict_cleanup() -> None:
    print("\n[7] Makefile python launcher + conflict cleanup")
    for rel in (
        "Flow_and_Temp/RFM/makefile.bat",
        "Flow_and_Temp/FlowTempPlotter/makefile.bat",
        "Pressure_and_Level/PressureLevelPlotter/makefile.bat",
    ):
        path = os.path.join(RFM_DIR, "..", "..", rel.replace("/", os.sep))
        path = os.path.normpath(path)
        text = open(path, encoding="utf-8").read().strip()
        check(f"{os.path.basename(os.path.dirname(path))}: uses python not python3", text.startswith("python "))
        check(f"{os.path.basename(os.path.dirname(path))}: no python3.exe", "python3" not in text)

    ftp = os.path.normpath(os.path.join(RFM_DIR, "..", "FlowTempPlotter", "FlowTempPlotter.py"))
    ftp_src = open(ftp, encoding="utf-8").read()
    check("FlowTempPlotter has no conflict markers", "<<<<<<<" not in ftp_src and ">>>>>>>" not in ftp_src)

    rfm_mk = open(os.path.join(RFM_DIR, "makefile.bat"), encoding="utf-8").read()
    check("RFM makefile hides rfm_controller", "rfm_controller" in rfm_mk)
    check("RFM makefile hides rfm_errors", "rfm_errors" in rfm_mk)


def test_syntax_all_modules() -> None:
    print("\n[8] Syntax of RFM modules")
    for name in ("RFMserial.py", "rfm_controller.py", "rfm_errors.py", "RFMdaemon.py", "channel.py", "schedularwindow.py"):
        path = os.path.join(RFM_DIR, name)
        try:
            ast.parse(open(path, encoding="utf-8").read())
            check(f"syntax {name}", True)
        except SyntaxError as e:
            check(f"syntax {name}", False, str(e))


def test_gui_input_fixes() -> None:
    print("\n[9] GUI number-input fixes (1-6)")
    from FuncLogger import FuncLogger
    from rfm_controller import RFMController, ToggleState
    from channel import Channel
    from RFMdaemon import RFMApp, COLUMNNUM

    flog = FuncLogger("flowtemp", "RFM_test")
    c = RFMController(False, "COM99", 99, 4095, flog)

    # (1) SelectChannel is recoverable via channel map
    c.toggle_switch(0, last_switch_state=False)
    check("SelectChannel when no channel", c.toggleStates[0] == ToggleState.SelectChannel)
    c.channelsEntry[0] = "1"
    ok = c.apply_changed_channel(0)
    check("apply channel returns True", ok is True)
    check("channel mapped to CH1", c.channels[0] == Channel.CH1)
    check("SelectChannel cleared to Off", c.toggleStates[0] == ToggleState.Off)

    # (4) invalid channel feedback
    c.channelsEntry[0] = "9"
    ok2 = c.apply_changed_channel(0)
    check("invalid channel returns False", ok2 is False)
    check("invalid keeps previous channel", c.channels[0] == Channel.CH1)
    check("invalid keeps typed buffer", c.channelsEntry[0] == "9")

    # GUI helpers without Tk mainloop
    app = RFMApp.__new__(RFMApp)
    app.mn = False
    app.width = COLUMNNUM * 235
    app.height = 385
    app.ctrl = c

    # (2) arrow / Tab navigation
    check("Tab 1->2", app.get_highlight_entry_using_keycode("Tab", 1) == 2)
    check("Right wrap 8->1", app.get_highlight_entry_using_keycode("Right", 8) == 1)
    check("Left wrap 1->8", app.get_highlight_entry_using_keycode("Left", 1) == 8)
    check("Down 1->5", app.get_highlight_entry_using_keycode("Down", 1) == 5)
    check("Up 5->1", app.get_highlight_entry_using_keycode("Up", 5) == 1)
    check("Down on channel stays", app.get_highlight_entry_using_keycode("Down", 5) == 5)

    # (5) length limits
    check(
        "setpoint max_len blocks",
        app.modify_number_string_by_key("99", "1", "1", max_len=2) == "99",
    )
    check(
        "channel max_len 1",
        app.modify_number_string_by_key("1", "2", "2", max_len=1) == "1",
    )
    check(
        "backspace works",
        app.modify_number_string_by_key("12", "BackSpace", "", max_len=2) == "1",
    )

    # (3) change_highlight must not wipe drafts — verify method body no longer clears
    src = open(os.path.join(RFM_DIR, "RFMdaemon.py"), encoding="utf-8").read()
    # crude: after change_highlight_entry_to, clearing flowSetPoint_Entry should be gone
    import re

    m = re.search(
        r"def change_highlight_entry_to\(self, entry\):(.*?)(?=\ndef |\Z)",
        src,
        re.S,
    )
    body = m.group(1) if m else ""
    check("highlight does not clear flowSetPoint_Entry", "flowSetPoint_Entry" not in body)
    check("highlight does not clear channelsEntry", "channelsEntry" not in body)

    # (6) mini mode mouse hit-test disabled
    app.mn = True
    check("mini mouse row is -1", app.get_row_index_from_mouse(200) == -1)
    check(
        "mini mouse no highlight",
        app.get_highlited_entry_from_mouse(100, 200) == 0,
    )

    # SelectChannel allows channel edit
    c2 = RFMController(False, "COM99", 99, 4095, flog)
    c2.toggleStates[0] = ToggleState.SelectChannel
    app.ctrl = c2
    check("can edit channel in SelectChannel", app._can_edit_channel(0) is True)
    check("cannot edit setpoint in SelectChannel", app._can_edit_setpoint(0) is False)


def main() -> int:
    print("=== RFM change verification ===")
    tests = [
        test_error_hierarchy,
        test_controller_no_tk,
        test_sim_controller_happy_path,
        test_serial_timeout_raises,
        test_error_propagation_controller,
        test_gui_error_helpers_exist,
        test_makefile_and_conflict_cleanup,
        test_syntax_all_modules,
        test_gui_input_fixes,
    ]
    for fn in tests:
        try:
            fn()
        except Exception:
            global FAIL
            FAIL += 1
            print(f"  FAIL  {fn.__name__} crashed:\n{traceback.format_exc()}")

    print(f"\n=== RESULT: {PASS} passed, {FAIL} failed ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
