# PulsePal ESPHome

ESPHome external component for the PulsePal nRF52840 firmware.

PulsePal uses the Nordic UART Service (NUS) over BLE and is intentionally
independent of the proprietary PowerPal protocol.

## Usage

```yaml
external_components:
  - source: github://YOUR-USER/pulsepal-esphome@main
    components: [pulsepal]

ble_client:
  - mac_address: C8:A3:65:A9:EF:BE
    id: pulsepal_ble

time:
  - platform: homeassistant
    id: ha_time

pulsepal:
  ble_client_id: pulsepal_ble
  pulses_per_kwh: 3200
  time_id: ha_time   # without this, every record is timestamped epoch=0

  power:
    name: "Meter Power"

  total_energy:
    name: "Meter Total Energy"

  pulse_count:
    name: "Meter Pulse Count"

  battery:
    name: "Meter Battery"

  battery_voltage:
    name: "Meter Battery Voltage"

  average_interval:
    name: "PulsePal Average Interval"

  report_interval:
    name: "PulsePal Report Interval"

  live_power:
    name: "PulsePal Live Power"
```

The component automatically subscribes to the PulsePal NUS TX characteristic,
parses STATUS/INTERVAL/HISTORY messages, and sends configuration commands over
the NUS RX characteristic.

ESPHome's external-component architecture is used so users do not need to copy
C++ files into their ESPHome installation.

## Changelog

- Fixed: `pulsepal.h` previously contained the Python `__init__.py` content by
  mistake instead of the actual C++ header -- rebuilt from scratch based on
  what `pulsepal.cpp` and the codegen in `__init__.py` actually reference.
- Fixed: `parent->register_ble_node(this)` was being called both in the
  `PulsePal` constructor and again from `__init__.py`'s `to_code`, causing
  every GATT event (including every pulse notification) to be processed
  twice. Removed the duplicate call in `__init__.py`.
- Fixed: nothing ever sent `SET_TIME` to the device, so `epoch` was always 0
  in STATUS/INTERVAL/HISTORY records. Added a `time_id` config option and a
  time sync sent right after connecting/reconnecting.

## Known risk areas if this doesn't compile as-is

Parts of `pulsepal.cpp` use BLEClient/ESP-IDF APIs (`espbt::ESPBTUUID`,
`parent()->get_characteristic()`, `parent()->register_for_notify()`,
`get_gattc_if()`/`get_conn_id()`) that weren't verified against a live
ESPHome build. If compilation fails on any of these, paste the error and
they can be adjusted to match your installed ESPHome version's actual API.
