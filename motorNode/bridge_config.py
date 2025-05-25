# bridge_config.py

# -- Serial Port Configuration --
# SERIAL_PORT = '/dev/ttyUSB0'  # Change to your Arduino's serial port
SERIAL_PORT = 'COM12' # Example for Windows
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0  # Seconds for serial read operations
SERIAL_RECONNECT_DELAY = 5 # Seconds

# -- MQTT Configuration --
MQTT_BROKER_HOST = 'localhost'
MQTT_BROKER_PORT = 11883 # Changed from 11883 as 1883 is default and more common
MQTT_CLIENT_ID_BRIDGE = 'mechine_middle_bridge_client'
MQTT_KEEP_ALIVE = 60
MQTT_RECONNECT_DELAY = 5 # Seconds

# -- Motor Definitions --
# This maps MQTT motor IDs to the lower computer's motor indices and conversion factors.
# 'lower_idx': 1 or 2 (from 'm1', 'm2' in Arduino code)
# 'steps_per_degree': YOU MUST CALCULATE THIS based on your motor, driver (microstepping), and any gearing.
#     Example: 200 steps/rev motor, 1/16 microstepping -> 3200 steps/rev.
#              3200 steps / 360 degrees = 8.888... steps/degree.
# 'limit_switches_indices': Maps lower computer limit switch (1 or 2) to this motor's proximity array [prox0, prox1].
#                           Use None if a limit switch is not applicable for a proximity sensor.
MOTOR_CONFIGS = [
    {
        "mqtt_id": 0,
        "lower_idx": 1,  # Corresponds to m1/..., stepper1 on Arduino
        "steps_per_degree": -34.444, # EXAMPLE VALUE - REPLACE
        "home_pos_steps": 0, # Step count considered as "home" on the lower computer after 'home' cmd
                           # This is usually 0 for AccelStepper's home command.
        "limit_switches_indices": [1, None] # [LIM_SW_1 maps to proximity[0], LIM_SW_2 maps to proximity[1]]
                                        # for motor with mqtt_id 1.
    },
    {
        "mqtt_id": 1,
        "lower_idx": 2,  # Corresponds to m2/..., stepper2 on Arduino
        "steps_per_degree": 34.444, # EXAMPLE VALUE - REPLACE
        "home_pos_steps": 0,
        "limit_switches_indices": [2, None] # Example: motor 2 doesn't use these global limit switches
                                               # or they are mapped differently.
    }
]

# -- Polling Intervals --
# How often to request data from the lower computer
POLLING_INTERVAL_MOTOR_DATA = 0.07  # Seconds (for position)
POLLING_INTERVAL_SENSORS = 0.02    # Seconds (for limit switches, emergency stop)

# -- Logging --
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR