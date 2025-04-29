from pymodbus.client import ModbusSerialClient as ModbusClient
# from pymodbus.client import ModbusTcpClient as ModbusClient
from pymodbus.framer import Framer
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian
import time
import ctypes
import serial
import serial.tools
import serial.tools.list_ports
from  singleton_decorator import singleton
from loguru import logger

@singleton
class MyModbus:
    def __init__(self, port:str, baud:int=115200):
        self.port = port
        self.baudrate = baud
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            raise IOError("No USB serial devices found.")
        
        desList = [port.device for port in ports if port.description=='USB Serial']
        if len(desList) == 0:
            raise Exception("no RS485 converter")
        print("=====>", desList[0])

        self.motorModbus:ModbusClient = ModbusClient(desList[0], baudrate=baud, timeout=0.05)
        # self.motorModbus:ModbusClient = ModbusClient(host='127.0.0.1', framer=Framer.RTU)
        # logger.debug("connecting.........")
        # self.connect(port)
        
    def connect(self, port:str, baud:int=115200):
        self.port = port
        self.baudrate = 115200
        logger.debug("self connecting")
        self.motorModbus.close()
        if not self.motorModbus.connected:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                raise IOError("No USB serial devices found.")
            
            desList = [port.device for port in ports if port.description=='USB Serial']
            if len(desList) == 0:
                raise Exception("no RS485 converter")
            print("=====>", desList[0])
            self.motorModbus = ModbusClient(port=desList[0], baudrate=baud, timeout=0.05)
            logger.debug("re connecting.........")
            self.motorModbus.connect()
        else:
            logger.debug("connect already done")

            
    def disconnect(self):
        self.motorModbus.close()
        
    def moveAbsPos(self, pos):
        if pos > 2147483647 or pos < -214748364:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")
        
        reg = self.encode_32bisInt(pos)
        self.motorModbus.write_registers(0xE8, reg)
        
        logger.debug('Moved abs')

    def moveIncPos(self, pos):
        if pos > 2147483647 or pos < -214748364:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")

        reg = self.encode_32bisInt(pos)
        self.motorModbus.write_registers(0xCE, reg)
        logger.debug('Moved inc')

        
    def getPos(self):
        # logger.debug('get pos')
        rawReg = self.motorModbus.read_holding_registers(address=4, count=2, slave=1)
        if not rawReg.isError():
            data = self.decode_32bisInt(rawReg.registers)
            # logger.debug('getPos', data)
            return data
        else:
            raise IOError(f"IO no data. go check the connection to motor: {rawReg}")

    def getVel(self):
        # logger.debug('get vel')
        rawReg = self.motorModbus.read_holding_registers(address=0x19, count=1, slave=1)
        if not rawReg.isError():
            data = self.decode_16bitInt(rawReg.registers)
        else:
            raise IOError(f"IO no data. go check the connection to motor: {rawReg}")

        # logger.debug(data)
        return data

    def setStop(self):
        reg = 0x100
        # self.motorModbus.write_registers(0xC8, reg)
        reg = 0x001
        self.motorModbus.write_registers(0xD4, reg) #驅動器重啟
        time.sleep(0.1)
        reg = 0x000
        self.motorModbus.write_registers(0xD4, reg) #驅動器重啟
        logger.debug('motor Stop')
    
    def clearError(self):
        reg = 0x100
        self.motorModbus.write_registers(0xD4, reg)
        logger.debug('motor clean error')
        
    def checkError(self):
        '''0=OK, 6=Location out of tolerance'''
        reg = self.motorModbus.read_holding_registers(address=0xA3, count=1, slave=1)
        if not reg.isError():
            errorCode = reg.registers[0] & 0b1111
            
            # print(errorCode)
        else:
            raise IOError(f"IO no data. go check the connection to motor: \n{reg}")
        
        return errorCode
 
    def decode_32bisInt(self, registers:list):
        if len(registers) != 2 :
            raise ValueError(f"Input list must contain exactly 2 elements, now is {len(registers)}")
        
        data = registers
        data.reverse()
        decoded = 0x0
        for d in data:
            decoded = (decoded << 16) | d
        decoded = ctypes.c_int32(decoded).value
        return decoded
    
    def decode_16bitInt(self, registers:list):
        if len(registers) != 1 :
            raise ValueError(f"Input list must contain exactly 1 elements, now is {len(registers)}")

        data = registers[0]
        decoded = ctypes.c_int16(data).value
        return decoded

    
    def encode_32bisInt(self, value):
        data = value.to_bytes(4, signed=True, byteorder='little')

        encoded = []
        for i in range(0,4,2):
            temp:int = data[i+1] << 8 | data[i]
            encoded.append(temp)
        # logger.debug('encoded', [x for x in map(hex, encoded)])
        return encoded
        

        
        
if __name__ == "__main__":        
    motorModbus = MyModbus('/dev/ttyUSB2')
    
    motorModbus.clearError()
    n = motorModbus.getPos()
    logger.debug(f'decoded pos: {n}')

    # motorModbus.connect('dev/ttyUSB2')
    # error = motorModbus.checkError()
    # logger.debug(error)
    
    # error = motorModbus.checkError()


    motorModbus.setStop()
    
    
    # #motorModbus.moveAbsPos(-10000)
    # time.sleep(1)
    # #motorModbus.moveAbsPos(0)
    # a = motorModbus.getVel()
    # logger.debug(f'decoded: {n}')
    # motorModbus.disconnect()
    # decoded = ctypes.c_int16(0xEED6).value
    # logger.debug(f'decoded: {n}')
    
    reg_addr = 0x009A
    # reg_addr = 0x00bf
    # reg_addr = 0x0029
    # reg_addr = 0x00c0
    # reg_addr = 0x00c1
    rawReg = motorModbus.motorModbus.read_holding_registers(address=reg_addr, count=1, slave=1)
    logger.info(f'seeing: {hex(reg_addr)}')
    if rawReg.isError():
        logger.error("error")
        exit()    
    for reg in rawReg.registers:
        logger.info('REG_PRE: '+str(reg))
        logger.info('REG_PRE_b: '+hex(reg))


    motorModbus.motorModbus.write_registers(reg_addr, [70])

    rawReg = motorModbus.motorModbus.read_holding_registers(address=reg_addr, count=1, slave=1)
    if rawReg.isError():
        logger.error("error")
        exit()    
    for reg in rawReg.registers:
        logger.info('REG_NOW: '+str(reg))
    
    motorModbus.motorModbus.write_registers(0x00DC, [1])
    # 斷電保存

    motorModbus.disconnect()

    time.sleep(0.5)