#include "pulsepal.h"

#ifdef USE_ESP32

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esphome/core/log.h"

namespace esphome::pulsepal {

static const char *const TAG = "pulsepal";

static constexpr uint8_t NUS_SERVICE_UUID[16] = {
    0x9e, 0xca, 0x4e, 0xe2, 0x0c, 0xa9, 0x9a, 0xe0,
    0x93, 0xf3, 0xa3, 0xb5, 0x01, 0x00, 0x40, 0x6e};

static constexpr uint8_t NUS_TX_UUID[16] = {
    0x9e, 0xca, 0x4e, 0xe2, 0x0c, 0xa9, 0x9a, 0xe0,
    0x93, 0xf3, 0xa3, 0xb5, 0x03, 0x00, 0x40, 0x6e};

static constexpr uint8_t NUS_RX_UUID[16] = {
    0x9e, 0xca, 0x4e, 0xe2, 0x0c, 0xa9, 0x9a, 0xe0,
    0x93, 0xf3, 0xa3, 0xb5, 0x02, 0x00, 0x40, 0x6e};

static espbt::ESPBTUUID uuid_from_bytes(const uint8_t *bytes) {
  return espbt::ESPBTUUID::from_raw(bytes);
}

PulsePal::PulsePal(ble_client::BLEClient *parent) {
  parent->register_ble_node(this);
}

void PulsePal::setup() {
  this->rx_buffer_.reserve(256);
  this->node_state = espbt::ClientState::IDLE;
}

void PulsePal::loop() {
  this->disable_loop();
}

void PulsePal::dump_config() {
  ESP_LOGCONFIG(TAG, "PulsePal:");
  ESP_LOGCONFIG(TAG, "  Pulses/kWh: %lu", (unsigned long) this->pulses_per_kwh_);
  ESP_LOGCONFIG(TAG, "  Nordic UART Service enabled");
}

void PulsePal::gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gattc_if,
                                   esp_ble_gattc_cb_param_t *param) {
  switch (event) {
    case ESP_GATTC_SEARCH_CMPL_EVT: {
      auto service_uuid = uuid_from_bytes(NUS_SERVICE_UUID);
      auto tx_uuid = uuid_from_bytes(NUS_TX_UUID);
      auto rx_uuid = uuid_from_bytes(NUS_RX_UUID);

      auto *tx = this->parent()->get_characteristic(service_uuid, tx_uuid);
      auto *rx = this->parent()->get_characteristic(service_uuid, rx_uuid);

      if (tx == nullptr || rx == nullptr) {
        ESP_LOGW(TAG, "PulsePal NUS service/characteristics not found");
        return;
      }

      this->tx_handle_ = tx->handle;
      this->rx_handle_ = rx->handle;

      auto status = this->parent()->register_for_notify(this->tx_handle_);
      if (status != ESP_OK) {
        ESP_LOGW(TAG, "Failed to register NUS TX notifications: %d", status);
        return;
      }

      // Do NOT mark ESTABLISHED here. Registration is asynchronous.
      // ESPHome's current BLE client implementation expects this to happen
      // after ESP_GATTC_REG_FOR_NOTIFY_EVT.
      break;
    }

    case ESP_GATTC_REG_FOR_NOTIFY_EVT: {
      if (param->reg_for_notify.handle != this->tx_handle_)
        break;

      if (param->reg_for_notify.status != ESP_GATT_OK) {
        ESP_LOGW(TAG, "NUS notification registration failed: %d",
                 param->reg_for_notify.status);
        break;
      }

      this->notify_registered_ = true;
      this->node_state = espbt::ClientState::ESTABLISHED;

      ESP_LOGI(TAG, "PulsePal BLE connected");

      this->send_command_("SET_PPKWH," + std::to_string(this->pulses_per_kwh_) + "\n");

      if (this->report_interval_number_ != nullptr)
        this->send_command_("SET_REPORT," +
                            std::to_string((uint32_t) this->report_interval_number_->state) + "\n");

      if (this->average_interval_number_ != nullptr)
        this->send_command_("SET_AVERAGE," +
                            std::to_string((uint32_t) this->average_interval_number_->state) + "\n");

      if (this->live_power_switch_ != nullptr)
        this->send_command_("SET_LIVE," +
                            std::to_string(this->live_power_switch_->state ? 1 : 0) + "\n");

      this->send_history_request_();
      break;
    }

    case ESP_GATTC_NOTIFY_EVT: {
      if (param->notify.handle != this->tx_handle_)
        break;

      if (param->notify.value_len == 0)
        break;

      for (uint16_t i = 0; i < param->notify.value_len; i++) {
        char c = static_cast<char>(param->notify.value[i]);

        if (c == '\n' || c == '\r') {
          if (!this->rx_buffer_.empty()) {
            this->rx_buffer_.push_back('\0');
            this->process_line_(this->rx_buffer_.c_str());
            this->rx_buffer_.clear();
          }
        } else if (this->rx_buffer_.size() < 255) {
          this->rx_buffer_.push_back(c);
        }
      }
      break;
    }

    case ESP_GATTC_CLOSE_EVT:
    case ESP_GATTC_DISCONNECT_EVT:
      this->notify_registered_ = false;
      this->node_state = espbt::ClientState::IDLE;
      this->rx_buffer_.clear();
      ESP_LOGI(TAG, "PulsePal BLE disconnected");
      break;

    default:
      break;
  }
}

void PulsePal::process_line_(const char *line) {
  uint32_t count = 0;
  uint32_t sequence = 0;
  uint32_t epoch = 0;
  int battery_pct = -1;
  int battery_mv = -1;
  float watts = 0.0f;
  float energy_kwh = 0.0f;
  float average_watts = 0.0f;

  if (sscanf(line, "STATUS,%lu,%f,%d,%d,%lu",
             &count, &watts, &battery_pct, &battery_mv, &epoch) == 5) {
    this->publish_status_(count, watts, battery_pct, battery_mv);
    return;
  }

  if (sscanf(line, "INTERVAL,%lu,%lu,%f,%f",
             &sequence, &epoch, &energy_kwh, &average_watts) == 4) {
    this->publish_interval_(sequence, epoch, energy_kwh, average_watts);
    return;
  }

  if (sscanf(line, "HISTORY,%lu,%lu,%f,%f",
             &sequence, &epoch, &energy_kwh, &average_watts) == 4) {
    this->publish_history_(sequence, epoch, energy_kwh, average_watts);
    return;
  }

  ESP_LOGD(TAG, "Unknown message: %s", line);
}

void PulsePal::publish_status_(uint32_t count, float watts, int battery_pct,
                               int battery_mv) {
  this->last_pulse_count_ = count;

  if (this->power_sensor_ != nullptr)
    this->power_sensor_->publish_state(watts);

  if (this->pulse_count_sensor_ != nullptr)
    this->pulse_count_sensor_->publish_state(count);

  if (this->total_energy_sensor_ != nullptr) {
    float energy = static_cast<float>(count) /
                   static_cast<float>(this->pulses_per_kwh_);
    this->total_energy_sensor_->publish_state(energy);
  }

  if (this->battery_sensor_ != nullptr && battery_pct >= 0)
    this->battery_sensor_->publish_state(battery_pct);

  if (this->battery_voltage_sensor_ != nullptr && battery_mv >= 0)
    this->battery_voltage_sensor_->publish_state(
        static_cast<float>(battery_mv) / 1000.0f);
}

void PulsePal::publish_interval_(uint32_t sequence, uint32_t epoch,
                                 float energy_kwh, float average_watts) {
  (void) epoch;
  (void) average_watts;

  if (sequence <= this->last_history_sequence_)
    return;

  this->last_history_sequence_ = sequence;

  // The nRF lifetime pulse count is authoritative for total energy.
  // INTERVAL messages are retained for diagnostics/backfill logging.
  ESP_LOGD(TAG, "Interval %lu: %.6f kWh, %.1f W",
           (unsigned long) sequence, energy_kwh, average_watts);
}

void PulsePal::publish_history_(uint32_t sequence, uint32_t epoch,
                                float energy_kwh, float average_watts) {
  (void) epoch;

  if (sequence <= this->last_history_sequence_)
    return;

  this->last_history_sequence_ = sequence;

  ESP_LOGI(TAG, "History %lu: %.6f kWh, %.1f W",
           (unsigned long) sequence, energy_kwh, average_watts);
}

void PulsePal::send_command_(const std::string &command) {
  if (!this->notify_registered_ || this->rx_handle_ == 0)
    return;

  auto status = esp_ble_gattc_write_char(
      this->parent()->get_gattc_if(),
      this->parent()->get_conn_id(),
      this->rx_handle_,
      command.size(),
      reinterpret_cast<uint8_t *>(const_cast<char *>(command.data())),
      ESP_GATT_WRITE_TYPE_RSP,
      ESP_GATT_AUTH_REQ_NONE);

  if (status != ESP_OK) {
    ESP_LOGW(TAG, "BLE command failed: %d", status);
  }
}

void PulsePal::send_history_request_() {
  this->send_command_("REQUEST_HISTORY\n");
}

void PulsePal::set_average_interval(float value) {
  if (value < 1000)
    value = 1000;

  this->send_command_("SET_AVERAGE," +
                      std::to_string((uint32_t) value) + "\n");
}

void PulsePal::set_report_interval(float value) {
  if (value < 1000)
    value = 1000;

  this->send_command_("SET_REPORT," +
                      std::to_string((uint32_t) value) + "\n");
}

void PulsePal::set_live_power(bool value) {
  this->send_command_("SET_LIVE," +
                      std::to_string(value ? 1 : 0) + "\n");
}

void PulsePalNumber::control(float value) {
  if (this->parent_ == nullptr)
    return;

  if (this->parent_->is_average_number(this))
    this->parent_->set_average_interval(value);
  else if (this->parent_->is_report_number(this))
    this->parent_->set_report_interval(value);

  this->publish_state(value);
}

void PulsePalSwitch::write_state(bool state) {
  if (this->parent_ != nullptr)
    this->parent_->set_live_power(state);

  this->publish_state(state);
}

}  // namespace esphome::pulsepal

#endif
