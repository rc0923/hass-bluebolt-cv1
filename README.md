# BlueBolt CV1 UPS Home Assistant Integration

A custom Home Assistant integration for BlueBolt UPS systems that provides real-time monitoring and control of your UPS via Telnet.
This integration was only tested with a BlueBolt-CV1 network card in a FURMAN F-1500UPS. It uses Telnet for communication and I am not sure if the commands it sends will work on a different UPS but feel free to test it out and let me know. May also work with a CV-2 card as according to documentation that card can also use Telnet communication.
WARNING: I AM NOT A DEVELOPER. I code sometimes as a hobby and not very well. This project was 99.8 percent vibe coded. I created it because there is no other integration.

## Features

- **Real-time(ish) Monitoring**
  - Input voltage
  - Output voltage
  - Power consumption (watts)
  - Current draw (amps)
  - Battery level (%)

- **Outlet Control**
  - Control up to 4 outlets (on/off)
  - Real-time outlet status

- **Communication**
  - Async-based communication using Python asyncio
  - Automatic retry logic for unreliable UPS responses
  - Persistent connection management with automatic reconnection

## Installation

### HACS

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Install
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/bluebolt_ups` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "BlueBolt UPS"
4. Enter the IP address of your BlueBolt UPS
5. Click **Submit**

The integration will automatically discover and create sensors and switches for your UPS.

## Entities Created

### Sensors

- `sensor.ups_watts` - Current power consumption in watts
- `sensor.ups_input_voltage` - Input voltage
- `sensor.ups_output_voltage` - Output voltage
- `sensor.ups_current` - Current draw in amps
- `sensor.ups_battery_level` - Battery level percentage

### Switches

On my UPS these are actually banks of (2) outlets. May rename "outlet" to "bank" in a future update

- `switch.ups_outlet_1` - Control outlet 1
- `switch.ups_outlet_2` - Control outlet 2
- `switch.ups_outlet_3` - Control outlet 3
- `switch.ups_outlet_4` - Control outlet 4

## Known Limitations

- There is some wacky Telnet behavior and sometimes the UPS responds with data from a different command than requested. This happens even on manual Telnet sessions.
- The integration includes automatic retry logic in an attempt to handle
- You will see warnings in the logs about "unexpected responses"

## Troubleshooting

### Connection Issues

1. Verify the UPS IP address is correct
2. Ensure port 23 (Telnet) is accessible on your network
3. Check Home Assistant logs for detailed error messages
4. Try connecting manually via Telnet to verify the UPS is responsive:
```bash
   telnet <UPS_IP> 23
```

## Development

This integration uses:
- Python asyncio for asynchronous communication
- Home Assistant's DataUpdateCoordinator for efficient polling
- Config flow for easy setup

### Communication Protocol

The integration communicates with the UPS via Telnet on port 23 using the following commands:

- `?POWER` - Retrieve power metrics (volts, watts, current)
- `?BATTERYSTAT` - Retrieve battery percentage
- `?OUTLETSTAT` - Retrieve outlet status
- `!SWITCH <outlet> <ON|OFF>` - Control outlet state

### Update Frequency

- Sensors poll every 30 seconds (configurable in coordinator)
- Switches update immediately after state changes

**Note**: This is an unofficial integration and contains heavy AI code.