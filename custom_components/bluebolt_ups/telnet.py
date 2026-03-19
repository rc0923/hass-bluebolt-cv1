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
        self.running = False
        self.last_outlet_status = {}
        self.last_power_data = {
            "volts_in": 0.0,
            "volts_out": 0.0,
            "watts": 0.0,
            "current": 0.0,
            "battery": 0.0,
        }
        self.last_connection_attempt = None
        self.connection_retry_interval = 10
        self.connection_timeout = 10
        self.polling_task = None

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
            await asyncio.sleep(0.5)
            initial_data = await self.reader.read(1024)
            _LOGGER.debug(f"Initial data: {initial_data!r}")

            # Try multiple commands to verify connection works
            # The UPS sometimes responds with wrong data, so we'll try a few times
            _LOGGER.debug(
                "Verifying connection (UPS may respond with unexpected data)..."
            )

            for attempt in range(3):
                # Try sending a simple command
                test_command = "?POWER" if attempt == 0 else "?OUTLETSTAT"
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
                            response_lines.append(line)
                            # Accept any valid-looking response from the UPS
                            if "=" in line and line.startswith("$"):
                                # This looks like valid UPS data
                                break
                        except UnicodeDecodeError:
                            pass
                    except asyncio.TimeoutError:
                        break

                response = "\n".join(response_lines)
                _LOGGER.debug(f"Attempt {attempt + 1} response: {response!r}")

                # Check if we got any valid response (anything with $ and =)
                if response and "=" in response and "$" in response:
                    _LOGGER.info(
                        f"Successfully connected to BlueBolt UPS (verified on attempt {attempt + 1})"
                    )
                    return True

                # Short delay before retry
                await asyncio.sleep(0.5)

            # If we got here, no valid responses
            _LOGGER.error("No valid responses from UPS after 3 attempts")
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

    async def send_command(self, command, timeout=5, retries=2):
        """Send a command and return the response.

        Note: The UPS sometimes responds with data from a different command.
        We'll try multiple times and accept any valid-looking response.
        """
        async with self.lock:
            for retry in range(retries):
                if not self.writer or not self.reader:
                    if not await self.connect():
                        return None

                try:
                    _LOGGER.debug(f"Sending: {command} (attempt {retry + 1}/{retries})")
                    self.writer.write(f"{command}\r\n".encode("ascii"))
                    await self.writer.drain()

                    response_lines = []
                    start_time = asyncio.get_event_loop().time()
                    expected_complete = False

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
                                _LOGGER.debug(f"Received: {line}")

                                # Only add valid-looking lines
                                if line and "=" in line:
                                    response_lines.append(line)

                                # Check for expected completion markers
                                if command == "?POWER" and "CURRENT" in line:
                                    expected_complete = True
                                    break
                                elif command == "?OUTLETSTAT" and "BANK4" in line:
                                    expected_complete = True
                                    break
                                elif command.startswith("!SWITCH") and "BANK" in line:
                                    expected_complete = True
                                    break

                            except UnicodeDecodeError:
                                pass

                        except asyncio.TimeoutError:
                            # If we have some response lines, that might be enough
                            if response_lines:
                                break

                    response = "\n".join(response_lines)

                    # If we got the expected response, return it
                    if expected_complete:
                        _LOGGER.debug(f"Got expected response for {command}")
                        return response

                    # If we got any valid response, check if it's acceptable
                    if response:
                        # For ?POWER, accept any response with power-related keys
                        if command == "?POWER" and any(
                            key in response for key in ["VOLTS", "WATTS", "CURRENT", "BATTERY"]
                        ):
                            _LOGGER.debug(
                                f"Got valid power data (may not be from this exact command)"
                            )
                            return response
                        # For ?OUTLETSTAT, accept any response with BANK data
                        elif command == "?OUTLETSTAT" and "BANK" in response:
                            _LOGGER.debug(
                                f"Got valid outlet data (may not be from this exact command)"
                            )
                            return response
                        # For switch commands, accept if we see BANK in response
                        elif command.startswith("!SWITCH") and "BANK" in response:
                            return response

                    # If this isn't the last retry, try again
                    if retry < retries - 1:
                        _LOGGER.warning(
                            f"Unexpected response for {command}, retrying..."
                        )
                        await asyncio.sleep(0.5)
                    else:
                        # Last retry - return whatever we got
                        _LOGGER.warning(
                            f"Got unexpected response after {retries} attempts: {response!r}"
                        )
                        return response if response else None

                except Exception as e:
                    _LOGGER.error(f"Error sending command: {e}", exc_info=True)
                    await self.disconnect()
                    if retry < retries - 1:
                        await asyncio.sleep(1)
                    else:
                        return None

            return None

    async def get_power_status(self):
        """Get power status."""
        data = {}
        response = await self.send_command("?POWER")

        if not response:
            return self.last_power_data.copy()

        for line in response.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip().lstrip("$").lower()
                try:
                    if key in ["volts_in", "volts_out", "watts", "current", "battery"]:
                        data[key] = float(value.strip())
                except ValueError:
                    pass

        if data:
            self.last_power_data.update(data)
        return self.last_power_data.copy()

    async def get_outlet_status(self):
        """Get outlet status."""
        data = {}
        response = await self.send_command("?OUTLETSTAT")

        if not response:
            return self.last_outlet_status.copy()

        for line in response.splitlines():
            if "BANK" in line and "=" in line:
                key, value = line.split("=", 1)
                outlet = key.strip().lstrip("$BANK")
                data[outlet] = value.strip()

        if data:
            self.last_outlet_status.update(data)
        return self.last_outlet_status.copy()

    async def switch_outlet(self, outlet, state):
        """Switch outlet."""
        if not outlet.isdigit() or int(outlet) not in range(1, 5):
            return False

        state = state.upper()
        if state not in ["ON", "OFF"]:
            return False

        response = await self.send_command(f"!SWITCH {outlet} {state}")

        if response and f"BANK{outlet}={state}" in response:
            self.last_outlet_status[outlet] = state
            return True
        return False

    async def test_connection(self):
        """Test connection."""
        _LOGGER.info(f"Testing connection to {self.host}")

        await self.disconnect()

        if not await self.connect():
            _LOGGER.error(f"Failed to connect to UPS at {self.host}")
            return False

        _LOGGER.info("Connection test successful")
        return True

    async def start_polling(self, interval=30):
        """Start polling."""
        self.running = True

        async def polling_task():
            _LOGGER.info("Starting polling")
            while self.running:
                try:
                    await self.get_power_status()
                    await self.get_outlet_status()
                    await asyncio.sleep(interval)
                except Exception as e:
                    _LOGGER.error(f"Polling error: {e}")
                    await asyncio.sleep(5)

        self.polling_task = asyncio.create_task(polling_task())
        return True

    async def stop_polling(self):
        """Stop polling."""
        self.running = False
        if self.polling_task:
            try:
                self.polling_task.cancel()
                await asyncio.wait_for(self.polling_task, timeout=1)
            except asyncio.TimeoutError, asyncio.CancelledError:
                pass
            self.polling_task = None
