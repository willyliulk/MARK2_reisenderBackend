import logging
import time
import threading
from threading import RLock
from enum import Enum

from bridge_config import (MOTOR_CONFIGS, POLLING_INTERVAL_MOTOR_DATA, POLLING_INTERVAL_SENSORS,
                         SERIAL_PORT, SERIAL_RECONNECT_DELAY, MQTT_RECONNECT_DELAY, LOG_LEVEL)
from serial_communicator import SerialCommunicator
from lower_computer_api import LowerComputerAPI
from mqtt_client_handler import MQTTClientHandler

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBridgeApp")

class ThreadSafeLowerComputerAPI:
    """Thread-safe wrapper for LowerComputerAPI"""
    def __init__(self, serial_comm):
        self._api = LowerComputerAPI(serial_comm)
        self._lock = RLock()  # 使用 RLock 允許同一執行緒重複取得鎖
    
    def move_motor_to_steps(self, motor_idx, steps):
        with self._lock:
            return self._api.move_motor_to_steps(motor_idx, steps)
    
    def get_motor_current_steps(self, motor_idx):
        with self._lock:
            return self._api.get_motor_current_steps(motor_idx)
    
    def home_motor(self, motor_idx, home_steps=0):
        with self._lock:
            return self._api.home_motor(motor_idx, home_steps)
    
    def stop_motor(self, motor_idx):
        with self._lock:
            return self._api.stop_motor(motor_idx)
    
    def get_switch_status(self, switch_type):
        with self._lock:
            return self._api.get_switch_status(switch_type)
    
    def get_limit_switch_status(self, switch_idx):
        with self._lock:
            return self._api.get_limit_switch_status(switch_idx)
    
    def control_light(self, light_type, state):
        with self._lock:
            return self._api.control_light(light_type, state)

class MachineMiddleBridge:
    def __init__(self):
        self.motor_configs_map = {mc["mqtt_id"]: mc for mc in MOTOR_CONFIGS}
        
        self.serial_comm = SerialCommunicator()
        self.lower_api = ThreadSafeLowerComputerAPI(self.serial_comm)  # 使用執行緒安全版本
        self.mqtt_client = MQTTClientHandler()

        self._stop_event = threading.Event()
        self._polling_threads = []

        self.current_motor_steps = {} # {lower_idx: steps}
        self.current_motor_angles = {} # {mqtt_id: angle}
        self.limit_switch_states = {} # {lower_lim_idx: state (0 or 1 from Arduino)}
        self.emergency_stop_active = None

    def _mqtt_command_handler(self, topic: str, payload: str):
        logger.info(f"MQTT Command Received: {topic} = {payload}")
        parts = topic.split('/')
        if len(parts) < 4:
            logger.warning(f"Malformed command topic: {topic}")
            return

        try:
            mqtt_motor_id = int(parts[1])
            command_type = parts[3]
        except (ValueError, IndexError):
            logger.warning(f"Could not parse motor ID or command type from topic: {topic}")
            return

        motor_conf = self.motor_configs_map.get(mqtt_motor_id)
        if not motor_conf:
            logger.error(f"Received command for unknown MQTT motor ID: {mqtt_motor_id}")
            return
        
        lower_idx = motor_conf["lower_idx"]

        if command_type == "goAbsPos":
            try:
                target_angle = float(payload)
                target_steps = int(target_angle * motor_conf["steps_per_degree"])
                logger.info(f"Motor {mqtt_motor_id} (Lower {lower_idx}): Moving to angle {target_angle}° (steps {target_steps})")
                self.lower_api.move_motor_to_steps(lower_idx, target_steps)
            except ValueError:
                logger.error(f"Invalid payload for goAbsPos: {payload}")
        
        elif command_type == "goIncPos":
            # Incremental move needs current position. Get it from our tracked state.
            # Note: This assumes our tracked state is accurate enough.
            # For higher precision, query current steps first, then calculate.
            current_steps = self.current_motor_steps.get(lower_idx)
            if current_steps is None:
                logger.warning(f"Cannot perform goIncPos for motor {mqtt_motor_id}: current position unknown. Querying...")
                current_steps = self.lower_api.get_motor_current_steps(lower_idx)
                if current_steps is None:
                    logger.error(f"Failed to get current position for goIncPos motor {mqtt_motor_id}")
                    return
                self.current_motor_steps[lower_idx] = current_steps

            try:
                inc_angle = float(payload)
                inc_steps = int(inc_angle * motor_conf["steps_per_degree"])
                target_steps = current_steps + inc_steps
                logger.info(f"Motor {mqtt_motor_id} (Lower {lower_idx}): Moving incrementally by {inc_angle}° ({inc_steps} steps) to {target_steps} steps")
                self.lower_api.move_motor_to_steps(lower_idx, target_steps)
            except ValueError:
                logger.error(f"Invalid payload for goIncPos: {payload}")

        elif command_type == "goHomePos":
            # motor_manager_v2 sends homePos value, but AccelStepper 'home' cmd goes to 0.
            # We'll use the Arduino's 'homeX' command which moves to step 0,
            # then Arduino's 'mX/r0' sets current position to 0.
            # The manager's `homePos` from its init is what *it* considers home angle.
            # Our `motor_conf["home_pos_steps"]` is what lower computer calls 0 after home.
            home_angle = float(payload)
            logger.info(f"Motor {mqtt_motor_id} (Lower {lower_idx}): Homing to {home_angle}")
            success = self.lower_api.home_motor(lower_idx, home_angle * motor_conf["steps_per_degree"])
            time.sleep(1) # Wait for homing to complete
            if success:
                 # After homing, its step count is 0. Update our internal state.
                self.current_motor_steps[lower_idx] = home_angle * motor_conf["steps_per_degree"]
                angle = home_angle # Should be home_angle
                self.current_motor_angles[mqtt_motor_id] = angle
                self.mqtt_client.publish(f"motor/{mqtt_motor_id}/angle", f"{angle:.3f}")
                logger.info(f"Motor {mqtt_motor_id} homed. Position set to 0 steps, {angle:.3f} degrees.")
            else:
                logger.error(f"Homing failed for motor {mqtt_motor_id}")

        elif command_type == "stop":
            logger.info(f"Motor {mqtt_motor_id} (Lower {lower_idx}): Stopping")
            self.lower_api.stop_motor(lower_idx)
        
        elif command_type == "resolve": # Placeholder for error resolution logic
            logger.info(f"Motor {mqtt_motor_id} (Lower {lower_idx}): Resolve command received (not fully implemented in bridge)")
            # Potentially re-enable motor or clear error flags if lower computer has them
            # For now, just ensure it's not in emergency stop locally.
            if self.emergency_stop_active:
                logger.warning("Cannot resolve, emergency stop is active on lower computer.")
            else:
                self.lower_api.home_motor(mqtt_motor_id)
                logger.info("Resolve: No specific action taken by bridge for now.")
        else:
            logger.warning(f"Unknown MQTT command type: {command_type} for topic {topic}")

    def _mqtt_light_command_handler(self, topic: str, payload: str):
        logger.info(f"MQTT light Command Received: {topic} = {payload}")
        parts = topic.split('/')
        
        try:
            _ = parts[0] #light
            light_choosed = parts[1] #{r|y|g}
        except (ValueError, IndexError):
            logger.warning(f"Could not parse light command type from topic: {topic}")
            return

        light_state = payload
        if payload not in {"on", "off"}:
            logger.warning(f"light_state incorrect for light command: {payload}")
            
        self.lower_api.control_light(light_choosed, light_state)
        
    def _setup_mqtt_subscriptions(self):
        for mc in MOTOR_CONFIGS:
            mqtt_id = mc["mqtt_id"]
            # General command topic for this motor ID
            # Using a wildcard for the specific command (goAbsPos, stop etc.)
            # This requires the callback to parse the full topic.
            cmd_topic_filter = f"motor/{mqtt_id}/cmd/#"
            self.mqtt_client.subscribe(cmd_topic_filter, qos=0)
            self.mqtt_client.add_message_callback(cmd_topic_filter, self._mqtt_command_handler)
            logger.info(f"Subscribed to MQTT commands for motor {mqtt_id} on {cmd_topic_filter}")
        
        cmd_topic_light = 'light/#'
        self.mqtt_client.subscribe(cmd_topic_light, qos=0)
        self.mqtt_client.add_message_callback(cmd_topic_light, self._mqtt_light_command_handler)
            
    def _poll_motor_data(self):
        """Periodically polls motor positions and converts to angles."""
        while not self._stop_event.is_set():
            if not self.serial_comm.is_connected():
                time.sleep(POLLING_INTERVAL_MOTOR_DATA) # Wait before retrying connection in next loop
                continue

            for mqtt_id, motor_conf in self.motor_configs_map.items():
                lower_idx = motor_conf["lower_idx"]
                steps = self.lower_api.get_motor_current_steps(lower_idx)
                if steps is not None:
                    self.current_motor_steps[lower_idx] = steps
                    angle = steps / motor_conf["steps_per_degree"]
                    self.current_motor_angles[mqtt_id] = angle
                    
                    # Publish to MQTT topic like motor/{id}/angle
                    angle_topic = f"motor/{mqtt_id}/angle"
                    self.mqtt_client.publish(angle_topic, f"{angle:.3f}", qos=0) # Adjust precision as needed
                else:
                    logger.debug(f"Failed to get steps for motor {mqtt_id} (Lower {lower_idx})")
            
            time.sleep(POLLING_INTERVAL_MOTOR_DATA)
        logger.info("Motor data polling thread stopped.")

    def _poll_sensor_data(self):
        """Periodically polls limit switches and emergency stop status."""
        while not self._stop_event.is_set():
            if not self.serial_comm.is_connected():
                time.sleep(POLLING_INTERVAL_SENSORS)
                continue

            # Poll Emergency Stop
            emg_val = self.lower_api.get_switch_status("emg") # Arduino: HIGH (1) = normal, LOW (0) = pressed/active
            if emg_val is not None:
                # Your C++ code: if(digitalRead(SW_EMG) == HIGH) means NOT stopped (normal)
                # So, emg_val == 0 means emergency stop is ACTIVE
                # motor manager v2 task_monitor_State implies proximity[0] or [1] being True causes ERROR state.
                # Let's assume manager's proximity expects True when triggered/active.
                self.emergency_stop_active = (emg_val == 0) # True if emg is active
                # Publish to a general bridge topic, as EMG is global
                self.mqtt_client.publish("bridge/emergency_stop", str(self.emergency_stop_active).lower(), qos=1, retain=True)

            # Poll Limit Switches (LIM_SW_1, LIM_SW_2 are global on Arduino)
            raw_lim_states = {}
            for lim_idx_on_arduino in [1, 2]: # Physical limit switches on Arduino
                state = self.lower_api.get_limit_switch_status(lim_idx_on_arduino)
                if state is not None:
                    # Arduino: state 1 = TRIGGERED, 0 =  NORMAL
                    # Manager expects proximity: True if triggered
                    raw_lim_states[lim_idx_on_arduino] = (state == 1) # True if triggered

            # Map raw limit switch states to motor-specific proximity topics
            for mqtt_id, motor_conf in self.motor_configs_map.items():
                motor_proximity_payload = ["0", "0"] # Default to not triggered
                
                # First proximity sensor for this MQTT motor
                lim_idx_for_prox0 = motor_conf["limit_switches_indices"][0]
                if lim_idx_for_prox0 is not None and lim_idx_for_prox0 in raw_lim_states:
                    if raw_lim_states[lim_idx_for_prox0]: # True if triggered
                        motor_proximity_payload[0] = "1"
                
                # Second proximity sensor for this MQTT motor
                lim_idx_for_prox1 = motor_conf["limit_switches_indices"][1]
                if lim_idx_for_prox1 is not None and lim_idx_for_prox1 in raw_lim_states:
                    if raw_lim_states[lim_idx_for_prox1]: # True if triggered
                        motor_proximity_payload[1] = "1"
                
                prox_topic = f"motor/{mqtt_id}/proximity"
                self.mqtt_client.publish(prox_topic, ",".join(motor_proximity_payload), qos=1, retain=True)

            time.sleep(POLLING_INTERVAL_SENSORS)
        logger.info("Sensor data polling thread stopped.")

    def start(self):
        logger.info("Starting Machine Middle Bridge...")
        
        # Start MQTT client first, so it's ready for publishes from polling threads
        self.mqtt_client.connect()
        # Wait for MQTT to connect initially
        timeout = 10  # seconds
        start_time = time.time()
        while not self.mqtt_client.is_connected() and (time.time() - start_time) < timeout:
            logger.info("Waiting for MQTT connection...")
            time.sleep(1)
        
        if not self.mqtt_client.is_connected():
            logger.error("MQTT client failed to connect. Bridge will not function correctly.")
            # Decide if to proceed or exit. For robustness, let's try to continue, it might connect later.
        else:
            self._setup_mqtt_subscriptions()

        # Attempt initial serial connection
        if not self.serial_comm.connect():
            logger.warning(f"Initial serial connection to {SERIAL_PORT} failed. Will keep trying in background.")
            # Polling threads will handle reconnections

        self._stop_event.clear()
        
        motor_poll_thread = threading.Thread(target=self._poll_motor_data, name="MotorPollThread")
        sensor_poll_thread = threading.Thread(target=self._poll_sensor_data, name="SensorPollThread")
        
        self._polling_threads.extend([motor_poll_thread, sensor_poll_thread])
        
        for t in self._polling_threads:
            t.daemon = True # Allow main program to exit even if threads are running
            t.start()
            
        logger.info("Machine Middle Bridge started. Polling threads running.")

    def stop(self):
        logger.info("Stopping Machine Middle Bridge...")
        self._stop_event.set()

        for t in self._polling_threads:
            if t.is_alive():
                logger.info(f"Waiting for thread {t.name} to stop...")
                t.join(timeout=POLLING_INTERVAL_SENSORS * 2) # Wait a bit longer than poll interval
                if t.is_alive():
                    logger.warning(f"Thread {t.name} did not stop in time.")
        self._polling_threads.clear()
        
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        if self.serial_comm:
            self.serial_comm.disconnect()
        
        logger.info("Machine Middle Bridge stopped.")

    def run_forever(self):
        self.start()
        try:
            while not self._stop_event.is_set():
                # Check and attempt to reconnect serial if disconnected
                if not self.serial_comm.is_connected():
                    logger.info(f"Serial disconnected. Attempting reconnect in {SERIAL_RECONNECT_DELAY}s...")
                    time.sleep(SERIAL_RECONNECT_DELAY)
                    self.serial_comm.connect() # connect() has its own logging

                # Check and attempt to reconnect MQTT (Paho handles some, but explicit check can be useful)
                if not self.mqtt_client.is_connected():
                    logger.info(f"MQTT disconnected. Paho should be attempting reconnect. Manual check in {MQTT_RECONNECT_DELAY}s...")
                    # Paho's loop_start() typically handles reconnections.
                    # If more control is needed, you might call self.mqtt_client.client.reconnect()
                    # but be careful not to interfere with Paho's internal mechanisms.
                    # For now, assume Paho's loop handles it.
                    time.sleep(MQTT_RECONNECT_DELAY)

                time.sleep(1) # Main loop check interval
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down...")
        finally:
            self.stop()