
class MotorManager_v2():
    # __metaclass__ = Singleton    
    class ManageState(Enum):
        STOP = 0
        RUNNING = 1
        
    class MotorState(Enum):
        IDEL = 0
        RUNNING = 1
        HOMEING = 2
        ERROR = 3
        

    
    @dataclass
    class MotorData:
        pos:float = 0.0
        vel:float = 0.0
        
    def __init__(self, id=0, homePos=0, broker='localhost', port=11883):
        '''ID由1開始'''
        self.id=id
        self.homePos=homePos
        self.motorData = self.MotorData()
        self.motorState = self.MotorState.IDEL
        self.motorProximity = [False, False]
        
        self.__managerState = self.ManageState.STOP
        
        # mqtt client
        self.broker=broker
        self.port = port
        
        # basic mqtt cb
        self.client = mqtt.Client(client_id=f"motorManager_v2_{self.id}")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
        self.topic_prefix = f'motor/{self.id}'
        
        
    async def startManager(self):
        logger.debug("startManger")
        self.__managerState = self.ManageState.RUNNING
        
        try:
            self.client.message_callback_add(f'{self.topic_prefix}/angle', self.__on_angle_cb)
            self.client.message_callback_add(f'{self.topic_prefix}/speed', self.__on_speed_cb)
            self.client.message_callback_add(f'{self.topic_prefix}/proximity', self.__on_proximity_cb)
            
            self.client.connect_async(self.broker, self.port)
            
            self.client.loop_start()
            
            self.taskHandel_monitor = asyncio.create_task(self.task_monitor_State())
            await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f'Error: {e}')
            self.__managerState = self.ManageState.STOP
            self.client.loop_stop()
            self.client.disconnect()
            if self.taskHandel_monitor is not None:
                self.taskHandel_monitor.cancel()
                self.taskHandel_monitor = None
            raise e
    
    async def closeManager(self):
        logger.debug(f"closeManager for motor_{self.id}")
        self.__managerState = self.ManageState.STOP
        if self.taskHandel_monitor is not None:
            self.taskHandel_monitor.cancel()
            self.taskHandel_monitor = None
        
        # 停止背景執行緒
        self.client.loop_stop()

        # 斷開與代理的連接
        self.client.disconnect()
        
    def on_connect(self, client, userdata, flags, rc):
        logger.debug("on_connect")
        if rc == 0:
            logger.debug(f"已連接到MQTT代理, 結果碼: {rc}")
            self.client.subscribe(f'{self.topic_prefix}/angle')
            self.client.subscribe(f'{self.topic_prefix}/speed')
            self.client.subscribe(f'{self.topic_prefix}/proximity')
        else:
            logger.error(f"連接失敗，結果碼: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """從MQTT代理斷開連接時的回調函數"""
        if rc != 0:
            logger.warning(f"意外斷開連接，結果碼: {rc}")
        
        # 重新連接到代理
        if self.__managerState != self.ManageState.STOP:
            self.client.reconnect()
    
    def __on_angle_cb(self, client, userdata, msg):
        """處理角度訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            # logger.debug(f"收到角度訊息: {payload}")
            self.motorData.pos = float(payload)
        except Exception as e:
            logger.error(f"處理角度訊息時出錯: {e}")

    def __on_speed_cb(self, client, userdata, msg):
        """處理速度訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            # logger.debug(f"收到速度訊息: {payload}")
            self.motorData.vel = float(payload)
        except Exception as e:
            logger.error(f"處理速度訊息時出錯: {e}")

    def __on_proximity_cb(self, client, userdata, msg):
        """處理接近開關訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            logger.debug(f"收到接近開關訊息: {payload}")
            self.__cb_proximity(payload)
        except Exception as e:
            logger.error(f"處理接近開關訊息時出錯: {e}")
        
        
    def goAbsPos(self, pos: float):
        """移動到絕對位置"""
        logger.debug("goAbsPos")
        if self.motorState == self.MotorState.ERROR:
            return
        self.motorState = self.MotorState.RUNNING
        self.client.publish(f"{self.topic_prefix}/cmd/goAbsPos", str(pos))
        
    def goIncPos(self, pos: float):
        """移動增量位置"""
        logger.debug("goIncPos")
        if self.motorState == self.MotorState.ERROR:
            return
        self.motorState = self.MotorState.RUNNING
        self.client.publish(f"{self.topic_prefix}/cmd/goIncPos", str(pos))
    
    def goHomePos(self):
        """移動到原點位置"""
        logger.debug("goHomePos")
        if self.motorState == self.MotorState.ERROR:
            return
        self.motorState = self.MotorState.HOMEING
        self.client.publish(f"{self.topic_prefix}/cmd/goHomePos", str(self.homePos))
        # self.client.publish(f"{self.topic_prefix}/cmd/goAbsPos", str(self.homePos))
        
    def motorStop(self):
        """停止電機"""
        logger.debug("motorStop")
        if self.motorState == self.MotorState.ERROR:
            return
        self.motorState = self.MotorState.IDEL
        self.client.publish(f"{self.topic_prefix}/cmd/stop", "")
    
    def resolve(self):
        """解決電機問題"""
        logger.debug("resolve")
        if self.motorState == self.MotorState.ERROR:
            self.motorState = self.MotorState.IDEL
            self.client.publish(f"{self.topic_prefix}/cmd/resolve", "")
    
    def get_motorData(self):
        """獲取電機數據"""
        return self.motorData
    
    def get_motorState(self):
        """獲取電機狀態"""            
        return self.motorState
        
    def get_proximitys(self):
        """獲取接近開關狀態"""
        return self.motorProximity
    
    def is_home(self):
        '''return True if motor is at home position'''
        if abs(self.motorData.pos - self.homePos) < 1:
            return True
        else:
            return False

    def __cb_proximity(self, content: str):
        """處理接近開關數據"""
        try:
            # 假設內容格式為 "0,0" 或 "1,0" 等
            values = content.strip().split(',')
            if len(values) >= 2:
                self.motorProximity[0] = values[0] == '1'
                self.motorProximity[1] = values[1] == '1'
        except Exception as e:
            logger.error(f"處理接近開關數據時出錯: {e}")
        
    async def task_monitor_State(self):
        """監控電機狀態"""
        logger.debug("task_monitor_State")
        while True:
            if self.__managerState == self.ManageState.STOP:
                break
            
            elif self.motorState == self.MotorState.ERROR:
                self.motorStop()
                if self.is_home():
                    self.motorState = self.MotorState.IDEL
                
            elif self.motorState == self.MotorState.HOMEING:
                if self.is_home():
                    self.motorState = self.MotorState.IDEL
                    self.motorStop()
                    
            elif self.motorState == self.MotorState.RUNNING:
                if self.motorProximity[0] or self.motorProximity[1]:
                    self.motorState = self.MotorState.ERROR
                    self.motorStop()
                elif self.motorData.vel == 0:
                    self.motorState = self.MotorState.IDEL
                    
            elif self.motorState == self.MotorState.IDEL:
                if self.motorData.vel != 0:
                    self.motorState = self.MotorState.RUNNING

            await asyncio.sleep(0.1)
        

    
 