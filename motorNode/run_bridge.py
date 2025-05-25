# run_bridge.py
import signal
from main_bridge_app import MachineMiddleBridge, logger

def main():
    bridge = MachineMiddleBridge()

    def signal_handler(sig, frame):
        logger.info(f"Signal {sig} received. Initiating shutdown...")
        bridge.stop() # Request graceful shutdown

    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handle kill/system shutdown

    bridge.run_forever() # This now includes start() and the main loop

if __name__ == '__main__':
    main()