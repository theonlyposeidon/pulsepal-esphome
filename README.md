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

pulsepal:
  ble_client_id: pulsepal_ble
  pulses_per_kwh: 3200

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
