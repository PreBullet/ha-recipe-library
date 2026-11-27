"""Tests for the AI settings: which AI Task entity runs which import job."""

import json
from pathlib import Path

import pytest
import voluptuous as vol
import voluptuous_serialize
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import config_validation as cv
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.recipe_library.ai_settings import entity_for_job
from custom_components.recipe_library.const import (
    AI_JOBS,
    CONF_AI_IMAGE,
    CONF_AI_TEXT,
    CONF_AI_VIDEO,
    DOMAIN,
)

INTEGRATION = Path(__file__).parent.parent / "custom_components" / DOMAIN
TRANSLATIONS = INTEGRATION / "translations"


async def setup_entry(hass: HomeAssistant, options: dict | None = None):
    """Set up the integration with a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={}, options=options or {}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def suggested(schema) -> dict:
    """Return the suggested value of every field of a form schema."""
    return {
        str(key): (key.description or {}).get("suggested_value")
        for key in schema.schema
    }


# -- reading the choice


def test_entity_for_job_returns_the_chosen_entity() -> None:
    options = {CONF_AI_IMAGE: "ai_task.openai_images"}
    assert entity_for_job(options, CONF_AI_IMAGE) == "ai_task.openai_images"


@pytest.mark.parametrize("options", [{}, {CONF_AI_VIDEO: ""}, {CONF_AI_VIDEO: None}])
def test_entity_for_job_is_none_without_a_choice(options: dict) -> None:
    # None means: pass no entity and let Home Assistant use its default.
    assert entity_for_job(options, CONF_AI_VIDEO) is None


def test_entity_for_job_rejects_unknown_jobs() -> None:
    with pytest.raises(ValueError):
        entity_for_job({}, "ai_music")


# -- the options form


async def test_options_form_has_one_optional_field_per_job(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    fields = {str(key): key for key in result["data_schema"].schema}
    assert set(fields) == set(AI_JOBS)
    # Optional: leaving a field empty means Home Assistant's default entity.
    assert all(isinstance(key, vol.Optional) for key in fields.values())


async def test_options_form_is_serializable_and_lists_only_ai_task_entities(
    hass: HomeAssistant,
) -> None:
    """The frontend gets this structure, so it must serialize and filter."""
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    fields = voluptuous_serialize.convert(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )

    assert {f["name"] for f in fields} == set(AI_JOBS)
    for field in fields:
        assert field["selector"]["entity"]["domain"] == ["ai_task"]


def test_the_options_flow_does_not_import_the_ai_task_component() -> None:
    """Importing it needs packages of the conversation integration.

    They are not installed on every Home Assistant, which would break the
    settings dialog.
    """
    source = (INTEGRATION / "config_flow.py").read_text()
    assert "components.ai_task" not in source
    assert "supported_features" not in source


async def test_saving_stores_the_choice_per_job(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_AI_TEXT: "ai_task.text_model",
            CONF_AI_IMAGE: "ai_task.vision_model",
            CONF_AI_VIDEO: "ai_task.video_model",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_AI_TEXT: "ai_task.text_model",
        CONF_AI_IMAGE: "ai_task.vision_model",
        CONF_AI_VIDEO: "ai_task.video_model",
    }
    assert entity_for_job(entry.options, CONF_AI_VIDEO) == "ai_task.video_model"


async def test_reopening_shows_the_saved_choice_and_allows_changes(
    hass: HomeAssistant,
) -> None:
    entry = await setup_entry(
        hass, {CONF_AI_IMAGE: "ai_task.vision_a", CONF_AI_VIDEO: "ai_task.video_a"}
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert suggested(result["data_schema"]) == {
        CONF_AI_TEXT: None,
        CONF_AI_IMAGE: "ai_task.vision_a",
        CONF_AI_VIDEO: "ai_task.video_a",
    }

    # Change one job and leave another untouched.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AI_IMAGE: "ai_task.vision_b", CONF_AI_VIDEO: "ai_task.video_a"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_AI_IMAGE: "ai_task.vision_b",
        CONF_AI_VIDEO: "ai_task.video_a",
    }


async def test_clearing_every_field_goes_back_to_the_default(
    hass: HomeAssistant,
) -> None:
    entry = await setup_entry(hass, {CONF_AI_IMAGE: "ai_task.vision_a"})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    # The frontend omits cleared fields.
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {}
    assert entity_for_job(entry.options, CONF_AI_IMAGE) is None


@pytest.mark.parametrize("entity_id", ["light.kitchen", "conversation.assistant"])
async def test_only_ai_task_entities_are_accepted(
    hass: HomeAssistant, entity_id: str
) -> None:
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_AI_TEXT: entity_id}
        )

    assert entry.options == {}


async def test_changing_the_choice_does_not_reload_the_library(
    hass: HomeAssistant,
) -> None:
    """The choice is read when an import runs, so the library keeps running."""
    entry = await setup_entry(hass)
    store = hass.data[DOMAIN]
    result = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AI_TEXT: "ai_task.text_model"}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN] is store


# -- translations


@pytest.mark.parametrize("language", ["en", "de"])
def test_every_field_has_a_label_and_a_description(language: str) -> None:
    texts = json.loads((TRANSLATIONS / f"{language}.json").read_text())
    form = texts["options"]["step"]["init"]

    assert form["title"] and form["description"]
    assert set(form["data"]) == set(AI_JOBS)
    assert set(form["data_description"]) == set(AI_JOBS)
    assert all(form["data"].values()) and all(form["data_description"].values())
