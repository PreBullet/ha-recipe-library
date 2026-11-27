"""Config flow for Recipe Library: one-step setup and the AI settings."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_AI_IMAGE, CONF_AI_TEXT, CONF_AI_VIDEO, DOMAIN, NAME


def _ai_task_selector() -> selector.EntitySelector:
    """Pick one AI Task entity.

    The list is not narrowed by the features of the entities. That filter makes
    Home Assistant import the ai_task component, which needs the packages of
    the conversation integration and is therefore not available on every
    installation. An entity that cannot do a job is reported when it is used.
    """
    # "domain" is checked by the backend too, a "filter" would only affect the UI.
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="ai_task"))


def _ai_schema() -> vol.Schema:
    """Return the AI settings form: one optional AI Task entity per job."""
    return vol.Schema(
        {
            vol.Optional(CONF_AI_TEXT): _ai_task_selector(),
            vol.Optional(CONF_AI_IMAGE): _ai_task_selector(),
            vol.Optional(CONF_AI_VIDEO): _ai_task_selector(),
        }
    )


class RecipeLibraryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow: one confirmation step."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow (the Configure button of the integration)."""
        return RecipeLibraryOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm the setup."""
        # One library per Home Assistant instance.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        # No fields: the form only shows the description and a submit button.
        return self.async_show_form(step_id="user")


class RecipeLibraryOptionsFlow(OptionsFlow):
    """Choose which AI Task entity does which import job.

    The choice is read when an import runs, so it can be changed at any time
    without reloading the integration.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the AI settings and store them."""
        if user_input is not None:
            # A cleared field is missing from the input, so "nothing chosen"
            # is simply not stored and means Home Assistant's default.
            return self.async_create_entry(data=dict(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _ai_schema(), self.config_entry.options
            ),
        )
