# Configuration reference

## Model selection

Use `station_type = WMR100` and `driver = user.wmr100` for every console handled by this extension. Set `model` to the physical console:

- `WMR88` or `WMR88A`;
- `WMR100` or `WMR100N`;
- `WMR180` or `WMR180A`;
- `WMRS200`.

## WMR88 profile defaults

When `model` resolves to WMR88/WMR88A, the driver defaults to:

```ini
send_data_request = true
timeout_warning_threshold = 8
timeout_reinit_threshold = 12
timeout_recovery_threshold = 20
max_remote_channels = 3
```

Any explicitly configured value overrides the model profile.

## Recovery thresholds

Thresholds count consecutive USB read timeouts, not missing individual RF sensors.

- `timeout_warning_threshold`: health changes to `warning`; lower timeout counts remain informational and do not change health.
- `timeout_reinit_threshold`: initialization commands are resent without closing the USB handle.
- `timeout_recovery_threshold`: the interface is released, rediscovered, reopened, reclaimed and initialized.
- `recovery_max_tries`: failed complete recovery cycles allowed before `RetriesExceeded`.

Set `timeout_reinit_threshold = 0` to disable command-only reinitialisation.

## Packet validation

`strict_packet_lengths = true` rejects known packet types with an unexpected length even when their additive checksum is valid.

`max_packet_length = 64` bounds the parser buffer. A larger buffer is not expected for the known protocol.

## Trace controls

- `developer_trace`: enable JSONL diagnostics.
- `developer_trace_path`: primary destination.
- `developer_trace_max_bytes`: rotation size of each file.
- `developer_trace_backup_count`: number of rotated files retained.
- `developer_trace_raw_reports`: trace every 8-byte USB report; high volume.
- `developer_trace_packets`: trace complete protocol packets and LOOP output.
- `stats_log_interval`: periodic statistics interval in seconds; `0` disables periodic summaries.

Trace failures never intentionally stop weather acquisition.

## Sensor map

The extension retains the upstream WMR100 default map. Remote channel 1 is outside temperature/humidity; channels 2 and 3 map to `extraTemp1/extraHumid1` and `extraTemp2/extraHumid2`.

Diagnostic fields decoded by the driver are not archived automatically unless added to the sensor map and database schema.
