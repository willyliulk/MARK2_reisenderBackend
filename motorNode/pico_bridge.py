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

import asyncio, json, sys, signal, logging, itertools, platform
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
ANGLE_TO_TICK = 42
ANGLE_OFFSET_0  = 33
ANGLE_OFFSET_1  = 330

if IS_WIN:
    CMD_ADDR  = "tcp://127.0.0.1:8780"
    STAT_ADDR = "tcp://127.0.0.1:8781"
else:
    CMD_ADDR  = "ipc:///tmp/pico_cmd"
    STAT_ADDR = "ipc:///tmp/pico_stat"


# ──────────────────── Serial Manager ────────────────────
class SerialManager:
    """
    • 自動掃描 USB CDC，斷線自動重連
    • 提供非同步 send(json_dict)
    • 收到 json line 後呼叫上層 callback
    """
    def __init__(self):
        self.reader = self.writer = None
        self.port   = None
        self.rx_cb  = None
        self._tx_q  = asyncio.Queue()

    async def start(self, rx_cb):
        self.rx_cb = rx_cb
        while True:
            try:
                await self._connect_and_loop()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(f"serial loop break: {e}")
            log.info("Re-scanning serial …")
            await asyncio.sleep(SCAN_INT)

    async def send(self, obj: dict):
        await self._tx_q.put(obj)

    # ───────── internal ─────────
    async def _connect_and_loop(self):
        while True:
            dev = self._auto_scan()
            if dev:
                self.port = dev
                break
            await asyncio.sleep(SCAN_INT)

        log.info(f"Opening serial@{self.port}")
        self.reader, self.writer = await serial_asyncio.open_serial_connection(
            url=self.port, baudrate=BAUD
        )
        log.info("Serial connected!")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._rx_loop())
            tg.create_task(self._tx_loop())

    async def _rx_loop(self):
        while True:
            line = await self.reader.readline()
            try:
                msg = json.loads(line.decode(errors="ignore").strip())
            except json.JSONDecodeError:
                log.warning(f"Bad JSON: {line[:60]!r}")
                continue
            await self.rx_cb(msg)

    async def _tx_loop(self):
        while True:
            obj = await self._tx_q.get()
            self.writer.write((json.dumps(obj) + "\n").encode())

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
                    cmd['pos'] = (cmd['pos']-ANGLE_OFFSET_0) * -ANGLE_TO_TICK
                elif cmd['m'] == 2:
                    cmd['pos'] = (cmd['pos']-ANGLE_OFFSET_1) * ANGLE_TO_TICK
            # print(cmd)
            fut = asyncio.get_running_loop().create_future()
            self.cmd_waiters[cid] = fut
            await self.serial.send(cmd)

            try:
                res = await asyncio.wait_for(fut, TIMEOUT)
            except asyncio.TimeoutError:
                self.cmd_waiters.pop(cid, None)
                res = {"ok": False, "err": "Timeout"}
            await self.rep.asend(json.dumps(res).encode())

    # ───────── Pub0 (status) ─────────
    async def _publish(self, obj: dict | bytes):
        self.last_stat_ts = asyncio.get_event_loop().time()
        if isinstance(obj, dict):
            obj = json.dumps(obj).encode()
        await self.pub.asend(obj)

    async def _keepalive_loop(self):
        while True:
            await asyncio.sleep(STATUS_FALLBACK)
            if asyncio.get_event_loop().time() - self.last_stat_ts > STATUS_FALLBACK:
                await self._publish(b'{"alive":1}')

    # ───────── Serial callback ─────────
    async def _on_serial_msg(self, msg: dict):
        if "cid" in msg:
            fut = self.cmd_waiters.pop(msg["cid"], None)
            if fut and not fut.done():
                fut.set_result(msg)
        else:
            # print(msg)
            if "m" in msg:
                msg['m'][0]["pos"] = (msg['m'][0]["pos"]) / -ANGLE_TO_TICK  + ANGLE_OFFSET_0
                msg['m'][1]["pos"] = (msg['m'][1]["pos"]) / ANGLE_TO_TICK + ANGLE_OFFSET_1
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
