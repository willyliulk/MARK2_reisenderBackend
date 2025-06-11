# mqtt_client_handler.py
import paho.mqtt.client as mqtt
import logging
import time
from bridge_config import (MQTT_BROKER_HOST, MQTT_BROKER_PORT, 
                           MQTT_CLIENT_ID_BRIDGE, MQTT_KEEP_ALIVE, MQTT_RECONNECT_DELAY)

logger = logging.getLogger(__name__)

class MQTTClientHandler:
    def __init__(self, client_id=MQTT_CLIENT_ID_BRIDGE,
                 broker_host=MQTT_BROKER_HOST, broker_port=MQTT_BROKER_PORT):
        self.client_id = client_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message # Default generic message handler

        self._connected = False
        self._on_message_callbacks = {} # For specific topic callbacks: topic -> function
        self._subscriptions = [] # List of topics to subscribe to on connect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Successfully connected to MQTT broker {self.broker_host}:{self.broker_port}")
            self._connected = True
            # Resubscribe to all topics
            for topic, qos in self._subscriptions:
                self.client.subscribe(topic, qos=qos)
                logger.info(f"Subscribed to {topic} with QoS {qos}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker with result code {rc}. Will attempt to reconnect.")
        self._connected = False
        # Reconnection logic is handled by Paho's loop or can be managed explicitly if needed.
        # For simplicity, Paho's internal reconnect mechanism is often sufficient if loop_start() is used.

    def _on_message(self, client, userdata, msg):
        logger.debug(f"Received MQTT message: {msg.topic} -> {msg.payload.decode()}")
        # Check if there's a specific callback for this topic pattern
        for topic_filter, callback in self._on_message_callbacks.items():
            if mqtt.topic_matches_sub(topic_filter, msg.topic):
                try:
                    callback(msg.topic, msg.payload.decode())
                except Exception as e:
                    logger.error(f"Error in MQTT message callback for {msg.topic}: {e}")
                return # Message handled by specific callback

        # Generic handler if no specific callback matched (optional)
        # logger.debug(f"No specific callback for topic {msg.topic}")


    def add_message_callback(self, topic_filter, callback):
        """
        Adds a callback for messages on a specific topic filter.
        The callback function should accept (topic, payload_string).
        """
        self._on_message_callbacks[topic_filter] = callback
        # If already connected, subscribe immediately. Otherwise, will be subscribed on_connect.
        if self._connected:
            # Find if this filter requires a new subscription or if an existing one covers it
            # For simplicity, we'll just add it to the list and let on_connect handle it,
            # or subscribe directly if needed.
            # Let's assume for now that subscriptions are added before connect, or handled by a subscribe method.
            pass


    def connect(self):
        try:
            logger.info(f"Attempting to connect to MQTT broker {self.broker_host}:{self.broker_port}")
            self.client.connect_async(self.broker_host, self.broker_port, MQTT_KEEP_ALIVE)
            self.client.loop_start() # Starts a background thread for network loop
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")

    def disconnect(self):
        logger.info("Disconnecting from MQTT broker.")
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False

    def subscribe(self, topic, qos=0):
        """Adds a topic to the subscription list and subscribes if connected."""
        if not any(sub[0] == topic for sub in self._subscriptions):
            self._subscriptions.append((topic, qos))
        
        if self._connected:
            self.client.subscribe(topic, qos=qos)
            logger.info(f"Subscribed to {topic} with QoS {qos}")


    def publish(self, topic, payload, qos=0, retain=False):
        if not self._connected:
            #logger.warning(f"MQTT not connected. Cannot publish to {topic}.") # Can be very noisy
            return
        try:
            self.client.publish(topic, payload, qos=qos, retain=retain)
            logger.debug(f"Published to MQTT: {topic} -> {payload}")
        except Exception as e:
            logger.error(f"Failed to publish to MQTT topic {topic}: {e}")
            
    def is_connected(self):
        return self._connected