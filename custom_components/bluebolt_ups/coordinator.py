"""Data update coordinator for BlueBolt UPS."""

from datetime import timedelta
from datetime import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlueBoltDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BlueBolt UPS data."""

    def __init__(self, hass: HomeAssistant, api, update_interval=timedelta(seconds=30)):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from the BlueBolt UPS."""
        try:
            outlet_status = await self.api.get_outlet_status()
            power_data = await self.api.get_power_status()

            if not isinstance(outlet_status, dict) or not isinstance(power_data, dict):
                raise UpdateFailed("Invalid data received from UPS")

            _LOGGER.debug(
                "UPS data updated - Power: %s, Outlets: %s", power_data, outlet_status
            )

            # Return combined data
            return {
                "outlet_status": outlet_status,
                "power_data": power_data,
                "last_update": datetime.now().isoformat(),
            }
        except Exception as err:
            _LOGGER.error("Error updating UPS data: %s", err)
            raise UpdateFailed(f"Error communicating with UPS: {err}")
