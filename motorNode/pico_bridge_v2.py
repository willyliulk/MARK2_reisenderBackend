#!/usr/bin/env python
"""
pico_bridge_xplat.py  •  nng + Serial  • 2025-06
-------------------------------------------------
可在 Windows / Linux / macOS 直接執行

依賴：
    pip install pyserial-asyncio pynng==0.6.*

埠位 (預設)：
    Linux/mac : ipc:///tmp/pico_cmd  / pico_stat
    Windows   : tcp://127.0.0.1:8780 / 8781
"""

import asyncio, json, sys, signal, logging, itertools, platform, os, subprocess
from pathlib import Path
import pynng, serial_asyncio
from serial.tools import list_ports

# ──────────────────── 基本設定 ────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pico")

IS_WIN = sys.platform.startswith("win")
BAUD          = 115200
SCAN_INT      = 2          # Serial 掃描間隔 (秒)
STATUS_FALLBACK = 2.0      # N 秒內無下位機狀態 ⇒ 送 keep-alive
ANGLE_TO_TICK = 105
ANGLE_OFFSET_0  = 33
ANGLE_OFFSET_1  = 330

if IS_WIN:
    CMD_ADDR  = "tcp://127.0.0.1:8780"
    STAT_ADDR = "tcp://127.0.0.1:8781"
else:
    CMD_ADDR  = "ipc:///tmp/pico_cmd"
    STAT_ADDR = "ipc:///tmp/pico_stat"


# ──────────────────── USB Device Helper ────────────────────
class USBDeviceHelper:
    """USB 設備輔助類，提供重置功能"""
    
    @staticmethod
    async def find_pico_usb_path():
        """尋找 Raspberry Pi Pico 的 USB 路徑"""
        if IS_WIN:
            return None  # Windows 不支持直接操作 sysfs
        
        try:
            for device in os.listdir('/sys/bus/usb/devices/'):
                vendor_path = f'/sys/bus/usb/devices/{device}/idVendor'
                product_path = f'/sys/bus/usb/devices/{device}/idProduct'
                
                if os.path.exists(vendor_path) and os.path.exists(product_path):
                    try:
                        with open(vendor_path, 'r') as f:
                            vendor = f.read().strip()
                        with open(product_path, 'r') as f:
                            product = f.read().strip()
                        
                        if vendor == '2e8a' and product == '000a':
                            return device
                    except Exception:
                        pass
            return None
        except Exception as e:
            log.error(f"查找 Pico USB 路徑時出錯: {e}")
            return None
    
    @staticmethod
    async def reset_usb_device(device_path=None):
        """重置 USB 設備"""
        if IS_WIN:
            log.warning("Windows 系統不支持直接重置 USB 設備")
            return False
        
        if not device_path:
            device_path = await USBDeviceHelper.find_pico_usb_path()
            
        if not device_path:
            log.error("無法找到 Pico 設備路徑，無法重置")
            return False
        
        log.info(f"正在重置 USB 設備: {device_path}")
        
        try:
            # 使用 subprocess 執行重置命令
            await asyncio.create_subprocess_shell(
                f"echo '{device_path}' | sudo tee /sys/bus/usb/drivers/usb/unbind",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await asyncio.sleep(2)
            
            await asyncio.create_subprocess_shell(
                f"echo '{device_path}' | sudo tee /sys/bus/usb/drivers/usb/bind",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            log.info("USB 設備重置完成")
            return True
        except Exception as e:
            log.error(f"重置 USB 設備時出錯: {e}")
            return False


# ──────────────────── Serial Manager ────────────────────
class SerialManager:
    """
    • 自動掃描 USB CDC，斷線自動重連
    • 提供非同步 send(json_dict)
    • 收到 json line 後呼叫上層 callback
    • 新增: 自動重置功能
    """
    def __init__(self):
        self.reader = self.writer = None
        self.port   = None
        self.rx_cb  = None
        self._tx_q  = asyncio.Queue()
        self.usb_helper = USBDeviceHelper()
        self.reset_attempts = 0
        self.max_reset_attempts = 3
        self.reset_cooldown = 60  # 冷卻時間（秒）
        self.last_reset_time = 0

    async def start(self, rx_cb):
        self.rx_cb = rx_cb
        while True:
            try:
                await self._connect_and_loop()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(f"serial loop break: {e}")
                # 嘗試重置 USB 設備
                await self._try_reset_device()
            log.info("Re-scanning serial …")
            await asyncio.sleep(SCAN_INT)

    async def send(self, obj: dict):
        await self._tx_q.put(obj)

    # ───────── internal ─────────
    async def _connect_and_loop(self):
        while True:
            # dev = self._auto_scan()
            dev = r"/dev/ttyACM0"
            if dev:
                self.port = dev
                break
            
            # 如果找不到設備，嘗試重置
            if not IS_WIN:
                await self._try_reset_device()
            
            await asyncio.sleep(SCAN_INT)

        log.info(f"Opening serial@{self.port}")
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=BAUD
            )
            log.info("Serial connected!")
            
            # 連接成功，重置嘗試次數
            self.reset_attempts = 0

            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._rx_loop())
                tg.create_task(self._tx_loop())
        except Exception as e:
            log.error(f"Serial connection error: {e}")
            # 連接失敗，嘗試重置
            await self._try_reset_device()
            raise

    async def _rx_loop(self):
        consecutive_errors = 0
        max_consecutive_errors = 5  # 連續錯誤閾值
        
        while True:
            try:
                line = await self.reader.readline()
                if not line:  # 空行可能表示連接問題
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        log.warning(f"Received {consecutive_errors} empty lines, possible connection issue")
                        raise ConnectionError("Serial connection may be broken")
                    continue
                
                # 成功接收數據，重置錯誤計數
                consecutive_errors = 0
                
                try:
                    msg = json.loads(line.decode(errors="ignore").strip())
                except json.JSONDecodeError:
                    log.warning(f"Bad JSON: {line[:60]!r}")
                    continue
                await self.rx_cb(msg)
            except (serial_asyncio.serial.SerialException, ConnectionError) as e:
                log.error(f"Serial read error: {e}")
                # 讀取錯誤，可能需要重置設備
                raise

    async def _tx_loop(self):
        while True:
            obj = await self._tx_q.get()
            try:
                self.writer.write((json.dumps(obj) + "\n").encode())
                await self.writer.drain()  # 確保數據被發送
            except Exception as e:
                log.error(f"Serial write error: {e}")
                # 寫入錯誤，可能需要重置設備
                raise

    async def _try_reset_device(self):
        """嘗試重置 USB 設備，包含冷卻時間和嘗試次數限制"""
        if IS_WIN:
            log.warning("Windows 系統不支持自動重置 USB 設備")
            return False
        
        current_time = asyncio.get_event_loop().time()
        # 檢查是否在冷卻期
        if current_time - self.last_reset_time < self.reset_cooldown:
            log.info(f"USB 重置冷卻中，跳過重置 ({int(self.reset_cooldown - (current_time - self.last_reset_time))}秒後可再次嘗試)")
            return False
        
        # 檢查嘗試次數
        if self.reset_attempts >= self.max_reset_attempts:
            log.warning(f"已達到最大重置嘗試次數 ({self.max_reset_attempts})，等待冷卻期結束")
            self.reset_attempts = 0  # 重置計數器
            self.last_reset_time = current_time  # 更新冷卻時間
            return False
        
        log.info(f"嘗試重置 USB 設備 (第 {self.reset_attempts + 1}/{self.max_reset_attempts} 次)")
        
        # 執行重置
        success = await self.usb_helper.reset_usb_device()
        self.reset_attempts += 1
        
        if success:
            log.info("USB 設備重置成功")
        else:
            log.error("USB 設備重置失敗")
        
        # 無論成功與否，都記錄最後重置時間
        if self.reset_attempts >= self.max_reset_attempts:
            self.last_reset_time = current_time
        
        return success

    @staticmethod
    def _auto_scan():
        """
        回傳可用序列埠 (string) or None
        判斷規則：
          • VID/PID = 2E8A:000A (Raspberry Pi Pico)
          • 描述中含 'Pico' / 'USB Serial' / 'CH340' / 'CP210' …
          • Windows 額外考慮 'COMx'
        """
        CAND = []
        for p in list_ports.comports():
            if p.product == "pico":
                p.device
            if p.vid == 0x2E8A:
                return p.device
            kw = (p.description or "").lower()
            if any(k in kw for k in ("pico", "ch340", "usb serial", "cp210")):
                return p.device
            CAND.append(p.device)
        return CAND[0] if CAND else None


# ──────────────────── Device Service (nng) ────────────────────
class DeviceService:
    def __init__(self):
        self.rep = pynng.Rep0(listen=CMD_ADDR)
        self.pub = pynng.Pub0(listen=STAT_ADDR)
        self.serial = SerialManager()

        self.cid_iter    = itertools.count(1)
        self.cmd_waiters = {}        # cid -> Future
        self.last_stat_ts = 0
        self.consecutive_timeouts = 0
        self.max_consecutive_timeouts = 3  # 連續超時閾值

    async def run(self):
        log.info(f"Cmd(Rep0)  listen  {CMD_ADDR}")
        log.info(f"Stat(Pub0) listen  {STAT_ADDR}")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._rep_loop(), name="rep")
            tg.create_task(self._keepalive_loop(), name="keepalive")
            tg.create_task(self.serial.start(self._on_serial_msg), name="serial")

    # ───────── Rep0 (command) ─────────
    async def _rep_loop(self):
        TIMEOUT = 10
        while True:
            raw = await self.rep.arecv()
            try:
                cmd = json.loads(raw)
            except Exception:
                await self.rep.asend(b'{"ok":false,"err":"BadJSON"}')
                continue

            cid = next(self.cid_iter)
            cmd["cid"] = cid
            # print(cmd)
            if 'pos' in cmd:
                if cmd['m'] == 1:
                    cmd['pos'] = (cmd['pos']-ANGLE_OFFSET_0) * ANGLE_TO_TICK
                elif cmd['m'] == 2:
                    cmd['pos'] = (cmd['pos']-ANGLE_OFFSET_1) * -ANGLE_TO_TICK
            # print(cmd)
            fut = asyncio.get_running_loop().create_future()
            self.cmd_waiters[cid] = fut
            await self.serial.send(cmd)

            try:
                res = await asyncio.wait_for(fut, TIMEOUT)
                # 成功收到回應，重置連續超時計數
                self.consecutive_timeouts = 0
            except asyncio.TimeoutError:
                self.cmd_waiters.pop(cid, None)
                res = {"ok": False, "err": "Timeout"}
                
                # 增加連續超時計數
                self.consecutive_timeouts += 1
                log.warning(f"命令超時 (連續第 {self.consecutive_timeouts}/{self.max_consecutive_timeouts} 次)")
                
                # 如果連續超時次數達到閾值，嘗試重置設備
                if self.consecutive_timeouts >= self.max_consecutive_timeouts:
                    log.warning(f"檢測到 {self.consecutive_timeouts} 次連續超時，嘗試重置設備")
                    await self.serial._try_reset_device()
                    self.consecutive_timeouts = 0  # 重置計數器
            
            await self.rep.asend(json.dumps(res).encode())

    # ───────── Pub0 (status) ─────────
    async def _publish(self, obj: dict | bytes):
        self.last_stat_ts = asyncio.get_event_loop().time()
        if isinstance(obj, dict):
            obj = json.dumps(obj).encode()
        await self.pub.asend(obj)

    async def _keepalive_loop(self):
        no_status_count = 0
        max_no_status = 5  # 連續無狀態更新閾值
        
        while True:
            await asyncio.sleep(STATUS_FALLBACK)
            current_time = asyncio.get_event_loop().time()
            
            if current_time - self.last_stat_ts > STATUS_FALLBACK:
                await self._publish(b'{"alive":1}')
                no_status_count += 1
                
                # 如果長時間沒有收到狀態更新，可能需要重置設備
                if no_status_count >= max_no_status:
                    log.warning(f"長時間 ({no_status_count * STATUS_FALLBACK}秒) 未收到設備狀態更新，嘗試重置設備")
                    await self.serial._try_reset_device()
                    no_status_count = 0  # 重置計數器
            else:
                no_status_count = 0  # 收到狀態更新，重置計數器

    # ───────── Serial callback ─────────
    async def _on_serial_msg(self, msg: dict):
        if "cid" in msg:
            fut = self.cmd_waiters.pop(msg["cid"], None)
            if fut and not fut.done():
                fut.set_result(msg)
        else:
            # print(msg)
            if "m" in msg:
                msg['m'][0]["pos"] = (msg['m'][0]["pos"]) / ANGLE_TO_TICK  + ANGLE_OFFSET_0
                msg['m'][1]["pos"] = (msg['m'][1]["pos"]) / -ANGLE_TO_TICK + ANGLE_OFFSET_1
            # print(msg)
            await self._publish(msg)


# ──────────────────── main ────────────────────
async def amain():
    # Windows: event-loop policy
    if IS_WIN:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    svc = DeviceService()

    # UNIX 訊號
    loop = asyncio.get_running_loop()
    if not IS_WIN:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(_shutdown(loop, s)))
    try:
        await svc.run()
    except KeyboardInterrupt:
        await _shutdown(loop, signal.SIGINT if not IS_WIN else None)

async def _shutdown(loop, sig):
    if sig:
        log.info(f"Received {sig!s} → shutting down …")
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

if __name__ == "__main__":
    asyncio.run(amain())
