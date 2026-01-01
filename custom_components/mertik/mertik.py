import logging
import asyncio
import socket 

_LOGGER = logging.getLogger(__name__)

class Mertik:
    def __init__(self, ip, port=2000):
        self.ip = ip
        self.port = port
        
        # --- TRAFFIC CONTROL ---
        # This lock ensures we never send 2 commands at once
        self._lock = asyncio.Lock()
        
        # Initialize state variables
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

    # --- Properties ---
    @property
    def is_on(self) -> bool:
        return self.on

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
        UDP_PORT = 30719
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("", UDP_PORT))
            
            # Send broadcast
            MESSAGE = "000100f6"
            hexstring = bytearray.fromhex(MESSAGE)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(hexstring, ("<broadcast>", 30718))

            # Receive reply
            sock.settimeout(3.0)
            data, addr = sock.recvfrom(1024)
            device = {"address": addr}
            return device
        except (socket.timeout, OSError):
            return {}
        finally:
            sock.close()

    # --- Async Actions ---
    async def async_standBy(self):
        await self._async_send_command("3136303003")

    async def async_aux_on(self):
        await self._async_send_command("32303031030a")

    async def async_aux_off(self):
        await self._async_send_command("32303030030a")

    async def async_ignite_fireplace(self):
        await self._async_send_command("314103")

    async def async_refresh_status(self):
        await self._async_send_command("303303")

    async def async_guard_flame_off(self):
        await self._async_send_command("313003")

    async def async_light_on(self):
        await self._async_send_command("3330303103")

    async def async_light_off(self):
        await self._async_send_command("3330303003")
        
    async def async_set_eco(self):
        msg = "4233303103"
        await self._async_send_command(msg)

    async def async_set_manual(self):
        msg = "423003"
        await self._async_send_command(msg)

    async def async_set_light_brightness(self, brightness) -> None:
        normalized_brightness = (brightness - 1) / 254 * 100

        if normalized_brightness == 100:
            device_code = "4642"
        elif normalized_brightness == 0:
            device_code = "3633"
        else:
            l = 36 + round(normalized_brightness / 100 * 8)
            if l >= 40:
                l += 1
            device_code = f"{l:02d}{l:02d}"

        msg = f"33304645{device_code}03"
        await self._async_send_command(msg)

    async def async_set_flame_height(self, flame_height) -> None:
        steps = [
            "3030", "3830", "3842", "3937", 
            "4132", "4145", "4239", "4335", 
            "4430", "4443", "4537", "4633", "4646"
        ]
        
        if 0 <= flame_height < len(steps):
            l = steps[flame_height]
            msg = "3136" + l + "03"
            await self._async_send_command(msg)
            # Trigger immediate refresh to update status
            await self.async_refresh_status()

    # --- Core Communication ---
    async def _async_send_command(self, msg):
        """Async command sender with Retry Logic, Traffic Lock, AND Cool Down."""
        
        # 1. ACQUIRE LOCK (Wait for line to clear)
        async with self._lock:
        
            MAX_RETRIES = 3
            RETRY_DELAY = 2.0
            
            if not isinstance(msg, str):
                msg = str(msg)
                
            send_command_prefix = "0233303330333033303830"
            full_payload = bytearray.fromhex(send_command_prefix + msg)
            
            process_status_prefixes = ("303030300003", "030300000003")

            last_error = None

            try:
                for attempt in range(1, MAX_RETRIES + 1):
                    writer = None
                    try:
                        # Connect
                        future = asyncio.open_connection(self.ip, self.port)
                        reader, writer = await asyncio.wait_for(future, timeout=10.0)
                        
                        # Send
                        writer.write(full_payload)
                        await writer.drain()

                        # Read
                        data = await asyncio.wait_for(reader.read(1024), timeout=10.0)

                        if not data:
                            raise ConnectionError("Empty response")

                        # Process
                        temp_data = data.decode("ascii", errors='ignore')
                        if len(temp_data) > 0:
                            temp_data = temp_data[1:]
                        
                        temp_data = temp_data.replace('\r', ';')

                        if temp_data.startswith(process_status_prefixes):
                            self._process_status(temp_data)
                        
                        # SUCCESS! Return immediately
                        return 

                    except (OSError, asyncio.TimeoutError, ConnectionError) as e:
                        last_error = e
                        _LOGGER.warning(f"Attempt {attempt} failed: {repr(e)}", exc_info=True)
                        
                        if writer:
                            try:
                                writer.close()
                                await writer.wait_closed()
                            except Exception:
                                pass

                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(RETRY_DELAY)
                        else:
                            _LOGGER.error(f"Unreachable: {repr(last_error)}", exc_info=True)

            finally:
                # --- MANDATORY COOL DOWN ---
                # Force a 1.0s pause BEFORE releasing the lock.
                # This ensures HA cannot slam the device with a 'Refresh' 
                # immediately after a command finishes.
                await asyncio.sleep(1.0) 

    def _process_status(self, statusStr):
        """Parses the raw status string."""
        try:
            # 1. Parse Flame Height
            tempSub = statusStr[14:16]
            tempSub = "0x" + tempSub
            flameHeightRaw = int(tempSub, 0)

            if flameHeightRaw <= 123:
                self.flameHeight = 0
                self.on = False
            else:
                self.flameHeight = round(((flameHeightRaw - 128) / 128) * 12) + 1
                self.on = True

            # 2. Parse Mode
            self.mode = statusStr[24:25]

            # 3. Parse Bits
            statusBits = statusStr[16:20]
            self._shutting_down = self._from_bit_status(statusBits, 7)
            self._guard_flame_on = self._from_bit_status(statusBits, 8)
            self._igniting = self._from_bit_status(statusBits, 11)
            self._aux_on = self._from_bit_status(statusBits, 12)
            self._light_on = self._from_bit_status(statusBits, 13)

            # 4. Parse Light Brightness
            self._light_brightness = round(
                ((int("0x" + statusStr[20:22], 0) - 100) / 151) * 255
            )
            if self._light_brightness < 0 or not self._light_on:
                self._light_brightness = 0

            # 5. Parse Temp (With Sanity Check)
            raw_temp = int("0x" + statusStr[30:32], 0) / 10
            
            if 1.0 < raw_temp < 50.0:
                self._ambient_temperature = raw_temp
            
        except Exception as e:
            _LOGGER.error(f"Error parsing status: {e}")

    def _hex2bin(self, hex_val):
        return format(int(hex_val, 16), "b").zfill(8)

    def _from_bit_status(self, hex_val, index):
        return self._hex2bin(hex_val)[index : index + 1] == "1"
