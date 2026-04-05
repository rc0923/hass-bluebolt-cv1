"""Asyncio-based communication with BlueBolt UPS."""

import asyncio
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

# Telnet command codes
IAC = 255  # Interpret As Command


class BlueBoltAPI:
    """Handles communication with the BlueBolt UPS using asyncio."""

    def __init__(self, host, port=23):
        """Initialize the BlueBolt API with the provided host IP."""
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.lock = asyncio.Lock()
        self.last_outlet_status = {}
        self.last_power_data = {
            "volts_in": 0.0,
            "volts_out": 0.0,
            "watts": 0.0,
            "current": 0.0,
            "battery": 0.0,
            "load": 0.0,
        }
        self.last_connection_attempt = None
        self.connection_retry_interval = 10
        self.connection_timeout = 10

    async def connect(self):
        """Establish a connection with the UPS."""
        # Check if we've tried to connect too recently
        now = datetime.now()
        if (
            self.last_connection_attempt
            and (now - self.last_connection_attempt).total_seconds()
            < self.connection_retry_interval
        ):
            _LOGGER.debug("Skipping connection - retry interval not reached")
            return False

        self.last_connection_attempt = now

        try:
            _LOGGER.info("Connecting to BlueBolt UPS at %s:%s...", self.host, self.port)

            # Create connection with timeout
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.connection_timeout,
            )
            _LOGGER.info("Socket connection established")

            # Discard initial telnet negotiation
            await asyncio.sleep(0.3)
            initial_data = await self.reader.read(1024)
            _LOGGER.debug(f"Initial data: {initial_data!r}")

            # Try a simple command to verify connection works
            _LOGGER.debug("Verifying connection...")

            for attempt in range(2):
                test_command = "?POWER"
                self.writer.write(f"{test_command}\r\n".encode("ascii"))
                await self.writer.drain()

                # Read response
                response_lines = []
                start_time = asyncio.get_event_loop().time()

                while asyncio.get_event_loop().time() - start_time < 2:
                    try:
                        chunk = await asyncio.wait_for(
                            self.reader.readline(), timeout=0.5
                        )
                        if not chunk:
                            break
                        if chunk[0] == IAC:
                            continue
                        try:
                            line = chunk.decode("ascii").strip()
                            if line and "=" in line:
                                response_lines.append(line)
                                break  # Got data, good enough
                        except UnicodeDecodeError:
                            pass
                    except asyncio.TimeoutError:
                        break

                if response_lines:
                    _LOGGER.info(f"Successfully connected to BlueBolt UPS")
                    return True

                await asyncio.sleep(0.3)

            _LOGGER.error("No valid responses from UPS")
            await self.disconnect()
            return False

        except asyncio.TimeoutError:
            _LOGGER.error(f"Connection timeout to {self.host}:{self.port}")
            await self.disconnect()
            return False
        except ConnectionRefusedError:
            _LOGGER.error(f"Connection refused by {self.host}:{self.port}")
            await self.disconnect()
            return False
        except Exception as e:
            _LOGGER.error(f"Error connecting to UPS: {e}", exc_info=True)
            await self.disconnect()
            return False

    async def disconnect(self):
        """Close the connection."""
        if self.writer:
            try:
                self.writer.close()
                await asyncio.wait_for(self.writer.wait_closed(), timeout=1.0)
            except Exception as e:
                _LOGGER.warning(f"Error closing connection: {e}")
        self.writer = None
        self.reader = None

    async def send_command(self, command, timeout=3):
        """Send a command and return the response.

        The UPS is very unreliable - just accept any response with data.
        """
        async with self.lock:
            if not self.writer or not self.reader:
                if not await self.connect():
                    return None

            try:
                _LOGGER.debug(f"Sending: {command}")
                self.writer.write(f"{command}\r\n".encode("ascii"))
                await self.writer.drain()

                response_lines = []
                start_time = asyncio.get_event_loop().time()

                # Read for up to 'timeout' seconds
                while asyncio.get_event_loop().time() - start_time < timeout:
                    try:
                        chunk = await asyncio.wait_for(
                            self.reader.readline(), timeout=0.5
                        )
                        if not chunk:
                            break
                        if chunk[0] == IAC:
                            continue

                        try:
                            line = chunk.decode("ascii").strip()
                            if line and "=" in line:
                                response_lines.append(line)
                                _LOGGER.debug(f"Received: {line}")
                        except UnicodeDecodeError:
                            pass

                    except asyncio.TimeoutError:
                        if response_lines:
                            break

                response = "\n".join(response_lines)

                # Return ANY response that has data
                if response:
                    return response
                else:
                    _LOGGER.debug(f"No data received for {command}")
                    return None

            except Exception as e:
                _LOGGER.error(f"Error sending command: {e}", exc_info=True)
                await self.disconnect()
                return None

        return None

    async def get_power_status(self):
        """Get power status by sending multiple commands and parsing all responses.

        The UPS has quirky behavior and often returns data from different commands.
        We send multiple commands and parse any valid data we receive.
        """
        collected_data = {}

        # Send multiple commands to increase chances of getting all data
        # The UPS often returns wrong data, so we send several and parse everything
        commands = ["?POWER", "?BATTERYSTAT", "?POWER"]

        for cmd in commands:
            response = await self.send_command(cmd)
            if response:
                # Parse any power-related data from the response, regardless of command
                for line in response.splitlines():
                    if "=" in line:
                        try:
                            key, value = line.split("=", 1)
                            key = key.strip().lstrip("$").lower()

                            # Accept any valid power data we find
                            # LOAD appears to be load percentage
                            if key in [
                                "volts_in",
                                "volts_out",
                                "watts",
                                "current",
                                "battery",
                                "load",
                            ]:
                                collected_data[key] = float(value.strip())
                                _LOGGER.debug(
                                    f"Collected {key}={collected_data[key]} from {cmd}"
                                )
                        except (ValueError, AttributeError) as e:
                            _LOGGER.debug(f"Could not parse line '{line}': {e}")

            # Small delay between commands to let UPS process
            await asyncio.sleep(0.2)

        # Update last known data with whatever we collected
        if collected_data:
            self.last_power_data.update(collected_data)
            _LOGGER.info(
                f"Power data: {dict((k, v) for k, v in self.last_power_data.items() if v != 0.0)}"
            )
        else:
            _LOGGER.warning("No power data collected, using last known values")

        return self.last_power_data.copy()

    async def get_outlet_status(self):
        """Get outlet status."""
        data = {}
        response = await self.send_command("?OUTLETSTAT")

        if not response:
            _LOGGER.debug("No outlet status received, using last known")
            return self.last_outlet_status.copy()

        for line in response.splitlines():
            if "BANK" in line and "=" in line:
                try:
                    key, value = line.split("=", 1)
                    outlet = key.strip().lstrip("$BANK")
                    data[outlet] = value.strip()
                except ValueError:
                    pass

        if data:
            self.last_outlet_status.update(data)
            _LOGGER.debug(f"Outlet status: {data}")

        return self.last_outlet_status.copy()

    async def switch_outlet(self, outlet, state):
        """Switch outlet."""
        if not outlet.isdigit() or int(outlet) not in range(1, 5):
            _LOGGER.error(f"Invalid outlet number: {outlet}")
            return False

        state = state.upper()
        if state not in ["ON", "OFF"]:
            _LOGGER.error(f"Invalid state: {state}")
            return False

        command = f"!SWITCH {outlet} {state}"
        response = await self.send_command(command)

        # Accept response if we see the outlet mentioned at all
        if response and f"BANK{outlet}" in response:
            self.last_outlet_status[outlet] = state
            _LOGGER.info(f"Switched outlet {outlet} to {state}")
            return True

        _LOGGER.warning(f"Uncertain if outlet {outlet} switched to {state}")
        # Optimistically assume it worked
        self.last_outlet_status[outlet] = state
        return True

    async def test_connection(self):
        """Test connection."""
        _LOGGER.info(f"Testing connection to {self.host}")

        await self.disconnect()

        if not await self.connect():
            _LOGGER.error(f"Failed to connect to UPS at {self.host}")
            return False

        _LOGGER.info("Connection test successful")
        return True
