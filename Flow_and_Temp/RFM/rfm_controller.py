"""RFM daemon business logic — serial I/O, channel state, scheduling (no Tk)."""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, Final, List, Optional, Sequence

from RFMserial import RFMserial
from channel import Channel, convert_int_to_channel
from schedularwindow import Action
from FuncLogger import FuncLogger
from rfm_errors import RFMControllerError, RFMSerialError, RFMSerialTimeout

COLUMNNUM = 4


class ToggleState(Enum):
    On = 1
    Off = 2
    SelectChannel = 3


class RFMController:
    """Owns MFC channel state and serial/schedule logic. GUI only observes/commands."""

    DAY_TO_HOUR: Final = 24
    HOUR_TO_MIN: Final = 60

    def __init__(
        self,
        serial_on: bool,
        port: str,
        pc_input_max: int,
        arduino_read_max: int,
        flog: FuncLogger,
    ):
        self.pc_input_max = pc_input_max
        self.arduino_read_max = arduino_read_max
        self.flog = flog
        self.last_read_time = time.time()
        self.last_schedule_handle_time_in_min = self.get_time_in_min()
        self._serial_timeout_logged = False
        self._read_ok_count = 0
        self._read_log_every = 50  # ~5s at 100ms tick — avoid flooding flog

        self.flog.info(
            f"Controller init: port={port} serial_on={serial_on} "
            f"pc_input_max={pc_input_max} arduino_read_max={arduino_read_max}"
        )
        self.reset_state()
        self.flog.info("Opening serial")
        try:
            self.serial = RFMserial(serial_on, port, 9600)
        except RFMSerialError:
            self.flog.error("Opening serial failed")
            raise
        except Exception as e:
            self.flog.error(f"Opening serial unexpected error: {e}")
            raise RFMControllerError(f"Failed to open serial: {e}") from e
        self.flog.info("Serial ready")

    def reset_state(self) -> None:
        self.flowSetPoint_Entry = [""] * COLUMNNUM
        self.flowSetPoints_Shown = ["  Set Channel"] * COLUMNNUM
        self.toggleStates = [ToggleState.Off] * COLUMNNUM
        self.channels = [Channel.CH_UNKNOWN] * COLUMNNUM
        self.channelsEntry = [""] * COLUMNNUM
        self.last_flow_values = [0.0] * COLUMNNUM
        self.flog.info("Channel state reset")

    def get_time_in_min(self) -> int:
        localtime = time.localtime()
        return (
            localtime.tm_wday * self.DAY_TO_HOUR * self.HOUR_TO_MIN
            + localtime.tm_hour * self.HOUR_TO_MIN
            + localtime.tm_min
        )

    def parse_flow_serial_buffer(self, flow_string: str) -> List[float]:
        # aaaabbbbccccdddd… — first four 4-digit groups are channel ADC bits
        try:
            flows = [int(flow_string[i : i + 4]) for i in range(0, len(flow_string), 4)]
            return [x * self.pc_input_max / self.arduino_read_max / 10 for x in flows]
        except Exception as e:
            raise RFMControllerError(f"Failed to parse serial buffer: {e}") from e

    def read_flow_values(self) -> List[float]:
        """
        One bounded read attempt.

        On success updates last_flow_values and returns them.
        On serial/controller failure: logs, then re-raises so GUI can popup.
        """
        try:
            serial_buffer = self.serial.readline_serial()
        except RFMSerialTimeout as e:
            if not self._serial_timeout_logged:
                self.flog.caution(f"read_flow_values: {e}")
                self._serial_timeout_logged = True
            raise
        except RFMSerialError as e:
            self.flog.error(f"read_flow_values: serial error: {e}")
            raise
        except Exception as e:
            self.flog.error(f"read_flow_values: unexpected: {e}")
            raise RFMControllerError(f"Serial read failed: {e}") from e

        if self._serial_timeout_logged:
            self.flog.info("read_flow_values: serial recovered after timeout")
        self._serial_timeout_logged = False

        try:
            flows = self.parse_flow_serial_buffer(serial_buffer)
            flow_values = [0.0] * COLUMNNUM
            for i in range(COLUMNNUM):
                if self.channels[i] != Channel.CH_UNKNOWN:
                    flow_values[i] = flows[int(self.channels[i].value) - 1]
                else:
                    flow_values[i] = 0.0
            self.last_read_time = time.time()
            self.last_flow_values = flow_values
            self._read_ok_count += 1
            if self._read_ok_count == 1 or self._read_ok_count % self._read_log_every == 0:
                self.flog.info(
                    f"read_flow_values: ok #{self._read_ok_count} "
                    f"len={len(serial_buffer)} raw={serial_buffer}"
                )
            return flow_values
        except RFMControllerError:
            self.flog.caution("read_flow_values: parse error")
            raise
        except Exception as e:
            self.flog.caution(f"read_flow_values: parse error: {e}")
            raise RFMControllerError(f"Failed to parse flow values: {e}") from e

    def is_valid_flow_setpoint(self, flow_setpoint_entry: str) -> bool:
        try:
            flow_setpoint = int(flow_setpoint_entry)
        except Exception:
            return False
        return 0 <= flow_setpoint <= self.pc_input_max

    def update_flow_setpoint(self, index: int) -> None:
        if self.channels[index] == Channel.CH_UNKNOWN:
            self.flowSetPoints_Shown[index] = "Set Channel"
            self.flog.caution(f"setpoint ch{index}: channel not set")
            return

        if not self.is_valid_flow_setpoint(self.flowSetPoint_Entry[index]):
            self.flowSetPoints_Shown[index] = "Input invalid"
            self.flog.caution(f"setpoint ch{index}: invalid '{self.flowSetPoint_Entry[index]}'")
            return

        self.flog.info(
            f"setpoint ch{index}: write {self.flowSetPoint_Entry[index]} -> {self.channels[index]}"
        )
        try:
            self.serial.writeFlowSetpoint_serial(self.flowSetPoint_Entry[index], self.channels[index])
        except RFMSerialError as e:
            self.flog.error(f"setpoint ch{index}: serial write failed: {e}")
            raise
        except Exception as e:
            self.flog.error(f"setpoint ch{index}: unexpected write error: {e}")
            raise RFMControllerError(f"Setpoint write failed: {e}") from e
        self.flowSetPoints_Shown[index] = self.flowSetPoint_Entry[index]

    def apply_changed_channel(self, index: int) -> bool:
        """Map typed channel number. Returns True on success (1-4), False if invalid."""
        raw = self.channelsEntry[index]
        try:
            channelEntry_int = int(raw) if raw != "" else 0
        except Exception:
            channelEntry_int = 0

        channel = convert_int_to_channel(channelEntry_int)
        if channel == Channel.CH_UNKNOWN:
            self.flog.caution(f"channel map col{index}: invalid '{raw}' (need 1-4)")
            return False

        self.channelsEntry[index] = ""
        self.channels[index] = channel
        self.flowSetPoints_Shown[index] = "paused"
        # Leave SelectChannel (need-channel-first) so channel input / On work again.
        if self.toggleStates[index] == ToggleState.SelectChannel:
            self.toggleStates[index] = ToggleState.Off
        self.flog.info(f"channel map col{index} -> {self.channels[index].value}")
        return True

    def toggle_switch(self, switch_index: int, last_switch_state: bool) -> None:
        """Apply On/Off logic. last_switch_state True means currently ON (sunken)."""
        if last_switch_state:
            self.toggleStates[switch_index] = ToggleState.Off
            if self.channels[switch_index] == Channel.CH_UNKNOWN:
                self.flog.info(f"toggle col{switch_index}: Off (no channel)")
                return

            self.flowSetPoints_Shown[switch_index] = "paused"
            self.flowSetPoint_Entry[switch_index] = ""
            self.flog.info(f"toggle col{switch_index}: Off -> {self.channels[switch_index]}")
            try:
                self.serial.writeFlowSetpoint_serial("0", self.channels[switch_index])
                self.serial.writeChannelOff_serial(self.channels[switch_index])
            except RFMSerialError as e:
                self.flog.error(f"toggle Off serial failed: {e}")
                raise
            except Exception as e:
                self.flog.error(f"toggle Off unexpected: {e}")
                raise RFMControllerError(f"Channel Off failed: {e}") from e
        else:
            if self.channels[switch_index] == Channel.CH_UNKNOWN:
                # SelectChannel: button stays Off; channel digits are accepted until mapped.
                self.toggleStates[switch_index] = ToggleState.SelectChannel
                self.flowSetPoints_Shown[switch_index] = "Set Channel"
                self.flog.caution(f"toggle col{switch_index}: need channel first (SelectChannel)")
                return

            self.toggleStates[switch_index] = ToggleState.On
            self.flowSetPoints_Shown[switch_index] = "0"
            self.flog.info(f"toggle col{switch_index}: On -> {self.channels[switch_index]}")
            try:
                self.serial.writeFlowSetpoint_serial("0", self.channels[switch_index])
                self.serial.writeChannelOn_serial(self.channels[switch_index])
            except RFMSerialError as e:
                self.flog.error(f"toggle On serial failed: {e}")
                raise
            except Exception as e:
                self.flog.error(f"toggle On unexpected: {e}")
                raise RFMControllerError(f"Channel On failed: {e}") from e

    def reset_hardware(self) -> None:
        self.flog.info("RESET: state + serial")
        self.reset_state()
        try:
            self.serial.reset_serial()
        except RFMSerialError as e:
            self.flog.error(f"RESET serial failed: {e}")
            raise
        except Exception as e:
            self.flog.error(f"RESET unexpected: {e}")
            raise RFMControllerError(f"Hardware reset failed: {e}") from e

    def handle_schedular(
        self,
        schedules: Sequence,
        on_ui_toggle: Optional[Callable[[int], None]] = None,
    ) -> None:
        if not schedules:
            return

        localtime = time.localtime()
        for schedule in schedules:
            if self.is_needed_to_do_scheduling(schedule, localtime):
                self.flog.info(
                    f"schedular: fire {schedule.channelname} {schedule.action} "
                    f"@ {schedule.day}/{schedule.hour:02d}:{schedule.minute:02d}"
                )
                try:
                    self.process_schedule_action(schedule, on_ui_toggle=on_ui_toggle)
                except RFMSerialError:
                    self.flog.error("schedular: serial error during action")
                    raise
                except RFMControllerError:
                    self.flog.error("schedular: controller error during action")
                    raise

        self.last_schedule_handle_time_in_min = self.get_time_in_min()

    def is_needed_to_do_scheduling(self, schedule, localtime) -> bool:
        try:
            schedule.day.get_int()
        except Exception:
            self.flog.caution("Invalid schedule data: day")
            return False
        try:
            schedule.hour
        except Exception:
            self.flog.caution("Invalid schedule data: hour")
            return False
        try:
            schedule.minute
        except Exception:
            self.flog.caution("Invalid schedule data: minute")
            return False
        if schedule.action == Action.Setpoint:
            try:
                schedule.number
            except Exception:
                self.flog.caution("Invalid schedule data: setpoint")
                return False

        is_same_day = schedule.day.get_int() == localtime.tm_wday
        is_same_time = schedule.hour == localtime.tm_hour and schedule.minute == localtime.tm_min
        is_different_time_with_last_time = (
            self.last_schedule_handle_time_in_min != self.get_time_in_min()
        )
        return is_same_day and is_same_time and is_different_time_with_last_time

    def process_schedule_action(
        self,
        schedule,
        on_ui_toggle: Optional[Callable[[int], None]] = None,
    ) -> None:
        channel_index = schedule.channelname.get_column()
        channel = self.channels[channel_index]
        if channel == Channel.CH_UNKNOWN:
            self.flog.caution(f"schedular: col{channel_index} has no channel mapped")
            return

        action = schedule.action
        if action == Action.On:
            if self.toggleStates[channel_index] == ToggleState.Off:
                if on_ui_toggle:
                    on_ui_toggle(channel_index)
                else:
                    self.toggle_switch(channel_index, last_switch_state=False)
        elif action == Action.Off:
            if self.toggleStates[channel_index] == ToggleState.On:
                if on_ui_toggle:
                    on_ui_toggle(channel_index)
                else:
                    self.toggle_switch(channel_index, last_switch_state=True)
        elif action == Action.Setpoint:
            if self.toggleStates[channel_index] == ToggleState.On:
                self.flowSetPoint_Entry[channel_index] = str(schedule.number)
                self.update_flow_setpoint(channel_index)
