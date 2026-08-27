#pragma once

#ifdef USE_ESP32

#include <string>

#include "esphome/core/component.h"
#include "esphome/components/ble_client/ble_client.h"
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/number/number.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/time/real_time_clock.h"

#include <esp_gattc_api.h>

namespace esphome {
namespace pulsepal {

class PulsePal;

// Custom Number entity: forwards changes to the parent PulsePal component,
// which decides (via is_average_number/is_report_number) which BLE command
// to send. Neither this nor PulsePalSwitch below is a Component -- their
// "initial value" is published directly at codegen time (see
// set_initial_value/set_initial_state), so no setup()/loop() is needed.
class PulsePalNumber : public number::Number {
 public:
  void set_parent(PulsePal *parent) { this->parent_ = parent; }
  void set_initial_value(float value) { this->publish_state(value); }

 protected:
  void control(float value) override;

  PulsePal *parent_{nullptr};
};

class PulsePalSwitch : public switch_::Switch {
 public:
  void set_parent(PulsePal *parent) { this->parent_ = parent; }
  void set_initial_state(bool state) { this->publish_state(state); }

 protected:
  void write_state(bool state) override;

  PulsePal *parent_{nullptr};
};

class PulsePal : public Component, public ble_client::BLEClientNode {
 public:
  explicit PulsePal(ble_client::BLEClient *parent);

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gattc_if,
                            esp_ble_gattc_cb_param_t *param) override;

  void set_power_sensor(sensor::Sensor *s) { power_sensor_ = s; }
  void set_total_energy_sensor(sensor::Sensor *s) { total_energy_sensor_ = s; }
  void set_pulse_count_sensor(sensor::Sensor *s) { pulse_count_sensor_ = s; }
  void set_battery_sensor(sensor::Sensor *s) { battery_sensor_ = s; }
  void set_battery_voltage_sensor(sensor::Sensor *s) { battery_voltage_sensor_ = s; }

  void set_pulses_per_kwh(uint32_t v) { pulses_per_kwh_ = v; }
  void set_average_interval_number(PulsePalNumber *n) { average_interval_number_ = n; }
  void set_report_interval_number(PulsePalNumber *n) { report_interval_number_ = n; }
  void set_live_power_switch(PulsePalSwitch *s) { live_power_switch_ = s; }
  void set_time(time::RealTimeClock *t) { time_ = t; }

  // Called from PulsePalNumber/PulsePalSwitch when the user changes them.
  void set_average_interval(float value_ms);
  void set_report_interval(float value_ms);
  void set_live_power(bool value);

  bool is_average_number(PulsePalNumber *n) const { return n == average_interval_number_; }
  bool is_report_number(PulsePalNumber *n) const { return n == report_interval_number_; }

 protected:
  void process_line_(const char *line);
  void publish_status_(uint32_t count, float watts, int battery_pct, int battery_mv);
  void publish_interval_(uint32_t sequence, uint32_t epoch, float energy_kwh, float average_watts);
  void publish_history_(uint32_t sequence, uint32_t epoch, float energy_kwh, float average_watts);
  void send_command_(const std::string &command);
  void send_history_request_();
  void send_time_sync_();

  sensor::Sensor *power_sensor_{nullptr};
  sensor::Sensor *total_energy_sensor_{nullptr};
  sensor::Sensor *pulse_count_sensor_{nullptr};
  sensor::Sensor *battery_sensor_{nullptr};
  sensor::Sensor *battery_voltage_sensor_{nullptr};

  PulsePalNumber *average_interval_number_{nullptr};
  PulsePalNumber *report_interval_number_{nullptr};
  PulsePalSwitch *live_power_switch_{nullptr};
  time::RealTimeClock *time_{nullptr};

  uint32_t pulses_per_kwh_{1000};

  uint16_t tx_handle_{0};
  uint16_t rx_handle_{0};
  bool notify_registered_{false};

  std::string rx_buffer_;

  uint32_t last_pulse_count_{0};
  uint32_t last_history_sequence_{0};
};

}  // namespace pulsepal
}  // namespace esphome

#endif  // USE_ESP32
