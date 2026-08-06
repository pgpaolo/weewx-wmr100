#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    Hardening and developer diagnostics:
#    Copyright (c) 2026 GP
#
#    See the WeeWX LICENSE.txt file for your full rights.
#
"""Robust WeeWX driver for Oregon Scientific WMR100-protocol stations.

Supported protocol family includes WMR100/WMR100N, WMR88/WMR88A,
WMR180/WMR180A and WMRS200 when they expose the WMR100 low-speed USB HID
interface. The WMR200 uses a different protocol and driver.

Important: sharing the same Oregon Scientific RF sensors does not guarantee
that a console uses the same computer interface. For example, WMR89-family
consoles use compatible protocol-3 RF sensors, but their USB interface is not
the WMR100 HID interface handled by this module.

The wind sensor reports wind speed, direction and gust, but not gust direction.
The station emits partial LOOP packets: each packet contains only one sensor
family. WeeWX combines these observations during archive processing.

This hardened version preserves the meteorological output and sensor mapping of
the upstream WeeWX 3.5.0 driver, while adding:

* bounded packet buffering and stream resynchronisation;
* checksum and packet-length validation;
* robust USB report validation;
* timeout classification and automatic USB reopen/reinitialisation;
* model-aware WMR88/WMR180 live-data request command;
* command-only reinitialisation before a full USB reopen;
* rotating JSONL developer trace;
* health/statistics counters and rate-limited diagnostics;
* safe, idempotent USB shutdown.

Protocol references:
  https://github.com/ejeklint/WLoggerDaemon/blob/master/Station_protocol.md
  https://wxtools.sourceforge.io/doc/wmr180.html
"""

import errno
import json
import logging
import logging.handlers
import os
import threading
import time
from datetime import datetime, timezone

import usb

import weewx.drivers
import weewx.wxformulas
import weeutil.weeutil

log = logging.getLogger(__name__)

DRIVER_NAME = 'WMR100'
DRIVER_VERSION = '3.5.2-gp2'

_INIT_COMMAND = [0x20, 0x00, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]
_DATA_REQUEST_COMMAND = [0x01, 0xD0, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]

SUPPORTED_MODELS = (
    'WMR100', 'WMR100N', 'WMR88', 'WMR88A',
    'WMR180', 'WMR180A', 'WMRS200'
)

_MODEL_ALIASES = {
    'WMR88/A': 'WMR88A',
    'WMR-88': 'WMR88',
    'WMR-88A': 'WMR88A',
    'WMR-100': 'WMR100',
    'WMR-100N': 'WMR100N',
    'WMR-180': 'WMR180',
    'WMR-180A': 'WMR180A',
    'WMRS-200': 'WMRS200',
}

# WMR88/WMR88A and WMR180/WMR180A are known to use the same 0x0fde:0xca01
# low-speed HID protocol, but field experience shows that they benefit from
# sending the live-data request and from allowing several minutes of RF silence
# before a full USB reopen. The WMR88 outdoor thermo-hygrometer can transmit at
# intervals of roughly 102 seconds, so a 90-second recovery watchdog is too
# aggressive for this model.
_MODEL_PROFILES = {
    'WMR88': {
        'name': 'wmr88',
        'send_data_request': True,
        'timeout_warning_threshold': 8,
        'timeout_reinit_threshold': 12,
        'timeout_recovery_threshold': 20,
        'max_remote_channels': 3,
    },
    'WMR88A': {
        'name': 'wmr88a',
        'send_data_request': True,
        'timeout_warning_threshold': 8,
        'timeout_reinit_threshold': 12,
        'timeout_recovery_threshold': 20,
        'max_remote_channels': 3,
    },
    'WMR180': {
        'name': 'wmr180',
        'send_data_request': True,
        'timeout_warning_threshold': 8,
        'timeout_reinit_threshold': 12,
        'timeout_recovery_threshold': 20,
        'max_remote_channels': 3,
    },
    'WMR180A': {
        'name': 'wmr180a',
        'send_data_request': True,
        'timeout_warning_threshold': 8,
        'timeout_reinit_threshold': 12,
        'timeout_recovery_threshold': 20,
        'max_remote_channels': 3,
    },
}

_DEFAULT_PROFILE = {
    'name': 'wmr100',
    'send_data_request': False,
    'timeout_warning_threshold': 4,
    'timeout_reinit_threshold': 0,
    'timeout_recovery_threshold': 6,
    'max_remote_channels': 8,
}


def _normalise_model(value):
    model = str(value or 'WMR100').strip().upper().replace(' ', '')
    return _MODEL_ALIASES.get(model, model)


def _config_or_profile(stn_dict, key, profile):
    return stn_dict[key] if key in stn_dict else profile[key]

_TIMEOUT_ERRNOS = {60, 110}
if hasattr(errno, 'ETIMEDOUT'):
    _TIMEOUT_ERRNOS.add(errno.ETIMEDOUT)


def loader(config_dict, engine):  # @UnusedVariable
    return WMR100(**config_dict[DRIVER_NAME])


def confeditor_loader():
    return WMR100ConfEditor()


def _to_bool(value, default=False):
    """Convert WeeWX/configobj values to bool without relying on configobj helpers."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ('1', 'true', 'yes', 'y', 'on', 'enable', 'enabled'):
        return True
    if text in ('0', 'false', 'no', 'n', 'off', 'disable', 'disabled'):
        return False
    return default


def _to_int(value, default):
    """Accept decimal integers and strings such as 0x81."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    return int(str(value).strip(), 0)


def _utc_now_string():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _hex_bytes(values):
    try:
        return ' '.join('%02x' % (int(value) & 0xFF) for value in values)
    except Exception:
        return repr(values)


def _exception_errno(exc):
    value = getattr(exc, 'errno', None)
    if isinstance(value, int):
        return value
    for item in getattr(exc, 'args', ()):
        if isinstance(item, int):
            return item
    return None


def _is_timeout(exc):
    err_no = _exception_errno(exc)
    if err_no in _TIMEOUT_ERRNOS:
        return True
    text = str(exc).strip().lower()
    return 'timed out' in text or 'timeout' in text or 'connection timed out' in text


def _is_spurious_no_error(exc):
    """Handle the historical libusb/PyUSB 0.4 USBError('No error') condition."""
    text = str(exc).strip().lower()
    return text in ('no error', "('no error',)") or getattr(exc, 'args', ()) == ('No error',)


def _should_log_count(count, interval=10):
    """Log the first occurrence, then every *interval* occurrences."""
    return count == 1 or (interval > 0 and count % interval == 0)


class _JsonLineTrace:
    """Small rotating JSONL trace writer that never becomes a driver dependency."""

    def __init__(self, enabled, path, max_bytes, backup_count):
        self.enabled = False
        self._logger = None
        self._handler = None
        if not enabled:
            return

        try:
            directory = os.path.dirname(os.path.abspath(path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            logger_name = '%s.developer_trace.%x' % (__name__, id(self))
            trace_logger = logging.getLogger(logger_name)
            trace_logger.setLevel(logging.INFO)
            trace_logger.propagate = False
            handler = logging.handlers.RotatingFileHandler(
                path,
                maxBytes=max(0, int(max_bytes)),
                backupCount=max(0, int(backup_count)),
                encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            trace_logger.addHandler(handler)
            self._logger = trace_logger
            self._handler = handler
            self.enabled = True
        except Exception as e:
            log.error('Unable to enable WMR100 developer trace at %s: %s', path, e)

    def write(self, payload):
        if not self.enabled:
            return
        try:
            self._logger.info(json.dumps(payload, sort_keys=True,
                                         separators=(',', ':'), default=str))
        except Exception as e:
            # Never let diagnostics stop weather acquisition.
            log.error('Unable to write WMR100 developer trace: %s', e)

    def close(self):
        if self._handler is None:
            return
        try:
            self._handler.flush()
            self._handler.close()
            if self._logger is not None:
                self._logger.removeHandler(self._handler)
        except Exception:
            pass
        finally:
            self._handler = None
            self._logger = None
            self.enabled = False


class WMR100(weewx.drivers.AbstractDevice):
    """Hardened driver for WMR100-protocol USB HID weather stations."""

    DEFAULT_MAP = {
        'pressure': 'pressure',
        'windSpeed': 'wind_speed',
        'windDir': 'wind_dir',
        'windGust': 'wind_gust',
        'windBatteryStatus': 'battery_status_wind',
        'inTemp': 'temperature_0',
        'outTemp': 'temperature_1',
        'extraTemp1': 'temperature_2',
        'extraTemp2': 'temperature_3',
        'extraTemp3': 'temperature_4',
        'extraTemp4': 'temperature_5',
        'extraTemp5': 'temperature_6',
        'extraTemp6': 'temperature_7',
        'extraTemp7': 'temperature_8',
        'inHumidity': 'humidity_0',
        'outHumidity': 'humidity_1',
        'extraHumid1': 'humidity_2',
        'extraHumid2': 'humidity_3',
        'extraHumid3': 'humidity_4',
        'extraHumid4': 'humidity_5',
        'extraHumid5': 'humidity_6',
        'extraHumid6': 'humidity_7',
        'extraHumid7': 'humidity_8',
        'inTempBatteryStatus': 'battery_status_0',
        'outTempBatteryStatus': 'battery_status_1',
        'extraBatteryStatus1': 'battery_status_2',
        'extraBatteryStatus2': 'battery_status_3',
        'extraBatteryStatus3': 'battery_status_4',
        'extraBatteryStatus4': 'battery_status_5',
        'extraBatteryStatus5': 'battery_status_6',
        'extraBatteryStatus6': 'battery_status_7',
        'extraBatteryStatus7': 'battery_status_8',
        'rain': 'rain',
        'rainTotal': 'rain_total',
        'rainRate': 'rain_rate',
        'hourRain': 'rain_hour',
        'rain24': 'rain_24',
        'rainBatteryStatus': 'battery_status_rain',
        'UV': 'uv',
        'uvBatteryStatus': 'battery_status_uv'
    }

    # Exact lengths include the two checksum bytes. The protocol checksum is
    # deliberately weak, so a valid checksum is not sufficient by itself.
    EXPECTED_PACKET_LENGTHS = {
        0x41: 17,  # rain
        0x42: 12,  # temperature and humidity
        0x46: 8,   # pressure
        0x47: 6,   # UV
        0x48: 11,  # wind
        0x60: 12,  # clock
    }

    # THWR800 temperature-only support is present upstream, but its exact frame
    # size is not documented in the principal protocol reference. Enforce only
    # the minimum required by the decoder and checksum.
    MIN_PACKET_LENGTHS = {
        0x44: 7,
    }

    PACKET_NAMES = {
        0x41: 'rain',
        0x42: 'temperature_humidity',
        0x44: 'temperature_only',
        0x46: 'pressure',
        0x47: 'uv',
        0x48: 'wind',
        0x60: 'clock',
    }

    def __init__(self, **stn_dict):
        log.info('WMR100 driver version is %s', DRIVER_VERSION)

        self.model = _normalise_model(stn_dict.get('model', 'WMR100'))
        self.model_profile = dict(_DEFAULT_PROFILE)
        self.model_profile.update(_MODEL_PROFILES.get(self.model, {}))
        if self.model not in SUPPORTED_MODELS:
            log.warning('Unrecognised WMR100-protocol model %s; using generic defaults',
                        self.model)

        self.record_generation = stn_dict.get('record_generation', 'software')
        self.timeout = float(stn_dict.get('timeout', 15.0))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 5.0))
        self.max_tries = max(1, _to_int(stn_dict.get('max_tries', 3), 3))
        self.recovery_max_tries = max(
            1, _to_int(stn_dict.get('recovery_max_tries', 3), 3))
        self.timeout_warning_threshold = max(
            1, _to_int(_config_or_profile(
                stn_dict, 'timeout_warning_threshold', self.model_profile),
                self.model_profile['timeout_warning_threshold']))
        self.timeout_reinit_threshold = max(
            0, _to_int(_config_or_profile(
                stn_dict, 'timeout_reinit_threshold', self.model_profile),
                self.model_profile['timeout_reinit_threshold']))
        self.timeout_recovery_threshold = max(
            0, _to_int(_config_or_profile(
                stn_dict, 'timeout_recovery_threshold', self.model_profile),
                self.model_profile['timeout_recovery_threshold']))
        if (self.timeout_reinit_threshold > 0 and
                self.timeout_recovery_threshold > 0 and
                self.timeout_reinit_threshold >= self.timeout_recovery_threshold):
            log.warning('timeout_reinit_threshold must be lower than '
                        'timeout_recovery_threshold; soft reinitialisation disabled')
            self.timeout_reinit_threshold = 0

        self.control_timeout_ms = max(
            100, _to_int(stn_dict.get('control_timeout_ms', 1000), 1000))
        self.command_delay = max(
            0.0, float(stn_dict.get('command_delay', 0.05)))
        self.send_data_request = _to_bool(
            _config_or_profile(stn_dict, 'send_data_request', self.model_profile),
            self.model_profile['send_data_request'])
        self.max_remote_channels = max(
            1, _to_int(stn_dict.get(
                'max_remote_channels', self.model_profile['max_remote_channels']),
                self.model_profile['max_remote_channels']))

        self.vendor_id = _to_int(stn_dict.get('vendor_id', '0x0fde'), 0x0FDE)
        self.product_id = _to_int(stn_dict.get('product_id', '0xca01'), 0xCA01)
        self.interface = _to_int(stn_dict.get('interface', 0), 0)
        self.IN_endpoint = _to_int(
            stn_dict.get('IN_endpoint', usb.ENDPOINT_IN + 1),
            usb.ENDPOINT_IN + 1)

        self.max_packet_length = max(
            16, _to_int(stn_dict.get('max_packet_length', 64), 64))
        self.strict_packet_lengths = _to_bool(
            stn_dict.get('strict_packet_lengths', True), True)
        self.stats_log_interval = max(
            0.0, float(stn_dict.get('stats_log_interval', 3600.0)))

        self.developer_trace_raw_reports = _to_bool(
            stn_dict.get('developer_trace_raw_reports', False), False)
        self.developer_trace_packets = _to_bool(
            stn_dict.get('developer_trace_packets', False), False)
        trace_enabled = _to_bool(stn_dict.get('developer_trace', False), False)
        trace_path = stn_dict.get(
            'developer_trace_path',
            '/var/log/weewx/wmr100-developer-trace.jsonl')
        trace_max_bytes = _to_int(
            stn_dict.get('developer_trace_max_bytes', 5242880), 5242880)
        trace_backup_count = _to_int(
            stn_dict.get('developer_trace_backup_count', 5), 5)
        self._developer_trace = _JsonLineTrace(
            trace_enabled, trace_path, trace_max_bytes, trace_backup_count)

        self.sensor_map = dict(self.DEFAULT_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        log.info('WMR100 sensor map is %s', self.sensor_map)

        self.last_rain_total = None
        self.last_time = None
        self.devh = None
        self._closed = False
        self._health_state = 'starting'
        self._trace_sequence = 0
        self._last_success_utc = None
        self._last_success_monotonic = None
        self._next_stats_log = (time.monotonic() + self.stats_log_interval
                                if self.stats_log_interval > 0 else None)
        self.stats = {
            'usb_reports': 0,
            'usb_payload_bytes': 0,
            'usb_timeouts': 0,
            'usb_errors': 0,
            'usb_spurious_no_error': 0,
            'usb_malformed_reports': 0,
            'usb_soft_reinitialisations': 0,
            'usb_soft_reinitialisation_failures': 0,
            'usb_recovery_cycles': 0,
            'usb_recovery_attempts': 0,
            'usb_recovery_failures': 0,
            'packets_valid': 0,
            'packets_decoded': 0,
            'packets_unmapped': 0,
            'packets_unknown': 0,
            'packets_malformed': 0,
            'checksum_errors': 0,
            'length_errors': 0,
            'parser_resyncs': 0,
            'decoder_errors': 0,
        }

        self._trace_event(
            'driver_start',
            model=self.model,
            vendor_id='0x%04x' % self.vendor_id,
            product_id='0x%04x' % self.product_id,
            interface=self.interface,
            in_endpoint='0x%02x' % self.IN_endpoint,
            timeout_seconds=self.timeout,
            model_profile=self.model_profile['name'],
            send_data_request=self.send_data_request,
            timeout_warning_threshold=self.timeout_warning_threshold,
            timeout_reinit_threshold=self.timeout_reinit_threshold,
            timeout_recovery_threshold=self.timeout_recovery_threshold,
            max_remote_channels=self.max_remote_channels)
        self.openPort()

    @property
    def hardware_name(self):
        return self.model

    def _trace_event(self, event, **fields):
        if not self._developer_trace.enabled:
            return
        self._trace_sequence += 1
        payload = {
            'timestamp_utc': _utc_now_string(),
            'sequence': self._trace_sequence,
            'event': event,
            'driver': DRIVER_NAME,
            'driver_version': DRIVER_VERSION,
            'model': self.model,
            'thread': threading.current_thread().name,
            'health_state': self._health_state,
        }
        payload.update(fields)
        self._developer_trace.write(payload)

    def _set_health(self, state, reason=None):
        if state == self._health_state:
            return
        old_state = self._health_state
        self._health_state = state
        self._trace_event('health_state_change', previous_state=old_state,
                          new_state=state, reason=reason)

    def _stats_snapshot(self):
        snapshot = dict(self.stats)
        snapshot['health_state'] = self._health_state
        snapshot['last_success_utc'] = self._last_success_utc
        if self._last_success_monotonic is not None:
            snapshot['seconds_since_last_success'] = round(
                max(0.0, time.monotonic() - self._last_success_monotonic), 3)
        else:
            snapshot['seconds_since_last_success'] = None
        return snapshot

    def _maybe_log_stats(self):
        if self._next_stats_log is None or time.monotonic() < self._next_stats_log:
            return
        snapshot = self._stats_snapshot()
        log.info('%s health statistics: %s', self.model, snapshot)
        self._trace_event('health_statistics', statistics=snapshot)
        self._next_stats_log = time.monotonic() + self.stats_log_interval

    # =========================================================================
    # USB lifecycle and recovery
    # =========================================================================

    def _findDevice(self):
        """Find the configured vendor and product IDs on the USB bus."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.vendor_id and dev.idProduct == self.product_id:
                    return dev
        return None

    def _control_message(self, command, command_name):
        if self.devh is None:
            raise weewx.WeeWxIOError('USB device is not open')
        try:
            self.devh.controlMsg(
                usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                0x0000009,
                command,
                0x0000200,
                self.interface,
                self.control_timeout_ms)
            self._trace_event('usb_control_tx', direction='TX',
                              command=command_name, raw_hex=_hex_bytes(command))
        except usb.USBError as e:
            self._trace_event('usb_control_error', direction='TX',
                              command=command_name, error=str(e),
                              errno=_exception_errno(e),
                              raw_hex=_hex_bytes(command))
            raise weewx.WakeupError(e)

    def _initialise_station(self):
        """Kick-start the console after initial open or recovery."""
        self._control_message(_INIT_COMMAND, 'initialise')
        if self.send_data_request:
            if self.command_delay:
                time.sleep(self.command_delay)
            self._control_message(_DATA_REQUEST_COMMAND, 'request_live_data')

    def openPort(self):
        """Open, claim and initialise the configured USB interface."""
        if self.devh is not None:
            return

        self._trace_event('usb_open_attempt', direction='SYSTEM')
        dev = self._findDevice()
        if not dev:
            message = 'Unable to find USB device (0x%04x, 0x%04x)' % (
                self.vendor_id, self.product_id)
            log.error(message)
            self._trace_event('usb_device_not_found', direction='SYSTEM',
                              vendor_id='0x%04x' % self.vendor_id,
                              product_id='0x%04x' % self.product_id)
            raise weewx.WeeWxIOError(message)

        handle = None
        try:
            handle = dev.open()
            try:
                handle.detachKernelDriver(self.interface)
                self._trace_event('usb_kernel_driver_detached',
                                  direction='SYSTEM', interface=self.interface)
            except usb.USBError:
                # Common when no kernel driver is attached. claimInterface()
                # remains the authoritative test.
                pass

            handle.claimInterface(self.interface)
            self.devh = handle
            self._initialise_station()
            self._set_health('ready', 'usb_opened')
            self._trace_event('usb_open_success', direction='SYSTEM',
                              interface=self.interface,
                              in_endpoint='0x%02x' % self.IN_endpoint)
        except Exception as e:
            if self.devh is handle:
                self.devh = None
            if handle is not None:
                try:
                    handle.releaseInterface()
                except Exception:
                    pass
            self._trace_event('usb_open_failure', direction='SYSTEM',
                              error=str(e), errno=_exception_errno(e))
            if isinstance(e, (weewx.WeeWxIOError, weewx.WakeupError)):
                raise
            if isinstance(e, usb.USBError):
                log.error('Unable to claim or initialise USB interface: %s', e)
                raise weewx.WeeWxIOError(e)
            raise

    def _close_usb_handle(self, reattach_kernel=False):
        handle, self.devh = self.devh, None
        if handle is None:
            return

        try:
            handle.releaseInterface()
        except Exception as e:
            self._trace_event('usb_release_warning', direction='SYSTEM', error=str(e))

        if reattach_kernel:
            attach = getattr(handle, 'attachKernelDriver', None)
            if callable(attach):
                try:
                    attach(self.interface)
                except Exception:
                    pass

        self._trace_event('usb_closed', direction='SYSTEM')

    def closePort(self):
        """Close the USB interface. Safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        self._trace_event('driver_stop', statistics=self._stats_snapshot())
        self._close_usb_handle(reattach_kernel=True)
        self._set_health('closed', 'driver_shutdown')
        self._developer_trace.close()

    def _soft_reinitialise_station(self, reason, error=None):
        """Reissue station commands without closing the USB interface.

        WMR88/WMR88A and WMR180-family consoles may remain enumerated while
        their live stream stops. A command-only restart is less disruptive than
        immediately releasing and reopening the HID interface.
        """
        self.stats['usb_soft_reinitialisations'] += 1
        occurrence = self.stats['usb_soft_reinitialisations']
        self._set_health('recovering', reason)
        self._trace_event(
            'usb_soft_reinitialisation_start', direction='SYSTEM',
            reason=reason, occurrence=occurrence,
            error=str(error) if error is not None else None,
            errno=_exception_errno(error) if error is not None else None)
        try:
            self._initialise_station()
        except Exception as e:
            self.stats['usb_soft_reinitialisation_failures'] += 1
            self._trace_event(
                'usb_soft_reinitialisation_failed', direction='SYSTEM',
                reason=reason, occurrence=occurrence, error=str(e),
                errno=_exception_errno(e))
            log.warning('%s command-only reinitialisation failed: %s',
                        self.model, e)
            self._recover_usb('soft_reinitialisation_failed', e)
            return

        self._set_health('ready', 'commands_reissued')
        self._trace_event(
            'usb_soft_reinitialisation_success', direction='SYSTEM',
            reason=reason, occurrence=occurrence,
            send_data_request=self.send_data_request)
        log.warning('%s USB commands reissued after prolonged data silence',
                    self.model)

    def _recover_usb(self, reason, error=None):
        """Close, rediscover, reopen and reinitialise the USB station."""
        self.stats['usb_recovery_cycles'] += 1
        cycle = self.stats['usb_recovery_cycles']
        self._set_health('recovering', reason)
        self._trace_event('usb_recovery_start', direction='SYSTEM',
                          reason=reason, recovery_cycle=cycle,
                          error=str(error) if error is not None else None,
                          errno=_exception_errno(error) if error is not None else None)
        self._close_usb_handle(reattach_kernel=False)

        last_error = error
        for attempt in range(1, self.recovery_max_tries + 1):
            self.stats['usb_recovery_attempts'] += 1
            if attempt > 1 and self.wait_before_retry > 0:
                time.sleep(self.wait_before_retry)
            try:
                self.openPort()
                self._trace_event('usb_recovery_success', direction='SYSTEM',
                                  reason=reason, recovery_cycle=cycle,
                                  recovery_attempt=attempt)
                log.warning('%s USB recovery succeeded after %s (cycle %d, attempt %d)',
                            self.model, reason, cycle, attempt)
                return
            except Exception as e:
                last_error = e
                self.stats['usb_recovery_failures'] += 1
                self._trace_event('usb_recovery_attempt_failed', direction='SYSTEM',
                                  reason=reason, recovery_cycle=cycle,
                                  recovery_attempt=attempt, error=str(e),
                                  errno=_exception_errno(e))

        self._set_health('failed', 'usb_recovery_exhausted')
        message = ('%s USB recovery failed after %d attempts: %s' %
                   (self.model, self.recovery_max_tries, last_error))
        log.error(message)
        self._trace_event('usb_recovery_exhausted', direction='SYSTEM',
                          reason=reason, recovery_cycle=cycle,
                          error=str(last_error))
        raise weewx.RetriesExceeded(message)

    # =========================================================================
    # LOOP generation and packet framing
    # =========================================================================

    def genLoopPackets(self):
        """Continuously yield WeeWX partial LOOP packets."""
        for packet in self.genPackets():
            packet_type = packet[1]
            decoder = self._dispatch_dict.get(packet_type)
            if decoder is None:
                self.stats['packets_unknown'] += 1
                count = self.stats['packets_unknown']
                if _should_log_count(count, 25):
                    log.warning('Unknown WMR100 packet type 0x%02x, length %d: %s',
                                packet_type, len(packet), _hex_bytes(packet))
                self._trace_event('unknown_packet', direction='RX',
                                  packet_type='0x%02x' % packet_type,
                                  packet_length=len(packet), raw_hex=_hex_bytes(packet),
                                  occurrence=count)
                continue

            try:
                raw_record = decoder(self, packet)
            except Exception as e:
                self.stats['decoder_errors'] += 1
                log.error('Unable to decode WMR100 packet type 0x%02x: %s',
                          packet_type, e)
                self._trace_event('packet_decode_error', direction='RX',
                                  packet_type='0x%02x' % packet_type,
                                  packet_name=self.PACKET_NAMES.get(packet_type),
                                  packet_length=len(packet), raw_hex=_hex_bytes(packet),
                                  error=str(e))
                continue

            if not raw_record:
                # Clock packets intentionally return None.
                continue

            record = {}
            for target_field, source_field in self.sensor_map.items():
                if source_field in raw_record:
                    record[target_field] = raw_record[source_field]

            if not record:
                self.stats['packets_unmapped'] += 1
                self._trace_event('packet_unmapped', direction='RX',
                                  packet_type='0x%02x' % packet_type,
                                  packet_name=self.PACKET_NAMES.get(packet_type),
                                  raw_fields=sorted(raw_record.keys()))
                continue

            record['dateTime'] = raw_record['dateTime']
            record['usUnits'] = raw_record['usUnits']
            self.stats['packets_decoded'] += 1
            if self.developer_trace_packets:
                self._trace_event('loop_packet', direction='OUTPUT',
                                  packet_type='0x%02x' % packet_type,
                                  packet_name=self.PACKET_NAMES.get(packet_type),
                                  fields=record)
            yield record

    def _validate_packet_length(self, packet_type, packet_length):
        expected = self.EXPECTED_PACKET_LENGTHS.get(packet_type)
        if expected is not None and packet_length != expected:
            return False, 'expected %d bytes, received %d' % (expected, packet_length)
        minimum = self.MIN_PACKET_LENGTHS.get(packet_type)
        if minimum is not None and packet_length < minimum:
            return False, 'minimum %d bytes, received %d' % (minimum, packet_length)
        return True, None

    def _process_packet_buffer(self, buff):
        if len(buff) < 4:
            self.stats['packets_malformed'] += 1
            self._trace_event('packet_too_short', direction='RX',
                              packet_length=len(buff), raw_hex=_hex_bytes(buff))
            return None

        computed_checksum = sum(buff[:-2]) & 0xFFFF
        actual_checksum = ((buff[-1] & 0xFF) << 8) + (buff[-2] & 0xFF)
        if computed_checksum != actual_checksum:
            self.stats['checksum_errors'] += 1
            count = self.stats['checksum_errors']
            if _should_log_count(count, 10):
                log.warning('Bad WMR100 checksum: calculated 0x%04x, received 0x%04x, '
                            'length %d, packet %s', computed_checksum,
                            actual_checksum, len(buff), _hex_bytes(buff))
            self._trace_event('packet_checksum_error', direction='RX',
                              packet_type=('0x%02x' % buff[1] if len(buff) > 1 else None),
                              packet_length=len(buff),
                              checksum_calculated=computed_checksum,
                              checksum_received=actual_checksum,
                              raw_hex=_hex_bytes(buff), occurrence=count)
            return None

        packet_type = buff[1]
        valid_length, reason = self._validate_packet_length(packet_type, len(buff))
        if not valid_length:
            self.stats['length_errors'] += 1
            count = self.stats['length_errors']
            if _should_log_count(count, 10):
                log.warning('Invalid WMR100 packet length for type 0x%02x: %s; packet %s',
                            packet_type, reason, _hex_bytes(buff))
            self._trace_event('packet_length_error', direction='RX',
                              packet_type='0x%02x' % packet_type,
                              packet_name=self.PACKET_NAMES.get(packet_type),
                              packet_length=len(buff), reason=reason,
                              raw_hex=_hex_bytes(buff), occurrence=count)
            if self.strict_packet_lengths:
                return None

        self.stats['packets_valid'] += 1
        if self.developer_trace_packets:
            self._trace_event('packet_valid', direction='RX',
                              packet_type='0x%02x' % packet_type,
                              packet_name=self.PACKET_NAMES.get(packet_type),
                              packet_length=len(buff), raw_hex=_hex_bytes(buff))
        return buff

    def genPackets(self):
        """Generate checksum- and length-validated station measurement packets."""
        gen_bytes = weeutil.weeutil.GenWithPeek(self._genBytes_raw())

        # Discard a possible partial frame until the first FF FF separator.
        try:
            for ibyte in gen_bytes:
                if gen_bytes.peek() != 0xFF:
                    break
        except StopIteration:
            return

        buff = []
        discarding_oversize = False

        for ibyte in gen_bytes:
            try:
                next_byte = gen_bytes.peek()
            except StopIteration:
                return

            if ibyte == 0xFF and next_byte == 0xFF:
                # Consume the second separator byte.
                try:
                    next(gen_bytes)
                except StopIteration:
                    return

                if not discarding_oversize:
                    packet = self._process_packet_buffer(buff)
                    if packet is not None:
                        yield packet
                buff = []
                discarding_oversize = False
                continue

            if discarding_oversize:
                continue

            buff.append(ibyte)
            if len(buff) > self.max_packet_length:
                self.stats['parser_resyncs'] += 1
                count = self.stats['parser_resyncs']
                log.warning('WMR100 packet exceeded %d bytes; discarding until next FF FF '
                            'separator', self.max_packet_length)
                self._trace_event('parser_buffer_overflow', direction='RX',
                                  max_packet_length=self.max_packet_length,
                                  buffered_length=len(buff),
                                  raw_hex=_hex_bytes(buff), occurrence=count)
                buff = []
                discarding_oversize = True

    def _genBytes_raw(self):
        """Generate payload bytes extracted from validated eight-byte USB reports."""
        consecutive_timeouts = 0
        consecutive_errors = 0

        while True:
            if self.devh is None:
                self._recover_usb('missing_usb_handle')

            try:
                report = self.devh.interruptRead(
                    self.IN_endpoint, 8, int(self.timeout * 1000))
            except usb.USBError as e:
                if _is_spurious_no_error(e):
                    self.stats['usb_spurious_no_error'] += 1
                    self._trace_event('usb_spurious_no_error', direction='RX',
                                      error=str(e),
                                      occurrence=self.stats['usb_spurious_no_error'])
                    continue

                if _is_timeout(e):
                    self.stats['usb_timeouts'] += 1
                    consecutive_timeouts += 1
                    consecutive_errors = 0
                    self._set_health('degraded', 'usb_read_timeout')
                    important_thresholds = {
                        self.timeout_warning_threshold,
                        self.timeout_reinit_threshold,
                        self.timeout_recovery_threshold,
                    }
                    if consecutive_timeouts in important_thresholds:
                        log.warning('%s USB read timeout (%d consecutive, %d total)',
                                    self.model, consecutive_timeouts,
                                    self.stats['usb_timeouts'])
                    else:
                        log.debug('%s USB read timeout (%d consecutive, %d total)',
                                  self.model, consecutive_timeouts,
                                  self.stats['usb_timeouts'])
                    self._trace_event(
                        'usb_read_timeout', direction='RX', error=str(e),
                        errno=_exception_errno(e),
                        timeout_seconds=self.timeout,
                        timeout_consecutive=consecutive_timeouts,
                        timeout_total=self.stats['usb_timeouts'],
                        last_success_utc=self._last_success_utc,
                        seconds_since_last_success=(
                            round(time.monotonic() - self._last_success_monotonic, 3)
                            if self._last_success_monotonic is not None else None))
                    if (self.timeout_reinit_threshold > 0 and
                            consecutive_timeouts == self.timeout_reinit_threshold):
                        self._soft_reinitialise_station(
                            'prolonged_usb_data_silence', e)
                    if (self.timeout_recovery_threshold > 0 and
                            consecutive_timeouts >= self.timeout_recovery_threshold):
                        self._recover_usb('consecutive_usb_timeouts', e)
                        consecutive_timeouts = 0
                    self._maybe_log_stats()
                    continue

                self.stats['usb_errors'] += 1
                consecutive_errors += 1
                consecutive_timeouts = 0
                self._set_health('degraded', 'usb_read_error')
                log.warning('WMR100 USB read error (%d/%d): %s',
                            consecutive_errors, self.max_tries, e)
                self._trace_event('usb_read_error', direction='RX', error=str(e),
                                  errno=_exception_errno(e),
                                  error_consecutive=consecutive_errors,
                                  error_total=self.stats['usb_errors'])
                if consecutive_errors >= self.max_tries:
                    self._recover_usb('consecutive_usb_errors', e)
                    consecutive_errors = 0
                elif self.wait_before_retry > 0:
                    time.sleep(self.wait_before_retry)
                self._maybe_log_stats()
                continue
            except Exception as e:
                self.stats['usb_errors'] += 1
                consecutive_errors += 1
                self._set_health('degraded', 'unexpected_usb_read_error')
                self._trace_event('usb_read_unexpected_error', direction='RX',
                                  error=str(e),
                                  error_consecutive=consecutive_errors)
                if consecutive_errors >= self.max_tries:
                    self._recover_usb('unexpected_usb_read_errors', e)
                    consecutive_errors = 0
                elif self.wait_before_retry > 0:
                    time.sleep(self.wait_before_retry)
                continue

            # Successful USB call. Validate the complete HID report before
            # trusting its count byte.
            try:
                report_length = len(report)
                payload_count = int(report[0])
            except Exception as e:
                report_length = None
                payload_count = None
                validation_error = 'unreadable report: %s' % e
            else:
                if report_length != 8:
                    validation_error = 'expected 8-byte report, received %d' % report_length
                elif payload_count < 0 or payload_count > 7:
                    validation_error = 'invalid payload count %d' % payload_count
                elif payload_count > report_length - 1:
                    validation_error = ('payload count %d exceeds report payload' %
                                        payload_count)
                else:
                    validation_error = None

            if validation_error is not None:
                self.stats['usb_malformed_reports'] += 1
                consecutive_errors += 1
                consecutive_timeouts = 0
                count = self.stats['usb_malformed_reports']
                if _should_log_count(count, 10):
                    log.warning('Malformed WMR100 USB report: %s; raw=%s',
                                validation_error, _hex_bytes(report))
                self._trace_event('usb_report_malformed', direction='RX',
                                  reason=validation_error,
                                  report_length=report_length,
                                  payload_count=payload_count,
                                  raw_hex=_hex_bytes(report), occurrence=count)
                if consecutive_errors >= self.max_tries:
                    self._recover_usb('malformed_usb_reports')
                    consecutive_errors = 0
                elif self.wait_before_retry > 0:
                    time.sleep(min(self.wait_before_retry, 1.0))
                continue

            consecutive_timeouts = 0
            consecutive_errors = 0
            self.stats['usb_reports'] += 1
            self.stats['usb_payload_bytes'] += payload_count

            if self.developer_trace_raw_reports:
                self._trace_event('usb_report', direction='RX',
                                  report_length=report_length,
                                  payload_count=payload_count,
                                  raw_hex=_hex_bytes(report))

            if payload_count > 0:
                self._last_success_utc = _utc_now_string()
                self._last_success_monotonic = time.monotonic()
                self._set_health('healthy', 'usb_payload_received')
                for value in report[1:payload_count + 1]:
                    yield int(value) & 0xFF

            self._maybe_log_stats()

    # =========================================================================
    # Packet decoders
    # =========================================================================

    @staticmethod
    def _battery_low_flag(packet):
        return (packet[0] & 0x40) >> 6

    def _rain_packet(self, packet):
        # The upstream driver intentionally uses hundredths of an inch. This
        # matches the observed 0.04-inch PCR800 bucket increment and is retained
        # for database compatibility.
        record = {
            'rain_rate': ((packet[3] << 8) + packet[2]) / 100.0,
            'rain_hour': ((packet[5] << 8) + packet[4]) / 100.0,
            'rain_24': ((packet[7] << 8) + packet[6]) / 100.0,
            'rain_total': ((packet[9] << 8) + packet[8]) / 100.0,
            # Preserve the original high-nibble output for compatibility.
            'battery_status_rain': packet[0] >> 4,
            # Extra raw diagnostic value; not mapped by default.
            'battery_low_rain': self._battery_low_flag(packet),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.US,
        }

        record['rain'] = weewx.wxformulas.calculate_rain(
            record['rain_total'], self.last_rain_total)
        if (self.last_rain_total is not None and
                record['rain_total'] < self.last_rain_total):
            self._trace_event('rain_counter_reset', direction='RX',
                              previous_total=self.last_rain_total,
                              current_total=record['rain_total'])
        self.last_rain_total = record['rain_total']
        return record

    def _temperature_packet(self, packet):
        record = {'dateTime': int(time.time() + 0.5),
                  'usUnits': weewx.METRIC}
        temperature = (((packet[4] & 0x7F) << 8) + packet[3]) / 10.0
        if packet[4] & 0x80:
            temperature = -temperature
        humidity = float(packet[5])
        channel = packet[2] & 0x0F
        if channel > self.max_remote_channels:
            self._trace_event('sensor_channel_outside_model_profile',
                              direction='RX', sensor='temperature_humidity',
                              channel=channel,
                              max_remote_channels=self.max_remote_channels)

        record['temperature_%d' % channel] = temperature
        record['humidity_%d' % channel] = humidity
        record['battery_status_%d' % channel] = self._battery_low_flag(packet)

        # Expose protocol metadata for optional custom mappings/diagnostics,
        # while leaving the standard WeeWX mapping unchanged.
        record['temperature_trend_%d' % channel] = packet[0] & 0x03
        record['humidity_trend_%d' % channel] = (packet[2] >> 4) & 0x03
        record['comfort_level_%d' % channel] = (packet[2] >> 6) & 0x03

        console_dewpoint = (((packet[7] & 0x7F) << 8) + packet[6]) / 10.0
        if packet[7] & 0x80:
            console_dewpoint = -console_dewpoint
        record['console_dewpoint_%d' % channel] = console_dewpoint

        if not 0.0 <= humidity <= 100.0:
            self._trace_event('sensor_value_suspicious', direction='RX',
                              sensor='temperature_humidity', channel=channel,
                              field='humidity', value=humidity)
        return record

    def _temperatureonly_packet(self, packet):
        record = {'dateTime': int(time.time() + 0.5),
                  'usUnits': weewx.METRIC}
        temperature = (((packet[4] & 0x7F) << 8) + packet[3]) / 10.0
        if packet[4] & 0x80:
            temperature = -temperature
        channel = packet[2] & 0x0F
        if channel > self.max_remote_channels:
            self._trace_event('sensor_channel_outside_model_profile',
                              direction='RX', sensor='temperature_only',
                              channel=channel,
                              max_remote_channels=self.max_remote_channels)
        record['temperature_%d' % channel] = temperature
        record['battery_status_%d' % channel] = self._battery_low_flag(packet)
        record['temperature_trend_%d' % channel] = packet[0] & 0x03
        return record

    def _pressure_packet(self, packet):
        station_pressure = float(((packet[3] & 0x0F) << 8) + packet[2])
        console_barometer = float(((packet[5] & 0x0F) << 8) + packet[4])
        record = {
            'pressure': station_pressure,
            # Not mapped by default because WeeWX calculates barometer using
            # station altitude, and WMRS200 consoles cannot always store it.
            'console_barometer': console_barometer,
            'forecast_code': packet[3] >> 4,
            'previous_forecast_code': packet[5] >> 4,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
        }
        if not 800.0 <= station_pressure <= 1100.0:
            self._trace_event('sensor_value_suspicious', direction='RX',
                              sensor='pressure', field='pressure',
                              value=station_pressure,
                              console_barometer=console_barometer,
                              raw_hex=_hex_bytes(packet))
        return record

    def _uv_packet(self, packet):
        uv_index = float(packet[3])
        record = {
            'uv': uv_index,
            'battery_status_uv': packet[0] >> 4,
            'battery_low_uv': self._battery_low_flag(packet),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
        }
        if uv_index > 25.0:
            self._trace_event('sensor_value_suspicious', direction='RX',
                              sensor='uv', field='uv', value=uv_index)
        return record

    def _wind_packet(self, packet):
        """Decode wind speed and gust in metres per second."""
        wind_speed = ((packet[6] << 4) + (packet[5] >> 4)) / 10.0
        wind_gust = (((packet[5] & 0x0F) << 8) + packet[4]) / 10.0
        record = {
            'wind_speed': wind_speed,
            'wind_gust': wind_gust,
            'wind_dir': (packet[2] & 0x0F) * 360.0 / 16.0,
            'battery_status_wind': packet[0] >> 4,
            'battery_low_wind': self._battery_low_flag(packet),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRICWX,
        }

        # Preserve upstream behaviour: a gust lower than average speed is an
        # inconsistent console value and is not emitted.
        if record['wind_gust'] < record['wind_speed']:
            self._trace_event('wind_gust_inconsistent', direction='RX',
                              wind_speed=record['wind_speed'],
                              wind_gust=record['wind_gust'])
            record['wind_gust'] = None
        return record

    def _clock_packet(self, packet):
        tt = (2000 + packet[8], packet[7], packet[6],
              packet[5], packet[4], 0, 0, 0, -1)
        try:
            self.last_time = time.mktime(tt)
        except (OverflowError, ValueError, OSError) as e:
            log.warning('Bad WMR100 clock packet ignored: %s', packet)
            self._trace_event('clock_packet_invalid', direction='RX',
                              error=str(e), raw_hex=_hex_bytes(packet))
        return None

    _dispatch_dict = {
        0x41: _rain_packet,
        0x42: _temperature_packet,
        0x44: _temperatureonly_packet,
        0x46: _pressure_packet,
        0x47: _uv_packet,
        0x48: _wind_packet,
        0x60: _clock_packet,
    }


class WMR100ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR100]
    # Oregon Scientific WMR100-protocol USB HID station.
    # Install this file as bin/user/wmr100.py and use user.wmr100.
    driver = user.wmr100

    # WMR88A uses the same USB protocol. Set WMR88A for the US model.
    model = WMR88

    # USB read/recovery
    timeout = 15
    wait_before_retry = 5
    max_tries = 3
    recovery_max_tries = 3
    # WMR88 wind packets are about 56 s apart and outdoor thermo/hygro
    # packets about 102 s apart. Avoid aggressive 60-90 s resets.
    timeout_warning_threshold = 8
    timeout_reinit_threshold = 12
    timeout_recovery_threshold = 20

    # Required/recommended for the WMR88/WMR88A live stream. The driver
    # automatically defaults this to true when model is WMR88 or WMR88A.
    send_data_request = true

    # Parser hardening
    strict_packet_lengths = true
    max_packet_length = 64

    # Optional rotating developer trace
    developer_trace = false
    developer_trace_path = /var/log/weewx/wmr100-developer-trace.jsonl
    developer_trace_max_bytes = 5242880
    developer_trace_backup_count = 5
    developer_trace_raw_reports = false
    developer_trace_packets = false
"""

    def modify_config(self, config_dict):
        print("""
Setting rainRate calculation to hardware.""")
        config_dict.setdefault('StdWXCalculate', {})
        config_dict['StdWXCalculate'].setdefault('Calculations', {})
        config_dict['StdWXCalculate']['Calculations']['rainRate'] = 'hardware'
