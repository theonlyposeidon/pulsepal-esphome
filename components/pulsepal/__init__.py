import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components import ble_client, number, sensor, switch
from esphome.components import time as time_
from esphome.const import (
    CONF_ID,
    CONF_TIME_ID,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_BATTERY,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KILOWATT_HOURS,
    UNIT_PERCENT,
    UNIT_VOLT,
    UNIT_WATT,
)

DEPENDENCIES = ["ble_client"]
AUTO_LOAD = ["sensor", "number", "switch"]

pulsepal_ns = cg.esphome_ns.namespace("pulsepal")
PulsePal = pulsepal_ns.class_(
    "PulsePal",
    cg.Component,
    ble_client.BLEClientNode,
)

PulsePalNumber = pulsepal_ns.class_("PulsePalNumber", number.Number)
PulsePalSwitch = pulsepal_ns.class_("PulsePalSwitch", switch.Switch)

CONF_BLE_CLIENT_ID = "ble_client_id"
CONF_PULSES_PER_KWH = "pulses_per_kwh"
CONF_POWER = "power"
CONF_TOTAL_ENERGY = "total_energy"
CONF_PULSE_COUNT = "pulse_count"
CONF_BATTERY = "battery"
CONF_BATTERY_VOLTAGE = "battery_voltage"
CONF_AVERAGE_INTERVAL = "average_interval"
CONF_REPORT_INTERVAL = "report_interval"
CONF_LIVE_POWER = "live_power"

SENSOR_SCHEMA = sensor.sensor_schema
NUMBER_SCHEMA = number.number_schema
SWITCH_SCHEMA = switch.switch_schema

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(PulsePal),
        cv.Required(CONF_BLE_CLIENT_ID): cv.use_id(ble_client.BLEClient),
        cv.Optional(CONF_PULSES_PER_KWH, default=3200): cv.int_range(min=1, max=1000000),
        cv.Optional(CONF_TIME_ID): cv.use_id(time_.RealTimeClock),

        cv.Optional(CONF_POWER): SENSOR_SCHEMA.extend(
            {
                cv.Optional("device_class", default=DEVICE_CLASS_POWER): cv.string,
                cv.Optional("state_class", default=STATE_CLASS_MEASUREMENT): cv.string,
                cv.Optional("unit_of_measurement", default=UNIT_WATT): cv.string,
            }
        ),
        cv.Optional(CONF_TOTAL_ENERGY): SENSOR_SCHEMA.extend(
            {
                cv.Optional("device_class", default=DEVICE_CLASS_ENERGY): cv.string,
                cv.Optional("state_class", default=STATE_CLASS_TOTAL_INCREASING): cv.string,
                cv.Optional("unit_of_measurement", default=UNIT_KILOWATT_HOURS): cv.string,
            }
        ),
        cv.Optional(CONF_PULSE_COUNT): SENSOR_SCHEMA.extend(
            {
                cv.Optional("state_class", default=STATE_CLASS_TOTAL_INCREASING): cv.string,
                cv.Optional("unit_of_measurement", default="pulses"): cv.string,
            }
        ),
        cv.Optional(CONF_BATTERY): SENSOR_SCHEMA.extend(
            {
                cv.Optional("device_class", default=DEVICE_CLASS_BATTERY): cv.string,
                cv.Optional("state_class", default=STATE_CLASS_MEASUREMENT): cv.string,
                cv.Optional("unit_of_measurement", default=UNIT_PERCENT): cv.string,
            }
        ),
        cv.Optional(CONF_BATTERY_VOLTAGE): SENSOR_SCHEMA.extend(
            {
                cv.Optional("state_class", default=STATE_CLASS_MEASUREMENT): cv.string,
                cv.Optional("unit_of_measurement", default=UNIT_VOLT): cv.string,
            }
        ),

        cv.Optional(CONF_AVERAGE_INTERVAL): cv.All(
            NUMBER_SCHEMA,
            cv.Schema(
                {
                    cv.GenerateID(): cv.declare_id(PulsePalNumber),
                    cv.Optional("min_value", default=1000): cv.float_range(min=1000),
                    cv.Optional("max_value", default=3600000): cv.float_range(max=3600000),
                    cv.Optional("step", default=1000): cv.float_range(min=1),
                }
            ),
        ),
        cv.Optional(CONF_REPORT_INTERVAL): cv.All(
            NUMBER_SCHEMA,
            cv.Schema(
                {
                    cv.GenerateID(): cv.declare_id(PulsePalNumber),
                    cv.Optional("min_value", default=1000): cv.float_range(min=1000),
                    cv.Optional("max_value", default=3600000): cv.float_range(max=3600000),
                    cv.Optional("step", default=1000): cv.float_range(min=1),
                }
            ),
        ),
        cv.Optional(CONF_LIVE_POWER): cv.All(
            SWITCH_SCHEMA,
            cv.GenerateID(),
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_BLE_CLIENT_ID])
    var = cg.new_Pvariable(config[CONF_ID], parent)
    await cg.register_component(var, config)
    # NOTE: the PulsePal constructor already calls parent->register_ble_node(this)
    # in C++ -- do not also call it here, or every GATT event (including every
    # pulse notification) gets dispatched twice.
    cg.add(var.set_pulses_per_kwh(config[CONF_PULSES_PER_KWH]))

    if CONF_TIME_ID in config:
        time_var = await cg.get_variable(config[CONF_TIME_ID])
        cg.add(var.set_time(time_var))

    if CONF_POWER in config:
        sens = await sensor.new_sensor(config[CONF_POWER])
        cg.add(var.set_power_sensor(sens))

    if CONF_TOTAL_ENERGY in config:
        sens = await sensor.new_sensor(config[CONF_TOTAL_ENERGY])
        cg.add(var.set_total_energy_sensor(sens))

    if CONF_PULSE_COUNT in config:
        sens = await sensor.new_sensor(config[CONF_PULSE_COUNT])
        cg.add(var.set_pulse_count_sensor(sens))

    if CONF_BATTERY in config:
        sens = await sensor.new_sensor(config[CONF_BATTERY])
        cg.add(var.set_battery_sensor(sens))

    if CONF_BATTERY_VOLTAGE in config:
        sens = await sensor.new_sensor(config[CONF_BATTERY_VOLTAGE])
        cg.add(var.set_battery_voltage_sensor(sens))

    if CONF_AVERAGE_INTERVAL in config:
        num = cg.new_Pvariable(config[CONF_AVERAGE_INTERVAL][CONF_ID])
        await number.register_number(num, config[CONF_AVERAGE_INTERVAL])
        cg.add(num.set_parent(var))
        cg.add(num.set_initial_value(config[CONF_AVERAGE_INTERVAL].get("initial_value", 60000)))
        cg.add(var.set_average_interval_number(num))

    if CONF_REPORT_INTERVAL in config:
        num = cg.new_Pvariable(config[CONF_REPORT_INTERVAL][CONF_ID])
        await number.register_number(num, config[CONF_REPORT_INTERVAL])
        cg.add(num.set_parent(var))
        cg.add(num.set_initial_value(config[CONF_REPORT_INTERVAL].get("initial_value", 5000)))
        cg.add(var.set_report_interval_number(num))

    if CONF_LIVE_POWER in config:
        sw = cg.new_Pvariable(config[CONF_LIVE_POWER][CONF_ID])
        await switch.register_switch(sw, config[CONF_LIVE_POWER])
        cg.add(sw.set_parent(var))
        cg.add(sw.set_initial_state(True))
        cg.add(var.set_live_power_switch(sw))
