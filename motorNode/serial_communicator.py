# serial_communicator.py
import threading
import serial
import time
import logging
from bridge_config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TIMEOUT, SERIAL_RECONNECT_DELAY

logger = logging.getLogger(__name__)

class SerialCommunicator:
    def __init__(self, port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE, timeout=SERIAL_TIMEOUT):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self._connect_lock = threading.Lock() # For thread-safe connect/reconnect

    def connect(self):
        with self._connect_lock:
            if self.serial_conn and self.serial_conn.is_open:
                logger.info("Serial connection already open.")
                return True
            try:
                logger.info(f"Attempting to connect to serial port {self.port} at {self.baudrate} baud.")
                self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                time.sleep(2) # Allow time for Arduino to reset after connection
                logger.info(f"Successfully connected to serial port {self.port}.")
                return True
            except serial.SerialException as e:
                logger.error(f"Failed to connect to serial port {self.port}: {e}")
                self.serial_conn = None
                return False

    def disconnect(self):
        with self._connect_lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                    logger.info(f"Disconnected from serial port {self.port}.")
                except Exception as e:
                    logger.error(f"Error disconnecting from serial port: {e}")
            self.serial_conn = None
            
    def is_connected(self):
        return self.serial_conn is not None and self.serial_conn.is_open

    def send_command(self, command):
        if not self.is_connected():
            logger.warning("Serial not connected. Attempting to reconnect...")
            if not self.connect():
                logger.error("Failed to send command: Serial reconnection failed.")
                return False
        
        try:
            command_with_newline = command + '\n'
            self.serial_conn.write(command_with_newline.encode('utf-8'))
            logger.debug(f"Sent: {command}")
            return True
        except serial.SerialException as e:
            logger.error(f"Serial error during send: {e}")
            self.disconnect() # Assume connection is lost
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending command '{command}': {e}")
            return False

    def read_line(self, timeout_override=None):
        if not self.is_connected():
            # logger.warning("Serial not connected. Cannot read line.") # Potentially too noisy
            return None
        
        read_timeout = timeout_override if timeout_override is not None else self.timeout
        original_timeout = self.serial_conn.timeout
        
        try:
            if self.serial_conn.timeout != read_timeout: # Temporarily change timeout if needed
                 self.serial_conn.timeout = read_timeout
            line = self.serial_conn.readline()
            if self.serial_conn.timeout != original_timeout: # Restore original
                 self.serial_conn.timeout = original_timeout

            if line:
                decoded_line = line.decode('utf-8', errors='ignore').strip()
                logger.debug(f"Received: {decoded_line}")
                return decoded_line
            return None # Timeout
        except serial.SerialException as e:
            logger.error(f"Serial error during read: {e}")
            self.disconnect() # Assume connection is lost
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading line: {e}")
            return None

    def send_command_and_wait_for_ok(self, command, max_lines=5, timeout_override=None):
        """Sends a command and expects 'OK' or 'ERR:...' within a few lines."""
        if not self.send_command(command):
            return False, "SEND_FAILED"

        responses = []
        for _ in range(max_lines):
            response = self.read_line(timeout_override)
            if response is None: # Timeout or error
                logger.warning(f"Timeout or error waiting for OK after command: {command}")
                return False, "TIMEOUT_OR_READ_ERROR"
            responses.append(response)
            if response == "OK":
                return True, responses
            if response.startswith("ERR:"):
                logger.error(f"Command '{command}' failed with error: {response}")
                return False, response
        
        logger.warning(f"No 'OK' or 'ERR:' received for command '{command}' within {max_lines} lines. Got: {responses}")
        return False, "NO_OK_ERR_RECEIVED"

    def send_query_command(self, command, data_prefix, max_lines=5)-> tuple[str|None, str|list[str]]:
        """Sends a command and expects a specific data line or 'ERR:...'."""
        if not self.send_command(command):
            return None, "SEND_FAILED"

        responses = []
        for _ in range(max_lines):
            response = self.read_line()
            if response is None: # Timeout or error
                logger.warning(f"Timeout or error waiting for data after query: {command}")
                return None, "TIMEOUT_OR_READ_ERROR"
            responses.append(response)
            if response.startswith(data_prefix):
                return response, responses # Return the data line and all received lines
            if response == "OK": # OK might come after data, or be the only response if no data
                continue
            if response.startswith("ERR:"):
                logger.error(f"Query command '{command}' failed with error: {response}")
                return None, response
        
        logger.warning(f"No data matching prefix '{data_prefix}' or 'ERR:' received for query '{command}'. Got: {responses}")
        return None, "NO_MATCHING_DATA_OR_ERR"