# lower_computer_api.py
import logging
import re
import threading
from serial_communicator import SerialCommunicator

logger = logging.getLogger(__name__)

class LowerComputerAPI:
    def __init__(self, serial_comm: SerialCommunicator):
        self.comm = serial_comm
        self._lock = threading.Lock() # To ensure only one command sequence at a time

    def _execute_command(self, command_str, timeout_override=None):
        with self._lock:
            success, response_lines = self.comm.send_command_and_wait_for_ok(command_str, timeout_override=timeout_override)
            return success, response_lines

    def _query_command(self, command_str, data_prefix_expected):
        with self._lock:
            data_line, all_lines = self.comm.send_query_command(command_str, data_prefix_expected)
            # Check if "OK" is in all_lines if data_line is not None, or if data_line itself is "OK" for some queries
            if data_line:
                if "OK" in all_lines or data_line == "OK": # Some queries might just return OK after data.
                    return data_line
                # Specific parsing might be needed if OK is not guaranteed or if ERR appears after data
                # For now, if data_prefix is found, assume success.
                is_ok_present = any(line == "OK" for line in all_lines)
                is_err_present = any(line.startswith("ERR:") for line in all_lines)
                if is_ok_present and not is_err_present:
                     return data_line
                elif is_err_present:
                    logger.warning(f"Query '{command_str}' got data '{data_line}' but also error: {all_lines}")
                    return None # Or handle partial success
                else: # Got data but no clear OK or ERR (should be rare with send_query_command)
                    return data_line # Tentative success
            elif all_lines == "TIMEOUT_OR_READ_ERROR" or all_lines.startswith("ERR:"):
                 logger.error(f"Query '{command_str}' failed: {all_lines}")
            return None


    # --- Motor Commands ---
    def move_motor_to_steps(self, motor_idx: int, steps: int):
        """motor_idx: 1 or 2"""
        cmd = f"m{motor_idx}/m{steps}"
        success, _ = self._execute_command(cmd)
        return success

    def set_motor_speed(self, motor_idx: int, speed: float):
        cmd = f"m{motor_idx}/s{speed:.2f}"
        success, _ = self._execute_command(cmd)
        return success

    def set_motor_acceleration(self, motor_idx: int, accel: float):
        cmd = f"m{motor_idx}/a{accel:.2f}"
        success, _ = self._execute_command(cmd)
        return success

    def reset_motor_position(self, motor_idx: int, steps: int = 0):
        cmd = f"m{motor_idx}/r{steps}"
        success, _ = self._execute_command(cmd)
        return success

    def home_motor(self, motor_idx: int, reset_step = 0):
        """Moves motor to its 0 step position as defined by AccelStepper."""
        cmd = f"m{motor_idx}/h"
        success, _ = self._execute_command(cmd, timeout_override=15)
        if success: # After homing to step 0, ensure its currentPosition is set to 0
            return self.reset_motor_position(motor_idx, reset_step)
        return False
    
    def home_all_motors(self):
        cmd = "home"
        success, _ = self._execute_command(cmd)
        if success:
            # Assuming motors are 1 and 2
            res1 = self.reset_motor_position(1,0)
            res2 = self.reset_motor_position(2,0)
            return res1 and res2
        return False

    def stop_motor(self, motor_idx: int):
        cmd = f"stop{motor_idx}"
        success, _ = self._execute_command(cmd)
        return success

    def stop_all_motors(self):
        cmd = "stop"
        success, _ = self._execute_command(cmd)
        return success

    def get_motor_current_steps(self, motor_idx: int):
        """Returns current step position of the motor, or None on error."""
        cmd = f"m{motor_idx}/m" # Query current position
        expected_prefix = f"m{motor_idx}/m"
        
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                steps = int(response_line[len(expected_prefix):])
                return steps
            except ValueError:
                logger.error(f"Could not parse steps from response: {response_line}")
        return None
        
    def get_motor_max_speed(self, motor_idx: int):
        cmd = f"m{motor_idx}/s"
        expected_prefix = f"m{motor_idx}/s"
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                return float(response_line[len(expected_prefix):])
            except ValueError:
                logger.error(f"Could not parse speed from: {response_line}")
        return None

    def get_motor_acceleration(self, motor_idx: int):
        cmd = f"m{motor_idx}/a"
        expected_prefix = f"m{motor_idx}/a"
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                return float(response_line[len(expected_prefix):])
            except ValueError:
                logger.error(f"Could not parse accel from: {response_line}")
        return None

    def get_full_status(self):
        """Parses the 'status' command. Returns a dict or None."""
        # This is more complex as it returns multiple lines
        with self._lock:
            if not self.comm.send_command("status"):
                return None
            
            status_data = {"motors": {}, "emergency_stop_active": None}
            lines_received = []
            try:
                # Expect "=== Motor Status ==="
                line = self.comm.read_line()
                if line is None or "Motor Status" not in line : return None
                lines_received.append(line)

                # Motor 1
                line = self.comm.read_line() # Motor1: pos=%ld, speed=%.2f, accel=%.2f, running=%s
                if line is None: return None
                lines_received.append(line)
                match = re.match(r"Motor1: pos=(-?\d+), speed=([\d.]+), accel=([\d.]+), running=(YES|NO)", line)
                if match:
                    status_data["motors"][1] = {
                        "pos": int(match.group(1)), "speed": float(match.group(2)),
                        "accel": float(match.group(3)), "running": match.group(4) == "YES"
                    }

                # Motor 2
                line = self.comm.read_line() # Motor2: pos=%ld, speed=%.2f, accel=%.2f, running=%s
                if line is None: return None
                lines_received.append(line)
                match = re.match(r"Motor2: pos=(-?\d+), speed=([\d.]+), accel=([\d.]+), running=(YES|NO)", line)
                if match:
                    status_data["motors"][2] = {
                        "pos": int(match.group(1)), "speed": float(match.group(2)),
                        "accel": float(match.group(3)), "running": match.group(4) == "YES"
                    }
                
                # Emergency Stop
                line = self.comm.read_line() # Emergency Stop: %s
                if line is None: return None
                lines_received.append(line)
                if "Emergency Stop: ACTIVE" in line:
                    status_data["emergency_stop_active"] = True
                elif "Emergency Stop: INACTIVE" in line:
                    status_data["emergency_stop_active"] = False
                
                # Expect "=================="
                line = self.comm.read_line()
                if line is None or "===" not in line: return None # Could be "OK" too
                lines_received.append(line)
                
                # Check for "OK" if it's sent after status block by your firmware
                # Your current firmware doesn't send "OK" after "status"
                
                return status_data
            except Exception as e:
                logger.error(f"Error parsing status: {e}. Received: {lines_received}")
                return None

    # --- Switch/Button/Limit Commands ---
    def get_switch_status(self, switch_type: str): # emg, sht
        cmd = f"sw/{switch_type}"
        expected_prefix = f"sw/{switch_type}:"
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                return int(response_line[len(expected_prefix):]) # 0 or 1
            except ValueError:
                logger.error(f"Could not parse switch status from: {response_line}")
        return None

    def get_button_status(self, btn_type: str): # r, g, b
        cmd = f"btn/{btn_type}"
        expected_prefix = f"btn/{btn_type}:"
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                return int(response_line[len(expected_prefix):]) # 0 or 1
            except ValueError:
                logger.error(f"Could not parse button status from: {response_line}")
        return None

    def get_limit_switch_status(self, lim_idx: int): # 1 or 2
        cmd = f"lim/{lim_idx}"
        expected_prefix = f"lim/{lim_idx}:"
        response_line = self._query_command(cmd, expected_prefix)
        if response_line and response_line.startswith(expected_prefix):
            try:
                # Arduino: 1 for NORMAL, 0 for TRIGGERED. Manager might expect 1 for triggered.
                # For now, return raw value. Conversion can happen in main bridge.
                return int(response_line[len(expected_prefix):]) # 0 or 1
            except ValueError:
                logger.error(f"Could not parse limit switch status from: {response_line}")
        return None

    # --- Light Commands ---
    def control_light(self, color: str, action: str): # color: g,y,r; action: on,off,toggle
        cmd = f"light/{color}{action}"
        success, _ = self._execute_command(cmd)
        return success

    # --- Other Commands ---
    def save_config_to_eeprom(self):
        cmd = "save"
        success, _ = self._execute_command(cmd)
        return success