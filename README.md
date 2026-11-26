# ha-recipe-library

Simple recipe library for Home Assistant: enter recipes, organise them with your own categories and browse them in a dashboard card. AI-assisted import from websites, YouTube and social media is planned (see the [roadmap](#roadmap)).

> **Status: v0.3.0, stage 1.** Storage, manual entry, photos, categories, search, filter, edit/delete and the dashboard card work. **Import is not available yet.**

## What it is

A small, focused library for recipes you want to keep:

- **Add recipes by hand**: title, an optional photo, time, servings, ingredients (one per line), instructions (one step per paragraph), notes and a source link or note.
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
- **Photo**: in the edit form tap **Choose photo** (on a phone this offers the camera or the gallery). The photo is shrunk in your browser before it is uploaded, so large camera pictures are fine. Use **Change photo** or **Remove photo** later. Recipes without a photo show a neutral placeholder.
- **Filter**: tap one or more category chips. A recipe has to match **all** selected categories. **All** clears the filter.
- **Search**: finds text in the title, ingredients, notes and category names, together with the selected filters.
- **Categories**: the tag button in the header opens the category list. There you can create, rename and delete categories. A rename applies immediately to all recipes and to the filter chips. Deleting a category only removes it from the recipes; the recipes stay. New categories can also be created while editing a recipe.
- **Edit / delete**: open a recipe and use the pencil or the bin. Deleting asks for confirmation.

## Theme and appearance

The card has no colours of its own. It only uses these Home Assistant theme variables (with neutral fallbacks if one is missing), so any theme works without extra configuration:

`--primary-color`, `--text-primary-color`, `--primary-text-color`, `--secondary-text-color`, `--ha-card-background` / `--card-background-color`, `--secondary-background-color`, `--divider-color`, `--error-color`

Tile and field backgrounds are derived from the text and card colours, the accent colour comes from `--primary-color`. The font is inherited from Home Assistant. The card loads no external fonts or scripts, and its images come only from your own Home Assistant.

## Dependencies

- **Other cards or custom integrations: none.** No HACS frontend card, no `card-mod`, no extra dashboard resource.
- **Home Assistant components:** `frontend`, `http` and `websocket_api`. They are part of every standard installation and are set up automatically.
- **Python packages:** none.
- **Network access:** none. Version 0.3.0 does not contact any external service.
- **Home Assistant version:** 2025.8 or newer. Tested with 2026.2.

When the import arrives (stage 2 and later) it will need an AI provider, and imported content will be sent to the provider you choose. That will be described here before it is released.

## Access, data and privacy

- **Who can use it:** every signed-in Home Assistant user can view, add, edit and delete recipes and categories. There is one shared library and no separate permissions. Admin rights are not needed.
- **Where the data lives:** in the Home Assistant storage file `.storage/recipe_library` of your configuration folder. Photos are stored next to it in the folder `.storage/recipe_library_images/`. Both are included in normal Home Assistant backups. Do not edit these files while Home Assistant is running.
- **Authentication:** the recipe texts are only transferred over Home Assistant's authenticated WebSocket connection. Like the other frontend files, the card's JavaScript file is served without authentication; it contains no recipe data.
- **Photos are the exception.** A browser cannot send the Home Assistant login along with an image tag, so photos are served at `/api/recipe_library/image/<random id>.jpg` **without authentication**. The id is a random 128 bit value that cannot be guessed, and photos are never listed anywhere, but anyone who knows the exact URL can open that one photo, including from outside your network if your Home Assistant is reachable from the internet. Home Assistant's own image upload works the same way. Do not upload pictures you consider private. Deleting a photo, or the recipe it belongs to, deletes the file, and the old URL stops working.
- **Photo privacy:** the card re-encodes every photo in the browser (longest side 960 px, JPEG). That removes metadata such as the camera, date and GPS location. The server additionally checks that an upload really is a JPEG, PNG or WebP image of at most 2 MB and serves it with headers that stop browsers from running it as anything else.
- **Cleanup:** photos that no recipe uses (for example after an upload that was never saved) are removed at startup once they are older than 24 hours.
- **Limits:** up to 1000 recipes and 100 categories, one photo per recipe, with length limits on all text fields.
- **No telemetry.**

## WebSocket API

For other cards or scripts. All commands need an authenticated Home Assistant WebSocket connection.

| Command                          | Fields                                                                                       | Result                                  |
| -------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------- |
| `recipe_library/subscribe`       |                                                                                              | Events with `{tags, recipes}` now and after every change |
| `recipe_library/recipe/save`     | `title` (required), `recipe_id` (to edit), `time`, `servings`, `tags` (ids), `ingredients`, `steps`, `notes`, `source`, `image` (file name from `image/upload`, empty for no photo) | The saved recipe; all fields are replaced when editing |
| `recipe_library/recipe/delete`   | `recipe_id`                                                                                  |                                         |
| `recipe_library/tag/create`      | `name`                                                                                       | The tag (existing one if the name is taken) |
| `recipe_library/tag/rename`      | `tag_id`, `name`                                                                             | The tag                                 |
| `recipe_library/tag/delete`      | `tag_id`                                                                                     | `{affected: <number of recipes>}`       |
| `recipe_library/image/upload`    | `data` (base64 of a JPEG, PNG or WebP, at most 2 MB)                                          | `{image: <file name>}`, to be used in `recipe/save` |
| `recipe_library/image/discard`   | `image` (file name)                                                                          | Deletes an uploaded photo that no recipe uses |

A recipe's `image` field holds a file name; the photo itself is at `/api/recipe_library/image/<file name>`. Errors use the codes `invalid_format`, `not_found`, `name_exists`, `limit_reached` and `image_too_large`.

## Roadmap

1. **Library** (this version): storage, manual entry with photo, categories (create, rename, delete), search and filter, edit and delete, dashboard card.
2. **Website import**: structured recipe data first, AI extraction as fallback.
3. **YouTube import**: the video is read directly by the AI provider.
4. **TikTok and Instagram**: best effort, because downloading these videos is often blocked. Text and image import (pasted caption, screenshot, cookbook photo) is the reliable fallback and also works for any other source.

## Development

```
custom_components/recipe_library/
  __init__.py        setup: storage, WebSocket commands, card registration
  library.py         recipes and categories, all rules (no Home Assistant imports)
  storage.py         persistence in Home Assistant storage
  images.py          photo checks and files (no Home Assistant imports)
  views.py           HTTP view that serves the photos
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

## How this was made

This integration was created with the help of AI ("vibe coding"): the code, the tests and the documentation were written together with Claude (Anthropic), guided by the repository owner. It comes with unit and integration tests, but like any software it can contain mistakes. Please keep a backup of your Home Assistant before using it, and report problems as issues. Pull requests are welcome.

## License

[MIT](LICENSE)

---

## Kurzfassung auf Deutsch

Eine schlanke Rezept-Bibliothek für Home Assistant. Rezepte lassen sich von Hand anlegen (auf Wunsch mit Foto), mit eigenen Kategorien organisieren und über eine Karte im Dashboard durchsuchen und filtern. Mehrere Kategorien pro Rezept sind möglich, eine Umbenennung wirkt sofort in allen Rezepten und Filtern. Jedes Rezept bleibt jederzeit bearbeitbar und löschbar. Der Import von Websites, YouTube und Social Media (KI-gestützt) folgt in den nächsten Stufen.

Bewusst nicht enthalten: Essensplaner, Einkaufslisten, Zeitstrahl, Zutaten-Datenbank und eine eigene Benutzerverwaltung. Zutaten sind einfache Textzeilen im Rezept. Jeder angemeldete Home-Assistant-Benutzer kann die Bibliothek nutzen.

**Installation:** per HACS als benutzerdefiniertes Repository (Kategorie *Integration*) hinzufügen, Home Assistant neu starten und unter *Einstellungen > Geräte & Dienste* die Integration *Recipe Library* anlegen. Die Karte wird von der Integration selbst bereitgestellt; es ist keine Dashboard-Ressource und keine weitere Karte nötig. Im Dashboard die Karte *Recipe Library* hinzufügen oder per YAML `type: custom:recipe-library-card` verwenden (Optionen `title`, `columns`, `height`).

**Design:** Die Karte nutzt ausschließlich Theme-Variablen von Home Assistant und passt sich dem aktiven Theme (hell, dunkel, eigene Themes) automatisch an.

**Abhängigkeiten:** keine zu anderen Karten oder Integrationen, keine Python-Pakete, kein Netzwerkzugriff. Voraussetzung sind nur die Home-Assistant-Bordmittel `frontend`, `http` und `websocket_api`.

**Fotos:** Im Bearbeiten-Formular lässt sich ein Foto wählen (am Handy Kamera oder Galerie). Es wird schon im Browser verkleinert und neu kodiert, dabei verschwinden Metadaten wie der Aufnahmeort. Achtung: Fotos werden unter einer zufälligen, nicht erratbaren URL **ohne Anmeldung** ausgeliefert (ein Bild-Tag im Browser kann die Home-Assistant-Anmeldung nicht mitsenden, wie bei der Bild-Funktion von Home Assistant selbst). Wer die genaue URL kennt, kann dieses eine Foto öffnen. Bitte keine privaten Bilder hochladen. Löscht man das Foto oder das Rezept, wird die Datei gelöscht.

**Daten:** gespeichert lokal in der Home-Assistant-Datei `.storage/recipe_library` und im Ordner `.storage/recipe_library_images/` (Fotos), beides enthalten in den normalen Backups.

**Entstehung:** Diese Integration ist mit Hilfe von KI entstanden („Vibe-Coding“, zusammen mit Claude von Anthropic). Sie ist getestet, kann aber wie jede Software Fehler enthalten. Bitte vor der Nutzung ein Backup von Home Assistant anlegen.
