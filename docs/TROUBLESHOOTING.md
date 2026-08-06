# Troubleshooting

## Device not found

```bash
lsusb -d 0fde:ca01
```

If there is no output, check the cable, console power and USB port. The driver cannot recover a device that is not enumerated by the operating system.

## Permission denied or unable to claim interface

```bash
sudo ./install-udev-rule.sh
id weewx
```

Reconnect the USB cable, then verify the device node group and mode. Stop any other process that may have claimed the same console.

## Driver starts but no live data arrives

For WMR88/WMR88A verify:

```ini
model = WMR88
send_data_request = true
```

Check the JSONL trace for transmitted control commands and consecutive timeouts.

## Frequent USB recovery

Do not tune recovery from an individual sensor's RF interval. USB timeouts mean no payload bytes from the console at all. For WMR88 begin with the model defaults and inspect the trace before reducing thresholds.

## Missing values in a LOOP packet

This protocol emits separate partial packets for wind, temperature/humidity, pressure, rain and UV. Missing fields in one LOOP are expected. Use a 300-second software archive interval for a more complete archive accumulator.

## Trace file is not created

Create the directory and file for the WeeWX service account:

```bash
sudo install -d -o weewx -g weewx -m 0750 /var/log/weewx
sudo touch /var/log/weewx/wmr100-developer-trace.jsonl
sudo chown weewx:weewx /var/log/weewx/wmr100-developer-trace.jsonl
sudo chmod 0640 /var/log/weewx/wmr100-developer-trace.jsonl
```

The driver should continue acquiring data even when the optional trace cannot be opened.
