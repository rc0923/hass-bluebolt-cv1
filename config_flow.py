"""Config flow for BlueBolt UPS integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from .const import DOMAIN
from .telnet import BlueBoltAPI

_LOGGER = logging.getLogger(__name__)


class BlueBoltConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BlueBolt UPS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            ups_ip = user_input["host"]

            # Test the connection
            api = BlueBoltAPI(ups_ip)
            if await api.test_connection():
                await api.disconnect()
                return self.async_create_entry(
                    title=f"BlueBolt UPS ({ups_ip})", data=user_input
                )
            else:
                errors["base"] = "cannot_connect"

        # Show input form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str}),
            errors=errors,
        )
