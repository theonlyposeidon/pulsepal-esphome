import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components import ble_client, number, sensor, switch
from esphome.components import time as time_
from esphome.const import (
    CONF_ID,
    CONF_TIME_ID,
    CONF_MIN_VALUE,
    CONF_MAX_VALUE,
    CONF_STEP,
    CONF_INITIAL_VALUE,
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

# NOTE: sensor.sensor_schema() / number.number_schema() / switch.switch_schema()
# are factory FUNCTIONS -- they must be CALLED with kwargs to produce an actual
# cv.Schema object. Assigning the bare function (as this file used to) and
# calling .extend() on it fails with "'function' object has no attribute
# 'extend'", since a plain function has no .extend().

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(PulsePal),
        cv.Required(CONF_BLE_CLIENT_ID): cv.use_id(ble_client.BLEClient),
        cv.Optional(CONF_PULSES_PER_KWH, default=3200): cv.int_range(min=1, max=1000000),
        cv.Optional(CONF_TIME_ID): cv.use_id(time_.RealTimeClock),

        cv.Optional(CONF_POWER): sensor.sensor_schema(
            unit_of_measurement=UNIT_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_TOTAL_ENERGY): sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOWATT_HOURS,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        cv.Optional(CONF_PULSE_COUNT): sensor.sensor_schema(
            unit_of_measurement="pulses",
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        cv.Optional(CONF_BATTERY): sensor.sensor_schema(
            unit_of_measurement=UNIT_PERCENT,
            device_class=DEVICE_CLASS_BATTERY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_BATTERY_VOLTAGE): sensor.sensor_schema(
            unit_of_measurement=UNIT_VOLT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),

        # min_value/max_value/step aren't part of number.number_schema()'s own
        # kwargs -- they're read separately in to_code() and passed into
        # number.new_number(), matching how ESPHome's own custom Number
        # components do it (see e.g. esphome/issues#6172 for the pattern).
        cv.Optional(CONF_AVERAGE_INTERVAL): number.number_schema(
            PulsePalNumber,
        ).extend(
            {
                cv.Optional(CONF_MIN_VALUE, default=1000): cv.float_,
                cv.Optional(CONF_MAX_VALUE, default=3600000): cv.float_,
                cv.Optional(CONF_STEP, default=1000): cv.float_,
                cv.Optional(CONF_INITIAL_VALUE, default=60000): cv.float_,
            }
        ),
        cv.Optional(CONF_REPORT_INTERVAL): number.number_schema(
            PulsePalNumber,
        ).extend(
            {
                cv.Optional(CONF_MIN_VALUE, default=1000): cv.float_,
                cv.Optional(CONF_MAX_VALUE, default=3600000): cv.float_,
                cv.Optional(CONF_STEP, default=1000): cv.float_,
                cv.Optional(CONF_INITIAL_VALUE, default=5000): cv.float_,
            }
        ),
        cv.Optional(CONF_LIVE_POWER): switch.switch_schema(
            PulsePalSwitch,
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
        conf = config[CONF_AVERAGE_INTERVAL]
        num = await number.new_number(
            conf,
            min_value=conf[CONF_MIN_VALUE],
            max_value=conf[CONF_MAX_VALUE],
            step=conf[CONF_STEP],
        )
        cg.add(num.set_parent(var))
        cg.add(num.set_initial_value(conf[CONF_INITIAL_VALUE]))
        cg.add(var.set_average_interval_number(num))

    if CONF_REPORT_INTERVAL in config:
        conf = config[CONF_REPORT_INTERVAL]
        num = await number.new_number(
            conf,
            min_value=conf[CONF_MIN_VALUE],
            max_value=conf[CONF_MAX_VALUE],
            step=conf[CONF_STEP],
        )
        cg.add(num.set_parent(var))
        cg.add(num.set_initial_value(conf[CONF_INITIAL_VALUE]))
        cg.add(var.set_report_interval_number(num))

    if CONF_LIVE_POWER in config:
        sw = await switch.new_switch(config[CONF_LIVE_POWER])
        cg.add(sw.set_parent(var))
        cg.add(sw.set_initial_state(True))
        cg.add(var.set_live_power_switch(sw))
