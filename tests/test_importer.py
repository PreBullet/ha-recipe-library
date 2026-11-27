"""Tests for reading recipes from schema.org data of web pages."""

import json
from typing import Any

import pytest

from custom_components.recipe_library.importer import NoRecipeError, parse_recipe
from custom_components.recipe_library.library import (
    MAX_LINE,
    MAX_LINES,
    MAX_SOURCE,
    MAX_TITLE,
    RecipeLibrary,
)

URL = "https://recipes.example/pasta/tomato"


def page(*blocks: Any, attrs: str = 'type="application/ld+json"') -> str:
    """Build a page with the given JSON-LD blocks (objects or raw strings)."""
    scripts = "".join(
        f"<script {attrs}>{b if isinstance(b, str) else json.dumps(b)}</script>"
        for b in blocks
    )
    return f"<html><head><title>x</title>{scripts}</head><body>Hi</body></html>"


def recipe(**fields: Any) -> dict[str, Any]:
    """Return a minimal valid schema.org recipe, changed by ``fields``."""
    base = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Tomato pasta",
        "recipeIngredient": ["200 g pasta", "1 can tomatoes"],
        "recipeInstructions": "Boil the pasta.\nAdd the sauce.",
    }
    return {**base, **fields}


def parse(*blocks: Any, url: str = URL) -> dict[str, Any]:
    return parse_recipe(page(*blocks), url)


# -- a complete recipe


def test_reads_all_fields() -> None:
    draft = parse(
        recipe(
            name="Tomato pasta",
            description="Quick and simple.",
            totalTime="PT30M",
            recipeYield="4 servings",
            recipeIngredient=["200 g pasta", "1 can tomatoes", "Salt"],
            recipeInstructions=[
                {"@type": "HowToStep", "text": "Boil the pasta."},
                {"@type": "HowToStep", "text": "Add the sauce."},
            ],
            image="/img/pasta.jpg",
        )
    )

    assert draft == {
        "title": "Tomato pasta",
        "time": "30 min",
        "servings": "4 servings",
        "ingredients": ["200 g pasta", "1 can tomatoes", "Salt"],
        "steps": ["Boil the pasta.", "Add the sauce."],
        "notes": "Quick and simple.",
        "source": URL,
        "image_url": "https://recipes.example/img/pasta.jpg",
    }


def test_a_draft_can_be_saved_as_a_recipe() -> None:
    """The card saves the draft as it is, so it must always be valid."""
    draft = parse(recipe(totalTime="PT1H", recipeYield=["4", "4 servings"]))
    fields = {k: v for k, v in draft.items() if k != "image_url"}

    saved = RecipeLibrary().save_recipe(fields)

    assert saved["title"] == "Tomato pasta"
    assert saved["ingredients"] == draft["ingredients"]


# -- where the recipe is in the data


def test_finds_the_recipe_in_a_graph() -> None:
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": "Recipes"},
            {"@type": "Article", "name": "A blog post"},
            recipe(name="From the graph"),
        ],
    }
    assert parse(graph)["title"] == "From the graph"


@pytest.mark.parametrize(
    "kind",
    [["Recipe", "NewsArticle"], "http://schema.org/Recipe", "schema:Recipe", "recipe"],
)
def test_accepts_the_ways_a_type_is_written(kind: Any) -> None:
    assert parse(recipe(**{"@type": kind}))["title"] == "Tomato pasta"


def test_finds_the_recipe_in_a_list_and_in_nested_data() -> None:
    assert (
        parse([{"@type": "WebSite"}, recipe(name="In a list")])["title"] == "In a list"
    )
    nested = {"@type": "WebPage", "mainEntity": recipe(name="Nested")}
    assert parse(nested)["title"] == "Nested"


def test_uses_the_first_complete_recipe_of_the_page() -> None:
    empty = {"@type": "Recipe", "name": "Only a name"}
    draft = parse(
        empty, recipe(name="First", recipeInstructions="One."), recipe(name="Second")
    )
    assert draft["title"] == "First"


def test_survives_broken_and_unrelated_blocks() -> None:
    html = page(
        "{ this is not json",
        {"@type": "Organization", "name": "Shop"},
        recipe(name="Still found"),
    )
    assert parse_recipe(html, URL)["title"] == "Still found"


def test_accepts_raw_line_breaks_inside_strings() -> None:
    raw = (
        '{"@type": "Recipe", "name": "Soup", "recipeIngredient": ["1 l water"],'
        ' "recipeInstructions": "Boil.\nServe."}'
    )
    assert parse(raw)["steps"] == ["Boil.", "Serve."]


def test_accepts_a_cdata_wrapper() -> None:
    wrapped = "/*<![CDATA[*/" + json.dumps(recipe(name="Wrapped")) + "/*]]>*/"
    assert parse(wrapped)["title"] == "Wrapped"


@pytest.mark.parametrize(
    "attrs",
    [
        "type='application/ld+json'",
        'TYPE="application/ld+json"',
        'class="x" type="application/ld+json" id="schema"',
        "type=application/ld+json",
    ],
)
def test_accepts_the_ways_a_script_tag_is_written(attrs: str) -> None:
    assert parse_recipe(page(recipe(), attrs=attrs), URL)["title"] == "Tomato pasta"


def test_ignores_other_scripts() -> None:
    html = page(recipe(), attrs='type="application/json"')
    with pytest.raises(NoRecipeError):
        parse_recipe(html, URL)


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<html><body>No data here</body></html>",
        page({"@type": "Article", "name": "Not a recipe"}),
        page({"@type": "Recipe", "name": "No ingredients or steps"}),
        page(recipe(name="")),
        page("[]"),
    ],
)
def test_raises_when_there_is_no_usable_recipe(html: str) -> None:
    with pytest.raises(NoRecipeError) as error:
        parse_recipe(html, URL)
    assert error.value.code == "no_recipe"


def test_deeply_nested_data_is_not_followed_forever() -> None:
    node: dict[str, Any] = recipe()
    for _ in range(60):
        node = {"@type": "Thing", "child": node}
    with pytest.raises(NoRecipeError):
        parse(node)


# -- instructions


def test_instructions_as_text_are_split_into_steps() -> None:
    draft = parse(recipe(recipeInstructions="1. Mix.\n\n2. Bake.<br>3. Serve."))
    assert draft["steps"] == ["1. Mix.", "2. Bake.", "3. Serve."]


def test_instructions_as_list_of_texts() -> None:
    assert parse(recipe(recipeInstructions=["Mix.", "Bake."]))["steps"] == [
        "Mix.",
        "Bake.",
    ]


def test_instructions_in_sections_are_flattened() -> None:
    instructions = [
        {
            "@type": "HowToSection",
            "name": "Dough",
            "itemListElement": [
                {"@type": "HowToStep", "text": "Knead."},
                {"@type": "HowToStep", "text": "Rest."},
            ],
        },
        {
            "@type": "HowToSection",
            "name": "Topping",
            "itemListElement": [{"@type": "HowToStep", "text": "Add cheese."}],
        },
    ]
    steps = parse(recipe(recipeInstructions=instructions))["steps"]
    assert steps == ["Knead.", "Rest.", "Add cheese."]


def test_a_step_without_text_falls_back_to_its_name() -> None:
    draft = parse(recipe(recipeInstructions=[{"@type": "HowToStep", "name": "Stir."}]))
    assert draft["steps"] == ["Stir."]


# -- text cleanup


def test_html_entities_and_tags_become_plain_text() -> None:
    draft = parse(
        recipe(
            name="Mac &amp; Cheese &#39;classic&#39;",
            recipeIngredient=[
                "2&nbsp;cups <b>macaroni</b>",
                "  1   tsp   salt  ",
                "",
                " ",
            ],
            recipeInstructions="<p>Boil &amp; drain.</p><p>Mix\xa0well.</p>",
        )
    )
    assert draft["title"] == "Mac & Cheese 'classic'"
    assert draft["ingredients"] == ["2 cups macaroni", "1 tsp salt"]
    assert draft["steps"] == ["Boil & drain.", "Mix well."]


def test_escaped_markup_is_removed_too() -> None:
    draft = parse(recipe(recipeInstructions="&lt;p&gt;Bake.&lt;/p&gt;"))
    assert draft["steps"] == ["Bake."]


def test_a_lone_less_than_sign_is_kept() -> None:
    draft = parse(recipe(recipeInstructions="Bake while the oven is <100 °C and stir."))
    assert draft["steps"] == ["Bake while the oven is <100 °C and stir."]


# -- time and servings


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"totalTime": "PT45M"}, "45 min"),
        ({"totalTime": "PT1H30M"}, "1 h 30 min"),
        ({"totalTime": "PT90M"}, "1 h 30 min"),
        ({"totalTime": "PT2H"}, "2 h"),
        ({"totalTime": "P0DT2H"}, "2 h"),
        ({"totalTime": "P1DT2H15M"}, "1 d 2 h 15 min"),
        ({"totalTime": "pt20m"}, "20 min"),
        ({"prepTime": "PT15M", "cookTime": "PT45M"}, "1 h"),
        ({"prepTime": "PT15M"}, "15 min"),
        ({"cookTime": "PT25M"}, "25 min"),
        ({"totalTime": "PT10M", "prepTime": "PT15M", "cookTime": "PT45M"}, "10 min"),
        ({"totalTime": "about 30 minutes"}, "about 30 minutes"),
        ({"totalTime": "PT0M"}, ""),
        ({"totalTime": 30}, ""),
        ({}, ""),
    ],
)
def test_time(fields: dict[str, Any], expected: str) -> None:
    assert parse(recipe(**fields))["time"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", "4"),
        (4, "4"),
        (4.0, "4.0"),
        ("4 servings", "4 servings"),
        (["4", "4 servings"], "4"),
        (["", "6 pieces"], "6 pieces"),
        ([], ""),
        (None, ""),
        ({"x": 1}, ""),
    ],
)
def test_servings(value: Any, expected: str) -> None:
    assert parse(recipe(recipeYield=value))["servings"] == expected


# -- images


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("https://cdn.example/a.jpg", "https://cdn.example/a.jpg"),
        (
            ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"],
            "https://cdn.example/a.jpg",
        ),
        (
            {"@type": "ImageObject", "url": "https://cdn.example/a.jpg"},
            "https://cdn.example/a.jpg",
        ),
        ([{"@type": "ImageObject", "url": "/a.jpg"}], "https://recipes.example/a.jpg"),
        ("a.jpg", "https://recipes.example/pasta/a.jpg"),
        ("//cdn.example/a.jpg", "https://cdn.example/a.jpg"),
        ("javascript:alert(1)", ""),
        ("data:image/png;base64,AAAA", ""),
        ("ftp://files.example/a.jpg", ""),
        ("", ""),
        (None, ""),
        (123, ""),
    ],
)
def test_image_url(image: Any, expected: str) -> None:
    assert parse(recipe(image=image))["image_url"] == expected


def test_thumbnail_is_used_when_there_is_no_image() -> None:
    draft = parse(recipe(thumbnailUrl="https://cdn.example/t.jpg"))
    assert draft["image_url"] == "https://cdn.example/t.jpg"


# -- limits


def test_texts_are_cut_to_the_limits_of_the_library() -> None:
    draft = parse(
        recipe(
            name="T" * (MAX_TITLE + 50),
            recipeIngredient=["x" * (MAX_LINE + 10)] * (MAX_LINES + 20),
            recipeInstructions=["s" * (MAX_LINE + 10)] * (MAX_LINES + 20),
            description="d" * 10000,
            recipeYield="y" * 500,
            totalTime="t" * 500,
        )
    )

    assert len(draft["title"]) <= MAX_TITLE
    assert len(draft["ingredients"]) == MAX_LINES
    assert all(len(line) <= MAX_LINE for line in draft["ingredients"])
    assert len(draft["steps"]) == MAX_LINES
    assert len(draft["notes"]) <= 5000
    assert len(draft["servings"]) <= 100
    assert len(draft["time"]) <= 100
    RecipeLibrary().save_recipe({k: v for k, v in draft.items() if k != "image_url"})


def test_a_very_long_page_address_is_not_taken_as_source() -> None:
    url = "https://recipes.example/" + "a" * MAX_SOURCE
    assert parse(recipe(), url=url)["source"] == ""
