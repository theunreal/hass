"""
MQTT switches for Tasmota. no need for startup script 
simplify the way you can work with Tasmota 

"""
import logging
from typing import Optional
import json

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.mqtt import (
    CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN, MqttAvailability)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_NAME, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_ICON, STATE_ON)
from homeassistant.components import mqtt, switch
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DOMAIN = 'mqtt_tasmota'


DEFAULT_INDEX =""
DEFAULT_NAME = 'MQTT Switch'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
CONF_INDEX = 'index'
CONF_SHORT_TOPIC ='stopic' # short_topic
DEFAULT_QOS = 1


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SHORT_TOPIC): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_INDEX, default=DEFAULT_INDEX): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_QOS, default=DEFAULT_QOS):
         vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    if discovery_info is None:
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_info)



async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT switch."""

    newswitch = MqttTasmotaSwitch(
        config.get(CONF_NAME),
        config.get(CONF_ICON),
        config.get(CONF_INDEX), # str '','1','2','3'
        config.get(CONF_SHORT_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_PAYLOAD_ON),
        config.get(CONF_PAYLOAD_OFF)
    )

    async_add_entities([newswitch])

def get_tasmota_avail_topic (topic):
    return ('tele/{}/LWT'.format(topic))

def get_tasmota_result (topic):
    return ('stat/{}/RESULT'.format(topic))

def get_tasmota_tele (topic):
    return ('tele/{}/SENSOR'.format(topic))

def get_tasmota_state (topic):
    return ('tele/{}/STATE'.format(topic))

def get_tasmota_command (topic,_index):
    return ('cmnd/{}/POWER{}'.format(topic,_index))


class MqttTasmotaSwitch(MqttAvailability, SwitchDevice):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, name, icon,
                 index,
                 short_topic, 
                 qos, retain, 
                 payload_on, 
                 payload_off
                 ):
        """Initialize the MQTT switch."""
        MqttAvailability.__init__(self, get_tasmota_avail_topic(short_topic), qos,
                                  "Online", "Offline")
        self._state = False
        self._name = name
        self._icon = icon
        self._short_topic = short_topic
        self._index = index # str
        self._status_str = "POWER{}".format(index)
        self._command_topic = get_tasmota_command (short_topic,index)
        self._result_topic = get_tasmota_result (short_topic)
        self._state_topic = get_tasmota_state (short_topic)
        self._qos = qos
        self._retain = retain
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._optimistic = False


    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await MqttAvailability.async_added_to_hass(self)

        @callback
        def state_message_received(topic, payload, qos):
            self.update_mqtt_results(payload)

        await mqtt.async_subscribe(
             self.hass, self._result_topic, state_message_received,
             self._qos)
        await mqtt.async_subscribe(
             self.hass, self._state_topic, state_message_received,
             self._qos)


    def update_mqtt_results (self,payload):
        try:
            #_LOGGER.error('get payload  %s ',payload)
            message = json.loads(payload)
            if self._status_str in message:
                val=message[self._status_str]
                if val == self._payload_on:
                    self._state = True
                elif val == self._payload_off:
                    self._state = False
                else:
                    _LOGGER.warning('unknown state %s val:%s',self._status_str,val)
        except ValueError:
            # If invalid JSON
          _LOGGER.error("Unable to parse payload as JSON: %s", payload)
          return

        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    async def async_turn_on(self, **kwargs):
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_on, self._qos,
            self._retain)

    async def async_turn_off(self, **kwargs):
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_off, self._qos,
            self._retain)

