"""Tests for the pure recipe library logic."""

import pytest

from custom_components.recipe_library import library as lib
from custom_components.recipe_library.library import (
    InvalidDataError,
    LimitError,
    NameExistsError,
    NotFoundError,
    RecipeLibrary,
)


def make_library() -> RecipeLibrary:
    """Return a library with a counting clock so timestamps are predictable."""
    ticks = iter(f"2026-01-01T00:00:{i:02d}+00:00" for i in range(60))
    return RecipeLibrary(now=lambda: next(ticks))


# -- tags ------------------------------------------------------------------


def test_create_tag_normalises_name():
    library = make_library()
    tag = library.create_tag("  Soßen   &  Marinaden ")
    assert tag["name"] == "Soßen & Marinaden"
    assert tag["id"]


def test_create_tag_is_idempotent_ignoring_case():
    library = make_library()
    first = library.create_tag("Pasta")
    second = library.create_tag("  pasta ")
    assert first == second
    assert len(library.snapshot()["tags"]) == 1


@pytest.mark.parametrize("name", ["", "   ", None, 5, "x" * (lib.MAX_TAG_NAME + 1)])
def test_create_tag_rejects_invalid_names(name):
    with pytest.raises(InvalidDataError):
        make_library().create_tag(name)


def test_create_tag_limit(monkeypatch):
    monkeypatch.setattr(lib, "MAX_TAGS", 2)
    library = make_library()
    library.create_tag("a")
    library.create_tag("b")
    with pytest.raises(LimitError):
        library.create_tag("c")
    # Existing names still resolve at the limit.
    assert library.create_tag("A")["name"] == "a"


def test_rename_tag_applies_to_all_recipes():
    library = make_library()
    pasta = library.create_tag("Pasta")
    soup = library.create_tag("Suppen")
    first = library.save_recipe({"title": "A", "tags": [pasta["id"], soup["id"]]})
    second = library.save_recipe({"title": "B", "tags": [pasta["id"]]})

    renamed = library.rename_tag(pasta["id"], "Nudeln")

    snapshot = library.snapshot()
    names = {t["id"]: t["name"] for t in snapshot["tags"]}
    assert renamed == {"id": pasta["id"], "name": "Nudeln"}
    assert names[pasta["id"]] == "Nudeln"
    # Recipes still reference the same id, so they show the new name.
    by_id = {r["id"]: r for r in snapshot["recipes"]}
    assert pasta["id"] in by_id[first["id"]]["tags"]
    assert by_id[second["id"]]["tags"] == [pasta["id"]]


def test_rename_tag_conflicts_and_case_change():
    library = make_library()
    pasta = library.create_tag("Pasta")
    library.create_tag("Suppen")
    with pytest.raises(NameExistsError):
        library.rename_tag(pasta["id"], "suppen")
    # Changing only the case of its own name is fine.
    assert library.rename_tag(pasta["id"], "PASTA")["name"] == "PASTA"
    assert library.rename_tag(pasta["id"], "PASTA")["name"] == "PASTA"


def test_rename_unknown_tag():
    with pytest.raises(NotFoundError):
        make_library().rename_tag("nope", "x")


def test_delete_tag_removes_it_from_recipes_but_keeps_recipes():
    library = make_library()
    pasta = library.create_tag("Pasta")
    soup = library.create_tag("Suppen")
    library.save_recipe({"title": "A", "tags": [pasta["id"], soup["id"]]})
    library.save_recipe({"title": "B", "tags": [soup["id"]]})
    library.save_recipe({"title": "C"})

    assert library.delete_tag(soup["id"]) == 2

    snapshot = library.snapshot()
    assert [t["name"] for t in snapshot["tags"]] == ["Pasta"]
    assert [r["tags"] for r in snapshot["recipes"]] == [[pasta["id"]], [], []]
    with pytest.raises(NotFoundError):
        library.delete_tag(soup["id"])


# -- recipes ---------------------------------------------------------------


def test_save_recipe_creates_and_cleans_fields():
    library = make_library()
    tag = library.create_tag("Suppen")
    recipe = library.save_recipe(
        {
            "title": "  Kürbissuppe ",
            "time": "40 Min.",
            "servings": "4",
            "tags": [tag["id"], tag["id"]],
            "ingredients": [" 1 Kürbis ", "", "  ", "1 Zwiebel"],
            "steps": ["Schneiden.", "  ", "Kochen."],
            "notes": " Mit Kernen. ",
            "source": " https://example.com/suppe ",
            "unknown_field": "ignored",
        }
    )
    assert recipe["id"]
    assert recipe["title"] == "Kürbissuppe"
    assert recipe["tags"] == [tag["id"]]
    assert recipe["ingredients"] == ["1 Kürbis", "1 Zwiebel"]
    assert recipe["steps"] == ["Schneiden.", "Kochen."]
    assert recipe["notes"] == "Mit Kernen."
    assert recipe["source"] == "https://example.com/suppe"
    assert "unknown_field" not in recipe
    assert recipe["created"] == recipe["updated"]
    assert library.get_recipe(recipe["id"]) == recipe


def test_save_recipe_update_replaces_fields_and_keeps_identity():
    library = make_library()
    tag = library.create_tag("Pasta")
    created = library.save_recipe({"title": "Alt", "tags": [tag["id"]], "notes": "x"})

    updated = library.save_recipe({"title": "Neu"}, created["id"])

    assert updated["id"] == created["id"]
    assert updated["created"] == created["created"]
    assert updated["updated"] != created["updated"]
    # All editable fields are replaced, so omitted ones are cleared.
    assert updated["title"] == "Neu"
    assert updated["tags"] == []
    assert updated["notes"] == ""
    assert len(library.snapshot()["recipes"]) == 1


def test_recipes_are_never_locked():
    """Imported and manually created recipes can always be edited and deleted."""
    library = make_library()
    imported = library.save_recipe(
        {"title": "Import", "source": "https://example.com/recipe"}
    )
    manual = library.save_recipe({"title": "Manuell"})
    for recipe in (imported, manual):
        library.save_recipe({"title": recipe["title"] + " (bearbeitet)"}, recipe["id"])
        library.delete_recipe(recipe["id"])
    assert library.snapshot()["recipes"] == []


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": 5},
        {"title": "x" * (lib.MAX_TITLE + 1)},
        {"title": "A", "time": "x" * (lib.MAX_SHORT + 1)},
        {"title": "A", "notes": "x" * (lib.MAX_NOTES + 1)},
        {"title": "A", "source": "x" * (lib.MAX_SOURCE + 1)},
        {"title": "A", "ingredients": "not a list"},
        {"title": "A", "ingredients": [1, 2]},
        {"title": "A", "ingredients": ["x"] * (lib.MAX_LINES + 1)},
        {"title": "A", "steps": ["x" * (lib.MAX_LINE + 1)]},
        {"title": "A", "tags": ["unknown"]},
        {"title": "A", "tags": "pasta"},
    ],
)
def test_save_recipe_rejects_invalid_data(fields):
    library = make_library()
    with pytest.raises(InvalidDataError):
        library.save_recipe(fields)
    assert library.snapshot()["recipes"] == []


def test_failed_update_changes_nothing():
    library = make_library()
    recipe = library.save_recipe({"title": "Gut"})
    with pytest.raises(InvalidDataError):
        library.save_recipe({"title": ""}, recipe["id"])
    assert library.get_recipe(recipe["id"]) == recipe


def test_recipe_limit(monkeypatch):
    monkeypatch.setattr(lib, "MAX_RECIPES", 1)
    library = make_library()
    first = library.save_recipe({"title": "A"})
    with pytest.raises(LimitError):
        library.save_recipe({"title": "B"})
    # Editing an existing recipe is still possible at the limit.
    library.save_recipe({"title": "A2"}, first["id"])


def test_unknown_recipe():
    library = make_library()
    with pytest.raises(NotFoundError):
        library.get_recipe("nope")
    with pytest.raises(NotFoundError):
        library.save_recipe({"title": "A"}, "nope")
    with pytest.raises(NotFoundError):
        library.delete_recipe("nope")


def test_snapshot_is_a_copy():
    library = make_library()
    tag = library.create_tag("Pasta")
    library.save_recipe({"title": "A", "tags": [tag["id"]]})
    snapshot = library.snapshot()
    snapshot["recipes"][0]["tags"].append("x")
    snapshot["recipes"][0]["title"] = "changed"
    snapshot["tags"][0]["name"] = "changed"
    assert library.snapshot()["recipes"][0]["title"] == "A"
    assert library.snapshot()["recipes"][0]["tags"] == [tag["id"]]
    assert library.snapshot()["tags"][0]["name"] == "Pasta"


# -- persistence -----------------------------------------------------------


def test_as_dict_roundtrip():
    library = make_library()
    tag = library.create_tag("Pasta")
    library.save_recipe({"title": "A", "tags": [tag["id"]], "ingredients": ["x"]})
    data = library.as_dict()
    assert data["version"] == lib.DATA_VERSION
    assert RecipeLibrary(data).as_dict() == data


def test_load_is_tolerant_and_keeps_recipes():
    data = {
        "version": 1,
        "tags": [
            {"id": "t1", "name": "Pasta"},
            {"id": 5, "name": "broken"},
            "garbage",
        ],
        "recipes": [
            {
                "id": "r1",
                "title": "Alt",
                "tags": ["t1", "t1", "gone"],
                "ingredients": ["a", 5, None],
            },
            {"id": "r2"},
            {"title": "no id"},
            "garbage",
        ],
    }
    snapshot = RecipeLibrary(data).snapshot()
    assert snapshot["tags"] == [{"id": "t1", "name": "Pasta"}]
    assert [r["id"] for r in snapshot["recipes"]] == ["r1", "r2"]
    first, second = snapshot["recipes"]
    assert first["tags"] == ["t1"]
    assert first["ingredients"] == ["a"]
    assert second["title"] == "?"


def test_load_does_not_enforce_limits(monkeypatch):
    """Lowering a limit later must never make stored recipes disappear."""
    library = make_library()
    library.save_recipe({"title": "A"})
    library.save_recipe({"title": "B"})
    monkeypatch.setattr(lib, "MAX_RECIPES", 1)
    assert len(RecipeLibrary(library.as_dict()).snapshot()["recipes"]) == 2
