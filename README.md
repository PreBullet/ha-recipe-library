# ha-recipe-library

Simple recipe library for Home Assistant: enter recipes, organise them with your own categories and browse them in a dashboard card. AI-assisted import from websites, YouTube and social media is planned (see the [roadmap](#roadmap)).

> **Status: v0.2.0, stage 1.** Storage, manual entry, categories, search, filter, edit/delete and the dashboard card work. **Import is not available yet.**

## What it is

A small, focused library for recipes you want to keep:

- **Add recipes by hand**: title, time, servings, ingredients (one per line), instructions (one step per paragraph), notes and a source link or note.
- **Browse** them in a library card on your dashboard, with search and filtering by category.
- **Organise** with categories (tags) you define yourself, for example *Pasta*, *Sauces & marinades*, *Braised dishes*. A recipe can have several. Renaming a category updates every recipe and filter that uses it.
- **Edit and delete** any recipe at any time. Nothing is locked, whether a recipe was imported later on or entered by hand.
- **Looks like your Home Assistant**: the card uses the active theme (light, dark, custom) and follows it when it changes.

## What it deliberately is not

No meal planner, no shopping lists, no timeline, no ingredient database, and no separate login or user management. Ingredients are plain text lines inside each recipe.

## Installation

### HACS (custom repository)

1. In HACS open the menu (three dots) and choose **Custom repositories**.
2. Add `https://github.com/PreBullet/ha-recipe-library` with the category **Integration**.
3. Download **Recipe Library** and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and add **Recipe Library**.

### Manual

Copy the folder `custom_components/recipe_library` into the `custom_components` folder of your Home Assistant configuration, restart, then add the integration as in step 4 above.

### Add the card to a dashboard

The integration serves and registers the card itself. You do **not** need to add a dashboard resource and you do not need to install a separate card.

1. Edit a dashboard, choose **Add card** and pick **Recipe Library** (or use the YAML below).
2. If the card is not listed right after installing, reload the browser page (hard refresh).

```yaml
type: custom:recipe-library-card
```

## Card options

| Option    | Default              | Description                                                              |
| --------- | -------------------- | ------------------------------------------------------------------------ |
| `title`   | `Recipes` / `Rezepte` | Heading of the card. Use your own text, or an empty string to hide it.   |
| `columns` | `2`                  | Recipe tiles per row, 1 to 6.                                            |
| `height`  | `min(78vh, 720px)`   | Card height: a number (pixels) or any CSS length such as `600px` or `70vh`. |

```yaml
type: custom:recipe-library-card
title: Cookbook
columns: 3
height: 640
```

The card is available in English and German and uses your Home Assistant language. Other languages show English.

## Using the library

- **Add**: tap **+**. Only the title is required.
- **Filter**: tap one or more category chips. A recipe has to match **all** selected categories. **All** clears the filter.
- **Search**: finds text in the title, ingredients, notes and category names, together with the selected filters.
- **Categories**: the tag button in the header opens the category list. There you can create, rename and delete categories. A rename applies immediately to all recipes and to the filter chips. Deleting a category only removes it from the recipes; the recipes stay. New categories can also be created while editing a recipe.
- **Edit / delete**: open a recipe and use the pencil or the bin. Deleting asks for confirmation.

## Theme and appearance

The card has no colours of its own. It only uses these Home Assistant theme variables (with neutral fallbacks if one is missing), so any theme works without extra configuration:

`--primary-color`, `--text-primary-color`, `--primary-text-color`, `--secondary-text-color`, `--ha-card-background` / `--card-background-color`, `--secondary-background-color`, `--divider-color`, `--error-color`

Tile and field backgrounds are derived from the text and card colours, the accent colour comes from `--primary-color`. The font is inherited from Home Assistant. The card loads no external fonts, images or scripts.

## Dependencies

- **Other cards or custom integrations: none.** No HACS frontend card, no `card-mod`, no extra dashboard resource.
- **Home Assistant components:** `frontend`, `http` and `websocket_api`. They are part of every standard installation and are set up automatically.
- **Python packages:** none.
- **Network access:** none. Version 0.2.0 does not contact any external service.
- **Home Assistant version:** 2025.8 or newer. Tested with 2026.2.

When the import arrives (stage 2 and later) it will need an AI provider, and imported content will be sent to the provider you choose. That will be described here before it is released.

## Access, data and privacy

- **Who can use it:** every signed-in Home Assistant user can view, add, edit and delete recipes and categories. There is one shared library and no separate permissions. Admin rights are not needed.
- **Where the data lives:** in the Home Assistant storage file `.storage/recipe_library` of your configuration folder. It is included in normal Home Assistant backups. Do not edit this file while Home Assistant is running.
- **Authentication:** the recipes are only transferred over Home Assistant's authenticated WebSocket connection. Like the other frontend files, the card's JavaScript file is served without authentication; it contains no recipe data.
- **Limits:** up to 1000 recipes and 100 categories, with length limits on all text fields.
- **No telemetry.**

## WebSocket API

For other cards or scripts. All commands need an authenticated Home Assistant WebSocket connection.

| Command                          | Fields                                                                                       | Result                                  |
| -------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------- |
| `recipe_library/subscribe`       |                                                                                              | Events with `{tags, recipes}` now and after every change |
| `recipe_library/recipe/save`     | `title` (required), `recipe_id` (to edit), `time`, `servings`, `tags` (ids), `ingredients`, `steps`, `notes`, `source` | The saved recipe; all fields are replaced when editing |
| `recipe_library/recipe/delete`   | `recipe_id`                                                                                  |                                         |
| `recipe_library/tag/create`      | `name`                                                                                       | The tag (existing one if the name is taken) |
| `recipe_library/tag/rename`      | `tag_id`, `name`                                                                             | The tag                                 |
| `recipe_library/tag/delete`      | `tag_id`                                                                                     | `{affected: <number of recipes>}`       |

Errors use the codes `invalid_format`, `not_found`, `name_exists` and `limit_reached`.

## Roadmap

1. **Library** (this version): storage, manual entry, categories (create, rename, delete), search and filter, edit and delete, dashboard card.
2. **Website import**: structured recipe data first, AI extraction as fallback.
3. **YouTube import**: the video is read directly by the AI provider.
4. **TikTok and Instagram**: best effort, because downloading these videos is often blocked. Text and image import (pasted caption, screenshot, cookbook photo) is the reliable fallback and also works for any other source.

## Development

```
custom_components/recipe_library/
  __init__.py        setup: storage, WebSocket commands, card registration
  library.py         recipes and categories, all rules (no Home Assistant imports)
  storage.py         persistence in Home Assistant storage
  ws_api.py          WebSocket commands used by the card
  config_flow.py     one-step setup, single instance
  const.py           constants
  manifest.json      integration manifest
  translations/      en, de
  frontend/          the dashboard card (one JavaScript file, no build step)
tests/               unit tests and integration tests
hacs.json            HACS metadata
```

Run the tests:

```
pip install -r requirements_test.txt
pytest
```

The card is plain JavaScript without a build step or dependencies, edit `frontend/recipe-library-card.js` directly. User content is only ever inserted as text, never as HTML.

## License

[MIT](LICENSE)

---

## Kurzfassung auf Deutsch

Eine schlanke Rezept-Bibliothek für Home Assistant. Rezepte lassen sich von Hand anlegen, mit eigenen Kategorien organisieren und über eine Karte im Dashboard durchsuchen und filtern. Mehrere Kategorien pro Rezept sind möglich, eine Umbenennung wirkt sofort in allen Rezepten und Filtern. Jedes Rezept bleibt jederzeit bearbeitbar und löschbar. Der Import von Websites, YouTube und Social Media (KI-gestützt) folgt in den nächsten Stufen.

Bewusst nicht enthalten: Essensplaner, Einkaufslisten, Zeitstrahl, Zutaten-Datenbank und eine eigene Benutzerverwaltung. Zutaten sind einfache Textzeilen im Rezept. Jeder angemeldete Home-Assistant-Benutzer kann die Bibliothek nutzen.

**Installation:** per HACS als benutzerdefiniertes Repository (Kategorie *Integration*) hinzufügen, Home Assistant neu starten und unter *Einstellungen > Geräte & Dienste* die Integration *Recipe Library* anlegen. Die Karte wird von der Integration selbst bereitgestellt; es ist keine Dashboard-Ressource und keine weitere Karte nötig. Im Dashboard die Karte *Recipe Library* hinzufügen oder per YAML `type: custom:recipe-library-card` verwenden (Optionen `title`, `columns`, `height`).

**Design:** Die Karte nutzt ausschließlich Theme-Variablen von Home Assistant und passt sich dem aktiven Theme (hell, dunkel, eigene Themes) automatisch an.

**Abhängigkeiten:** keine zu anderen Karten oder Integrationen, keine Python-Pakete, kein Netzwerkzugriff. Voraussetzung sind nur die Home-Assistant-Bordmittel `frontend`, `http` und `websocket_api`.

**Daten:** gespeichert lokal in der Home-Assistant-Datei `.storage/recipe_library`, enthalten in den normalen Backups.
