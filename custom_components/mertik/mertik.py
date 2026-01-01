import logging
import asyncio
import socket 
from .const import (
    UDP_PORT_DISCOVERY,
    UDP_PORT_TARGET,
    DISCOVERY_PAYLOAD,
    CMD_PREFIX,
    RESPONSE_PREFIX_1,
    RESPONSE_PREFIX_2,
    CMD_STATUS_POLL,
    CMD_IGNITE,
    CMD_SHUTDOWN,
    CMD_PILOT_STANDBY,
    CMD_AUX_ON,
    CMD_AUX_OFF,
    CMD_LIGHT_ON,
    CMD_LIGHT_OFF,
    CMD_FAN_ON,
    CMD_FAN_OFF,
    CMD_ECO_MODE,
    CMD_MANUAL_MODE,
    CMD_FLAME_PREFIX,
    CMD_FLAME_SUFFIX,
    FLAME_STEPS,
    CMD_LIGHT_SET_PREFIX,
    CMD_LIGHT_SET_SUFFIX
)

_LOGGER = logging.getLogger(__name__)

class Mertik:
    def __init__(self, ip, port=2000):
        self.ip = ip
        self.port = port
        self._lock = asyncio.Lock()
        
        # State variables
        self.on = False 
        self.mode = None 
        self.flameHeight = 0
        self._aux_on = False
        self._shutting_down = False
        self._igniting = False
        self._guard_flame_on = False 
        self._light_on = False
        self._light_brightness = 0
        self._ambient_temperature = 0.0
        
        # New Feature States
        self._fan_on = False
        self._low_battery = False
        self._rf_signal_level = 0
        
        # Glitch Counter
        self._temp_glitch_count = 0

    # --- Properties ---
    @property
    def is_on(self) -> bool:
        return self.on or self._guard_flame_on

    @property
    def is_aux_on(self) -> bool:
        return self._aux_on
        
    @property
    def is_igniting(self) -> bool:
        return self._igniting

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def ambient_temperature(self) -> float:
        return self._ambient_temperature

    @property
    def is_light_on(self) -> bool:
        return self._light_on

    @property
    def light_brightness(self) -> int:
        return self._light_brightness

    @property
    def get_mode(self):
        return self.mode

    def get_flame_height(self) -> int:
        return self.flameHeight

    # --- Discovery ---
    @staticmethod
    def get_devices():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("", UDP_PORT_DISCOVERY))
            hexstring = bytearray.fromhex(DISCOVERY_PAYLOAD)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(hexstring, ("<broadcast>", UDP_PORT_TARGET))

            sock.settimeout(3.0)
            data, addr = sock.recvfrom(1024)
            return {"address": addr}
        except (socket.timeout, OSError):
            return {}
        finally:
            sock.close()

    # --- Async Actions ---
    async def async_standBy(self):
        await self._async_send_command(CMD_PILOT_STANDBY)

    async def async_aux_on(self):
        await self._async_send_command(CMD_AUX_ON)

    async def async_aux_off(self):
        await self._async_send_command(CMD_AUX_OFF)

    async def async_ignite_fireplace(self):
        await self._async_send_command(CMD_IGNITE)

    async def async_refresh_status(self):
        await self._async_send_command(CMD_STATUS_POLL)

    async def async_guard_flame_off(self):
        await self._async_send_command(CMD_SHUTDOWN)

    async def async_light_on(self):
        await self._async_send_command(CMD_LIGHT_ON)

    async def async_light_off(self):
        await self._async_send_command(CMD_LIGHT_OFF)
        
    async def async_fan_on(self):
        await self._async_send_command(CMD_FAN_ON)

    async def async_fan_off(self):
        await self._async_send_command(CMD_FAN_OFF)

    async def async_set_eco(self):
        await self._async_send_command(CMD_ECO_MODE)

    async def async_set_manual(self):
        await self._async_send_command(CMD_MANUAL_MODE)

    async def async_set_light_brightness(self, brightness) -> None:
        normalized_brightness = (brightness - 1) / 254 * 100
        if normalized_brightness == 100:
            device_code = "4642"
        elif normalized_brightness == 0:
            device_code = "3633"
        else:
            l = 36 + round(normalized_brightness / 100 * 8)
            if l >= 40: l += 1
            device_code = f"{l:02d}{l:02d}"

        msg = f"{CMD_LIGHT_SET_PREFIX}{device_code}{CMD_LIGHT_SET_SUFFIX}"
        await self._async_send_command(msg)

    async def async_set_flame_height(self, flame_height) -> None:
        if 0 <= flame_height < len(FLAME_STEPS):
            l = FLAME_STEPS[flame_height]
            msg = CMD_FLAME_PREFIX + l + CMD_FLAME_SUFFIX
            await self._async_send_command(msg)

    # --- Core Communication ---
    async def _async_send_command(self, msg):
        async with self._lock:
            MAX_RETRIES = 3
            RETRY_DELAY = 2.0 
            
            if not isinstance(msg, str): msg = str(msg)
            full_payload = bytearray.fromhex(CMD_PREFIX + msg)
            process_status_prefixes = (RESPONSE_PREFIX_1, RESPONSE_PREFIX_2)
            last_error = None

            try:
                for attempt in range(1, MAX_RETRIES + 1):
                    writer = None
                    try:
                        future = asyncio.open_connection(self.ip, self.port)
                        reader, writer = await asyncio.wait_for(future, timeout=10.0)
                        
                        writer.write(full_payload)
                        await writer.drain()

                        data = await asyncio.wait_for(reader.read(1024), timeout=10.0)
                        if not data: raise ConnectionError("Empty response")

                        temp_data = data.decode("ascii", errors='ignore')
                        if len(temp_data) > 0: temp_data = temp_data[1:]
                        temp_data = temp_data.replace('\r', ';')

                        if temp_data.startswith(process_status_prefixes):
                            self._process_status(temp_data)
                        return 

                    except (OSError, asyncio.TimeoutError, ConnectionError) as e:
                        last_error = e
                        _LOGGER.warning(f"Attempt {attempt} failed: {repr(e)}")
                        if writer:
                            try:
                                writer.close()
                                await writer.wait_closed()
                            except Exception: pass
                        
                        if attempt < MAX_RETRIES:
                            sleep_time = RETRY_DELAY * attempt
                            await asyncio.sleep(sleep_time)
                        else:
                            _LOGGER.error(f"Unreachable: {repr(last_error)}")
            finally:
                await asyncio.sleep(0.25) 

    def _process_status(self, statusStr):
        try:
            # 1. Flame Height
            flameHeightRaw = int("0x" + statusStr[14:16], 0)
            if flameHeightRaw <= 123:
                self.flameHeight = 0
                self.on = False 
            else:
                # FIX: Clamp to 12. 
                # Mathematical edge case: round(12.9) -> 13, which is invalid.
                calc_height = round(((flameHeightRaw - 128) / 128) * 12) + 1
                self.flameHeight = min(12, calc_height)
                self.on = True

            # 2. Mode
            self.mode = statusStr[24:25]

            # 3. Bits
            statusBits = statusStr[16:20]
            self._shutting_down = self._from_bit_status(statusBits, 7)
            self._guard_flame_on = self._from_bit_status(statusBits, 8) 
            self._igniting = self._from_bit_status(statusBits, 11)
            raw_aux_on = self._from_bit_status(statusBits, 12)
            self._light_on = self._from_bit_status(statusBits, 13)
            
            # --- NEW SENSORS PARSING ---
            self._low_battery = self._from_bit_status(statusBits, 9) 
            self._fan_on = self._from_bit_status(statusBits, 14)      
            
            try:
                self._rf_signal_level = int("0x" + statusStr[12:14], 0)
            except ValueError:
                self._rf_signal_level = 0

            if self.flameHeight == 0:
                self._aux_on = False
            else:
                self._aux_on = raw_aux_on

            # 4. Light
            self._light_brightness = round(((int("0x" + statusStr[20:22], 0) - 100) / 151) * 255)
            if self._light_brightness < 0 or not self._light_on: self._light_brightness = 0

            # 5. Temp
            raw_temp = int("0x" + statusStr[30:32], 0) / 10
            
            if self._ambient_temperature == 0.0:
                 if 0.0 < raw_temp < 60.0:
                     _LOGGER.info(f"System initialized with temperature: {raw_temp}")
                     self._ambient_temperature = raw_temp
                     return

            # Glitch Filter
            if 1.0 < raw_temp < 50.0:
                diff = abs(raw_temp - self._ambient_temperature)
                
                if diff > 5.0:
                    self._temp_glitch_count += 1
                    if self._temp_glitch_count <= 3:
                        return 
                    else:
                        _LOGGER.warning(f"Accepting large temp change to {raw_temp} after verification.")
                        self._temp_glitch_count = 0
                        self._ambient_temperature = raw_temp
                else:
                    self._temp_glitch_count = 0
                    self._ambient_temperature = raw_temp
            
        except Exception as e:
            _LOGGER.error(f"Error parsing status: {e}")

    def _hex2bin(self, hex_val):
        return format(int(hex_val, 16), "b").zfill(8)

    def _from_bit_status(self, hex_val, index):
        return self._hex2bin(hex_val)[index : index + 1] == "1"
