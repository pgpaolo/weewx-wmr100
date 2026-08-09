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




class CapturingTrace:
    enabled = True

    def __init__(self):
        self.events = []

    def write(self, payload):
        self.events.append(dict(payload))

    def close(self):
        pass


STAT_KEYS = [
    'usb_reports', 'usb_payload_bytes', 'usb_timeouts',
    'usb_timeout_episodes', 'usb_timeout_recoveries',
    'usb_timeout_warning_episodes', 'usb_timeout_max_consecutive', 'usb_errors',
    'usb_spurious_no_error', 'usb_malformed_reports',
    'usb_soft_reinitialisations', 'usb_soft_reinitialisation_failures',
    'usb_recovery_cycles', 'usb_recovery_attempts', 'usb_recovery_failures',
    'packets_valid', 'packets_decoded', 'packets_unmapped', 'packets_unknown',
    'packets_malformed', 'checksum_errors', 'length_errors', 'parser_resyncs',
    'parser_leading_ff_recoveries', 'decoder_errors'
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
    driver._stream_resync_required = False
    driver._stream_resync_reason = None
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

# Regression gp6: the native console forecast code is exposed through the
# standard WeeWX forecastIcon observation without mapping console pressure to
# barometer/altimeter.
assert mod.WMR100.DEFAULT_MAP['forecastIcon'] == 'forecast_code'
assert 'barometer' not in mod.WMR100.DEFAULT_MAP
assert 'altimeter' not in mod.WMR100.DEFAULT_MAP

driver_forecast = make_driver()
driver_forecast.genPackets = lambda: iter([samples[0x46]])
loop = list(driver_forecast.genLoopPackets())
assert len(loop) == 1
assert loop[0]['pressure'] == 1005.0
assert loop[0]['forecastIcon'] == 0
assert 'barometer' not in loop[0]
assert 'altimeter' not in loop[0]

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

# Regression gp5: a real WMR88 clock frame was observed immediately after
# startup with one residual leading FF left after an FF FF FF delimiter run.
# The 13-byte buffer fails checksum, while removing exactly one leading FF
# produces the documented 12-byte clock packet with a perfect checksum.
real_wmr88_clock = [0xb0, 0x60, 0x00, 0x00, 0x38, 0x12, 0x07, 0x08,
                    0x1a, 0x00, 0x83, 0x01]
leading_ff_clock = [0xff] + real_wmr88_clock
assert sum(real_wmr88_clock[:-2]) == ((real_wmr88_clock[-1] << 8) + real_wmr88_clock[-2])
driver_gp5 = make_driver()
trace_gp5 = CapturingTrace()
driver_gp5._developer_trace = trace_gp5
assert driver_gp5._process_packet_buffer(leading_ff_clock) == real_wmr88_clock
assert driver_gp5.stats['parser_leading_ff_recoveries'] == 1
assert driver_gp5.stats['checksum_errors'] == 0
recovery_events = [e for e in trace_gp5.events
                   if e.get('event') == 'packet_leading_ff_recovered']
assert len(recovery_events) == 1
assert recovery_events[0]['packet_type'] == '0x60'
assert recovery_events[0]['packet_name'] == 'clock'
assert recovery_events[0]['severity'] == 'info'
assert recovery_events[0]['impact'] == 'none_packet_recovered'
assert recovery_events[0]['original_length'] == 13
assert recovery_events[0]['recovered_length'] == 12
assert recovery_events[0]['checksum_calculated'] == 0x0183
assert recovery_events[0]['checksum_received'] == 0x0183

# Full framing regression: FF FF FF followed by the real WMR88 clock frame
# must emit one valid clock packet rather than a checksum error.
triple_ff_stream = ([0xff, 0xff, 0xff] + real_wmr88_clock + [0xff, 0xff])
driver_triple = make_driver()
driver_triple._genBytes_raw = lambda: iter(triple_ff_stream)
assert list(driver_triple.genPackets()) == [real_wmr88_clock]
assert driver_triple.stats['parser_leading_ff_recoveries'] == 1
assert driver_triple.stats['checksum_errors'] == 0

# Safety regression: a leading FF is never stripped unless the candidate is
# known, has the correct length, and passes checksum.
invalid_leading_ff = [0xff] + list(real_wmr88_clock)
invalid_leading_ff[-2] ^= 0x01
driver_invalid_ff = make_driver()
assert driver_invalid_ff._process_packet_buffer(invalid_leading_ff) is None
assert driver_invalid_ff.stats['parser_leading_ff_recoveries'] == 0
assert driver_invalid_ff.stats['checksum_errors'] == 1

# Regression: real WMR88 wind frame observed on 2026-08-07.
# When the USB generator starts at 00 48 ... without a preceding delimiter,
# that first fragment is not trustworthy and must be discarded in full. The
# old synchroniser dropped only the 00, leaving a checksum-valid 48 0c ...
# fragment that was later reported as unknown packet type 0x0c.
real_wmr88_wind = [0x00, 0x48, 0x0c, 0x0c, 0x13, 0x30, 0x01, 0x00,
                   0x20, 0xc4, 0x00]
assert sum(real_wmr88_wind[:-2]) == ((real_wmr88_wind[-1] << 8) + real_wmr88_wind[-2])
record = driver._wind_packet(real_wmr88_wind)
assert record['wind_dir'] == 270.0
assert abs(record['wind_speed'] - 1.9) < 1e-9
assert abs(record['wind_gust'] - 1.9) < 1e-9

# Start in the middle of a frame (no initial FF FF). Only the complete frame
# after the first real delimiter must be emitted.
partial_start_stream = (real_wmr88_wind + [0xff, 0xff] +
                        samples[0x47] + [0xff, 0xff])
driver_partial = make_driver()
driver_partial._genBytes_raw = lambda: iter(partial_start_stream)
assert list(driver_partial.genPackets()) == [samples[0x47]]
assert driver_partial.stats['packets_unknown'] == 0

# The same wind frame is accepted normally when preceded by a real delimiter.
framed_wind_stream = ([0xff, 0xff] + real_wmr88_wind + [0xff, 0xff])
driver_framed = make_driver()
driver_framed._genBytes_raw = lambda: iter(framed_wind_stream)
assert list(driver_framed.genPackets()) == [real_wmr88_wind]

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

# Regression gp4: isolated USB timeout remains informational and healthy.
# The real WMR88 trace showed many single 15-second timeouts followed by a
# normal report a few seconds later. These must not mark the driver degraded.
handle = FakeHandle([
    [1, 0x10, 0, 0, 0, 0, 0, 0],
    TimeoutUSBError('Operation timed out', 110),
    [1, 0x11, 0, 0, 0, 0, 0, 0],
])
device = FakeDevice([handle])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR88', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0,
                      command_delay=0)
trace = CapturingTrace()
instance._developer_trace = trace
gen = instance._genBytes_raw()
assert next(gen) == 0x10
assert instance._health_state == 'healthy'
assert next(gen) == 0x11
assert instance._health_state == 'healthy'
timeout_events = [e for e in trace.events if e.get('event') == 'usb_read_timeout']
recovered_events = [e for e in trace.events if e.get('event') == 'usb_read_recovered']
assert len(timeout_events) == 1
assert timeout_events[0]['severity'] == 'info'
assert timeout_events[0]['classification'] == 'poll_timeout_no_data'
assert timeout_events[0]['timeout_consecutive'] == 1
assert timeout_events[0]['health_state'] == 'healthy'
assert len(recovered_events) == 1
assert recovered_events[0]['recovered_timeouts'] == 1
assert recovered_events[0]['health_state'] == 'healthy'
assert instance.stats['usb_timeout_episodes'] == 1
assert instance.stats['usb_timeout_recoveries'] == 1
assert instance.stats['usb_timeout_warning_episodes'] == 0
assert instance.stats['usb_timeout_max_consecutive'] == 1
assert not any(
    e.get('event') == 'health_state_change' and e.get('new_state') == 'degraded'
    for e in trace.events
)
instance.closePort()

# Regression gp4: health changes only when the warning threshold is reached,
# then returns to healthy with one explicit usb_read_recovered event.
handle = FakeHandle([
    [1, 0x20, 0, 0, 0, 0, 0, 0],
    TimeoutUSBError('Operation timed out', 110),
    TimeoutUSBError('Operation timed out', 110),
    [1, 0x21, 0, 0, 0, 0, 0, 0],
])
device = FakeDevice([handle])
usb.busses = lambda: [FakeBus(device)]
instance = mod.WMR100(model='WMR88', developer_trace=False,
                      stats_log_interval=0, wait_before_retry=0,
                      command_delay=0, timeout_warning_threshold=2,
                      timeout_reinit_threshold=0,
                      timeout_recovery_threshold=20)
trace = CapturingTrace()
instance._developer_trace = trace
gen = instance._genBytes_raw()
assert next(gen) == 0x20
assert next(gen) == 0x21
timeout_events = [e for e in trace.events if e.get('event') == 'usb_read_timeout']
assert [e['severity'] for e in timeout_events] == ['info', 'warning']
assert timeout_events[1]['classification'] == 'timeout_threshold_reached'
assert timeout_events[1]['timeout_consecutive'] == 2
health_changes = [
    (e.get('previous_state'), e.get('new_state'), e.get('reason'))
    for e in trace.events if e.get('event') == 'health_state_change'
]
assert ('healthy', 'warning', 'usb_timeout_threshold_reached') in health_changes
assert ('warning', 'healthy', 'usb_read_recovered') in health_changes
recovered_events = [e for e in trace.events if e.get('event') == 'usb_read_recovered']
assert len(recovered_events) == 1
assert recovered_events[0]['recovered_timeouts'] == 2
assert instance.stats['usb_timeout_warning_episodes'] == 1
assert instance.stats['usb_timeout_max_consecutive'] == 2
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
