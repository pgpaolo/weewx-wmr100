#!/usr/bin/env python3
"""Offline regression tests for the hardened WMR100/WMR88 driver."""

from pathlib import Path
import importlib.util
import sys
import types

# ----- minimal dependency stubs -----
usb = types.ModuleType('usb')


class USBError(Exception):
    pass


usb.USBError = USBError
usb.ENDPOINT_IN = 0x80
usb.TYPE_CLASS = 0x20
usb.RECIP_INTERFACE = 0x01
usb.busses = lambda: []
sys.modules['usb'] = usb

weewx = types.ModuleType('weewx')


class WeeWxIOError(Exception):
    pass


class WakeupError(Exception):
    pass


class RetriesExceeded(Exception):
    pass


weewx.WeeWxIOError = WeeWxIOError
weewx.WakeupError = WakeupError
weewx.RetriesExceeded = RetriesExceeded
weewx.US = 1
weewx.METRIC = 2
weewx.METRICWX = 3

weewx_drivers = types.ModuleType('weewx.drivers')


class AbstractDevice:
    pass


class AbstractConfEditor:
    pass


weewx_drivers.AbstractDevice = AbstractDevice
weewx_drivers.AbstractConfEditor = AbstractConfEditor
weewx.drivers = weewx_drivers

weewx_wxformulas = types.ModuleType('weewx.wxformulas')


def calculate_rain(new, old):
    if new is None or old is None or new < old:
        return None
    return new - old


weewx_wxformulas.calculate_rain = calculate_rain
weewx.wxformulas = weewx_wxformulas

sys.modules['weewx'] = weewx
sys.modules['weewx.drivers'] = weewx_drivers
sys.modules['weewx.wxformulas'] = weewx_wxformulas

weeutil = types.ModuleType('weeutil')
weeutil_we = types.ModuleType('weeutil.weeutil')


class GenWithPeek:
    def __init__(self, gen):
        self.gen = iter(gen)
        self.have = False
        self.value = None

    def _fill(self):
        if not self.have:
            self.value = next(self.gen)
            self.have = True

    def peek(self):
        self._fill()
        return self.value

    def __iter__(self):
        return self

    def __next__(self):
        self._fill()
        value = self.value
        self.have = False
        self.value = None
        return value


weeutil_we.GenWithPeek = GenWithPeek
weeutil.weeutil = weeutil_we
sys.modules['weeutil'] = weeutil
sys.modules['weeutil.weeutil'] = weeutil_we

driver_path = Path(__file__).resolve().parents[1] / 'bin' / 'user' / 'wmr100.py'
spec = importlib.util.spec_from_file_location('wmr100_gp', driver_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Trace:
    enabled = False

    def write(self, payload):
        pass

    def close(self):
        pass


STAT_KEYS = [
    'usb_reports', 'usb_payload_bytes', 'usb_timeouts', 'usb_errors',
    'usb_spurious_no_error', 'usb_malformed_reports',
    'usb_soft_reinitialisations', 'usb_soft_reinitialisation_failures',
    'usb_recovery_cycles', 'usb_recovery_attempts', 'usb_recovery_failures',
    'packets_valid', 'packets_decoded', 'packets_unmapped', 'packets_unknown',
    'packets_malformed', 'checksum_errors', 'length_errors', 'parser_resyncs',
    'decoder_errors'
]


def make_driver():
    driver = mod.WMR100.__new__(mod.WMR100)
    driver.model = 'TEST'
    driver.model_profile = dict(mod._DEFAULT_PROFILE)
    driver.max_remote_channels = 8
    driver.sensor_map = dict(mod.WMR100.DEFAULT_MAP)
    driver.last_rain_total = None
    driver.last_time = None
    driver.max_packet_length = 64
    driver.strict_packet_lengths = True
    driver.developer_trace_packets = False
    driver.developer_trace_raw_reports = False
    driver._developer_trace = Trace()
    driver._trace_sequence = 0
    driver._health_state = 'healthy'
    driver._last_success_utc = None
    driver._last_success_monotonic = None
    driver.stats_log_interval = 0
    driver._next_stats_log = None
    driver.stats = {key: 0 for key in STAT_KEYS}
    return driver


samples = {
    0x41: [0x00, 0x41, 0xff, 0x02, 0x0c, 0x00, 0x00, 0x00,
           0x25, 0x00, 0x00, 0x0c, 0x01, 0x01, 0x06, 0x87, 0x01],
    0x42: [0x20, 0x42, 0xd1, 0x91, 0x00, 0x48, 0x64, 0x00,
           0x00, 0x20, 0x90, 0x02],
    0x46: [0x00, 0x46, 0xed, 0x03, 0xed, 0x33, 0x56, 0x02],
    0x47: [0x00, 0x47, 0x00, 0x05, 0x4c, 0x00],
    0x48: [0x00, 0x48, 0x0a, 0x0c, 0x16, 0xe0, 0x02, 0x00,
           0x20, 0x76, 0x01],
    0x60: [0x00, 0x60, 0x00, 0x00, 0x14, 0x09, 0x1c, 0x04,
           0x09, 0x01, 0xa7, 0x00],
}

# Packet validation.
driver = make_driver()
for packet_type, packet in samples.items():
    assert sum(packet[:-2]) == ((packet[-1] << 8) + packet[-2]), hex(packet_type)
    assert driver._process_packet_buffer(packet) == packet, hex(packet_type)

# Decoder checks.
record = driver._temperature_packet(samples[0x42])
assert record['temperature_1'] == 14.5
assert record['humidity_1'] == 72.0
assert record['battery_status_1'] == 0
assert record['console_dewpoint_1'] == 10.0

record = driver._wind_packet(samples[0x48])
assert record['wind_dir'] == 225.0
assert abs(record['wind_speed'] - 4.6) < 1e-9
assert record['wind_gust'] is None

record = driver._pressure_packet(samples[0x46])
assert record['pressure'] == 1005.0
assert record['console_barometer'] == 1005.0
assert record['forecast_code'] == 0
assert record['previous_forecast_code'] == 3

record = driver._rain_packet(samples[0x41])
assert abs(record['rain_rate'] - 7.67) < 1e-9
assert abs(record['rain_total'] - 0.37) < 1e-9
assert record['rain'] is None
second_rain = list(samples[0x41])
second_rain[8] = 0x29
checksum = sum(second_rain[:-2])
second_rain[-2] = checksum & 0xff
second_rain[-1] = (checksum >> 8) & 0xff
record = driver._rain_packet(second_rain)
assert abs(record['rain'] - 0.04) < 1e-9

# Bad checksum rejected.
bad = list(samples[0x47])
bad[3] = 6
assert driver._process_packet_buffer(bad) is None
assert driver.stats['checksum_errors'] == 1

# Valid checksum but wrong known length rejected.
wrong_len = samples[0x47][:-2] + [0x00] + [0x00, 0x00]
checksum = sum(wrong_len[:-2])
wrong_len[-2] = checksum & 0xff
wrong_len[-1] = (checksum >> 8) & 0xff
assert driver._process_packet_buffer(wrong_len) is None
assert driver.stats['length_errors'] == 1

# Full stream framing with FF FF separators.
stream = ([0xff, 0xff] + samples[0x47] + [0xff, 0xff] +
          samples[0x46] + [0xff, 0xff])
driver2 = make_driver()
driver2._genBytes_raw = lambda: iter(stream)
packets = list(driver2.genPackets())
assert packets == [samples[0x47], samples[0x46]]

print('Packet and decoder tests passed.')


# USB lifecycle and recovery tests.
class TimeoutUSBError(USBError):
    def __init__(self, message, err_no=None):
        super().__init__(message)
        self.errno = err_no


class FakeHandle:
    def __init__(self, reads=None):
        self.reads = list(reads or [])
        self.controls = []
        self.claimed = False
        self.released = False

    def detachKernelDriver(self, interface):
        raise USBError('no kernel driver')

    def claimInterface(self, interface):
        self.claimed = True

    def releaseInterface(self):
        self.released = True

    def controlMsg(self, request_type, request, command, value, index, timeout):
        self.controls.append(list(command))

    def interruptRead(self, endpoint, size, timeout):
        item = self.reads.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeDevice:
    idVendor = 0x0fde
    idProduct = 0xca01

    def __init__(self, handles):
        self.handles = list(handles)

    def open(self):
        return self.handles.pop(0)


class FakeBus:
    def __init__(self, device):
        self.devices = [device]


# Generic WMR100 keeps upstream single-command default.
handle = FakeHandle()
device = FakeDevice([handle])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR100', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0)
assert instance.model == 'WMR100'
assert instance.send_data_request is False
assert handle.controls == [mod._INIT_COMMAND]
instance.closePort()

# WMR88 profile enables the live-data request and conservative watchdog.
handle = FakeHandle()
device = FakeDevice([handle])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR-88', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0,
                      command_delay=0)
assert instance.model == 'WMR88'
assert instance.hardware_name == 'WMR88'
assert instance.send_data_request is True
assert instance.timeout_warning_threshold == 8
assert instance.timeout_reinit_threshold == 12
assert instance.timeout_recovery_threshold == 20
assert instance.max_remote_channels == 3
assert handle.controls == [mod._INIT_COMMAND, mod._DATA_REQUEST_COMMAND]
instance.closePort()

# WMR88 soft reinitialisation after 12 timeouts, without reopening the device.
timeouts = [TimeoutUSBError('Operation timed out', 110) for _ in range(12)]
handle = FakeHandle(timeouts + [[1, 0xaa, 0, 0, 0, 0, 0, 0]])
device = FakeDevice([handle])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR88A', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0,
                      command_delay=0)
assert next(instance._genBytes_raw()) == 0xaa
assert instance.stats['usb_timeouts'] == 12
assert instance.stats['usb_soft_reinitialisations'] == 1
assert instance.stats['usb_recovery_cycles'] == 0
assert handle.controls == [
    mod._INIT_COMMAND, mod._DATA_REQUEST_COMMAND,
    mod._INIT_COMMAND, mod._DATA_REQUEST_COMMAND,
]
instance.closePort()

# Full reopen remains available after a configured threshold.
first = FakeHandle([
    TimeoutUSBError('Operation timed out', 110),
    TimeoutUSBError('Operation timed out', 110),
])
second = FakeHandle([[1, 0xbb, 0, 0, 0, 0, 0, 0]])
device = FakeDevice([first, second])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR88', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0,
                      command_delay=0, timeout_reinit_threshold=0,
                      timeout_recovery_threshold=2, recovery_max_tries=1)
assert next(instance._genBytes_raw()) == 0xbb
assert instance.stats['usb_timeouts'] == 2
assert instance.stats['usb_recovery_cycles'] == 1
assert second.controls == [mod._INIT_COMMAND, mod._DATA_REQUEST_COMMAND]
instance.closePort()

print('WMR88/WMR88A profile, USB lifecycle and recovery tests passed.')
print('All hardened-driver tests passed.')
