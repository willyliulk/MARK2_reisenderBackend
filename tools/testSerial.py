import tkinter as tk
from tkinter import ttk
import serial
import json
import threading

class PicoDualStepperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PicoDualStepper Control Panel")
        self.serial_port = None
        self.running = True
        self.status_thread = None

        # Initialize Serial Communication
        self.init_serial()

        # Create GUI Layout
        self.create_widgets()

        # Start Status Monitor Thread
        self.start_status_monitor()

    def init_serial(self):
        try:
            self.serial_port = serial.Serial(port='COM12', baudrate=115200, timeout=1)
            print("Serial port connected.")
        except Exception as e:
            print(f"Error connecting to serial port: {e}")

    def create_widgets(self):
        # Title
        ttk.Label(self.root, text="PicoDualStepper Control Panel", font=("Arial", 18)).grid(row=0, column=0, columnspan=3, pady=10)

        # Motor Control
        motor_frame = ttk.LabelFrame(self.root, text="Motor Control", padding=(10, 10))
        motor_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        ttk.Label(motor_frame, text="Select Motor:").grid(row=0, column=0, pady=5)
        self.motor_select = ttk.Combobox(motor_frame, values=["Motor 1", "Motor 2"], state="readonly")
        self.motor_select.grid(row=0, column=1, pady=5)
        self.motor_select.current(0)

        ttk.Label(motor_frame, text="Target Position:").grid(row=1, column=0, pady=5)
        self.target_position = ttk.Entry(motor_frame)
        self.target_position.grid(row=1, column=1, pady=5)

        ttk.Button(motor_frame, text="Move", command=self.move_motor).grid(row=2, column=0, pady=5, sticky="ew")
        ttk.Button(motor_frame, text="Stop", command=self.stop_motor).grid(row=2, column=1, pady=5, sticky="ew")
        ttk.Button(motor_frame, text="Home", command=self.home_motor).grid(row=3, column=0, pady=5, columnspan=2, sticky="ew")

        ttk.Label(motor_frame, text="Max Speed:").grid(row=4, column=0, pady=5)
        self.max_speed = ttk.Entry(motor_frame)
        self.max_speed.grid(row=4, column=1, pady=5)

        ttk.Label(motor_frame, text="Acceleration:").grid(row=5, column=0, pady=5)
        self.acceleration = ttk.Entry(motor_frame)
        self.acceleration.grid(row=5, column=1, pady=5)

        ttk.Button(motor_frame, text="Set Parameters", command=self.set_motor_parameters).grid(row=6, column=0, columnspan=2, pady=5, sticky="ew")

        # Lamp Control
        lamp_frame = ttk.LabelFrame(self.root, text="Lamp Control", padding=(10, 10))
        lamp_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        ttk.Button(lamp_frame, text="Toggle Red Lamp", command=lambda: self.toggle_lamp("r")).grid(row=0, column=0, pady=5, sticky="ew")
        ttk.Button(lamp_frame, text="Toggle Yellow Lamp", command=lambda: self.toggle_lamp("y")).grid(row=1, column=0, pady=5, sticky="ew")
        ttk.Button(lamp_frame, text="Toggle Green Lamp", command=lambda: self.toggle_lamp("g")).grid(row=2, column=0, pady=5, sticky="ew")

        # Status Monitor
        status_frame = ttk.LabelFrame(self.root, text="Status Monitor", padding=(10, 10))
        status_frame.grid(row=1, column=2, padx=10, pady=10, sticky="nsew")

        ttk.Button(status_frame, text="Get Status", command=self.get_status).grid(row=0, column=0, pady=5, sticky="ew")
        self.status_text = tk.Text(status_frame, width=40, height=15, state="disabled")
        self.status_text.grid(row=1, column=0, pady=5)

    def send_command(self, cmd, params=None):
        if self.serial_port:
            command = {"cmd": cmd}
            if params:
                command.update(params)
            try:
                self.serial_port.write((json.dumps(command) + '\n').encode())
            except Exception as e:
                print(f"Error sending command: {e}")

    def move_motor(self):
        motor = 1 if self.motor_select.get() == "Motor 1" else 2
        position = int(self.target_position.get())
        self.send_command("MOVE", {"m": motor, "pos": position})

    def stop_motor(self):
        motor = 1 if self.motor_select.get() == "Motor 1" else 2
        self.send_command("STOP", {"m": motor})

    def home_motor(self):
        motor = 1 if self.motor_select.get() == "Motor 1" else 2
        self.send_command("HOME", {"m": motor})

    def set_motor_parameters(self):
        motor = 1 if self.motor_select.get() == "Motor 1" else 2
        max_speed = float(self.max_speed.get())
        acceleration = float(self.acceleration.get())
        self.send_command("SET", {"m": motor, "max": max_speed, "acc": acceleration})
        self.send_command("SAVE")

    def toggle_lamp(self, color):
        self.send_command("LAMP", {color: 1})

    def get_status(self):
        self.send_command("VERSION")

    def start_status_monitor(self):
        self.status_thread = threading.Thread(target=self.monitor_status, daemon=True)
        self.status_thread.start()

    def monitor_status(self):
        while self.running:
            if self.serial_port and self.serial_port.in_waiting > 0:
                try:
                    line = self.serial_port.readline().decode().strip()
                    self.update_status(line)
                except Exception as e:
                    print(f"Error reading from serial: {e}")

    def update_status(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.config(state="disabled")
        self.status_text.see(tk.END)

    def on_close(self):
        self.running = False
        if self.serial_port:
            self.serial_port.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = PicoDualStepperGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()