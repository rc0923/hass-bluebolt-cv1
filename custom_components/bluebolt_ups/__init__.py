"""The BlueBolt UPS integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BlueBoltDataUpdateCoordinator
from .telnet import BlueBoltAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BlueBolt UPS from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    api = BlueBoltAPI(entry.data["host"])

    # Validate API connection
    if not await api.test_connection():
        _LOGGER.error("Failed to connect to BlueBolt UPS at %s", entry.data["host"])
        return False

    # Create coordinator
    coordinator = BlueBoltDataUpdateCoordinator(hass, api)

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store API instance and coordinator in hass.data for other components
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Load platforms (Sensor, Switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("BlueBolt UPS successfully set up at %s", entry.data["host"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)

        if entry_data:
            api = entry_data["api"]
            _LOGGER.info("Closing connection to BlueBolt UPS at %s", entry.data["host"])
            await api.disconnect()

    return unload_ok
