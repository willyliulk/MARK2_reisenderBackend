import serial

serial_port = serial.Serial('/dev/ttyUSB3', 500000, timeout=1)
serial_port.write(b'm\n')

res = serial_port.read_until(b'\r\n')

print(res)

serial_port.close()