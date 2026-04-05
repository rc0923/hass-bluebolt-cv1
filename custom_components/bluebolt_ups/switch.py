"""Switch platform for BlueBolt UPS."""

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up UPS outlet switches."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api = entry_data["api"]
    coordinator = entry_data["coordinator"]

    switches = [
        UPSOutletSwitch(coordinator, api, str(outlet)) for outlet in range(1, 5)
    ]

    async_add_entities(switches, False)


class UPSOutletSwitch(CoordinatorEntity, SwitchEntity):
    """UPS Outlet Switch."""

    _attr_should_poll = False
    _attr_force_update = True

    def __init__(self, coordinator, api, outlet):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api = api
        self._outlet = outlet
        self._attr_name = f"UPS Outlet {outlet}"
        self._attr_unique_id = f"ups_outlet_{outlet}"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        # Get outlet statuses from coordinator data
        if self.coordinator.data and "outlet_status" in self.coordinator.data:
            outlet_status = self.coordinator.data["outlet_status"]
            if self._outlet in outlet_status:
                return outlet_status[self._outlet] == "ON"
        return None

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        success = await self._api.switch_outlet(self._outlet, "ON")
        if success:
            # Request refresh from coordinator after state change
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        success = await self._api.switch_outlet(self._outlet, "OFF")
        if success:
            # Request refresh from coordinator after state change
            await self.coordinator.async_request_refresh()
