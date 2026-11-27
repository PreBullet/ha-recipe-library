# ha-recipe-library

Simple recipe library for Home Assistant: enter recipes, organise them with your own categories and browse them in a dashboard card. Recipes can be imported from web pages. AI-assisted import for YouTube, social media, screenshots and photos is planned (see the [roadmap](#roadmap)).

> **Status: v0.4.0.** Storage, manual entry, photos, categories, search, filter, edit/delete, the dashboard card and the [import from web pages](#import-from-a-web-page) with structured recipe data work. **AI-based import (pages without structured data, text, screenshots, YouTube) is not available yet.** The [AI settings](#ai-settings) for it can already be filled in.

## What it is

A small, focused library for recipes you want to keep:

- **Import from a web page**: paste a link, check the recipe and save it. No AI needed for the many sites that publish structured recipe data.
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
- **Import**: tap the import button in the header, see [Import from a web page](#import-from-a-web-page).
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
- **AI provider (optional, only for the coming AI import):** an integration that offers an AI Task entity, for example OpenAI, Google Gemini, Anthropic or Ollama. The library itself, photos and categories do not need it. See [AI settings](#ai-settings).
- **Python packages:** none.
- **Network access:** only when you import: Home Assistant then loads the web page you entered (and its photo). Nothing else is contacted, and there is no telemetry. See [Import from a web page](#import-from-a-web-page).
- **Home Assistant version:** 2025.8 or newer. Tested with 2026.2.

## Import from a web page

Tap the import button (arrow into a tray) in the header of the card, paste the link of a recipe page and tap **Import**. The recipe opens in the edit form so you can check and change it. **Nothing is saved until you press Save**, and cancelling throws the draft away, including its photo.

What is taken over: the title, the time (total time, or preparation plus cooking time), the servings, the ingredients, the instructions, the description (as notes), the address as source and the main photo. Categories are not set, choose them while you check the recipe.

**How it works.** Most recipe sites describe their recipes in a structured way for search engines (schema.org `Recipe` data in a `<script type="application/ld+json">` block). The import reads exactly that. **No AI is used**, so no provider is needed and nothing leaves your Home Assistant except the request for the page.

**What does not work (yet):**

- Pages without structured recipe data, pages that only show the recipe after JavaScript has run, and pages that block automated access. You get a message; the AI-based import for such pages is planned.
- Pages that only use the older microdata format.
- Photos that are not JPEG, PNG or WebP, or larger than 2 MB. The recipe is imported without a photo then.
- Pages in your own network (see below).

**Safety.** The Home Assistant server loads the address, and every signed-in user can trigger that. To keep it from being misused to reach other devices in your network, only public web pages are loaded:

- only `http` and `https` on the standard ports (80 and 443), and no addresses with a login in them,
- no addresses that lead to your own network or to Home Assistant itself (private, loopback, link-local, carrier-grade NAT and similar ranges, IPv4 and IPv6). This is checked for addresses written as numbers, for host names at the moment they are resolved (the address that is checked is the one that is connected to) and for every redirect, at most 5,
- pages up to 4 MB and photos up to 2 MB, 15 seconds per download, at most two imports at the same time,
- only the recipe data that was read is passed on, never the page itself. No cookies are kept.

A recipe site that runs on a device in your own network can therefore not be imported, enter such recipes by hand.

**Photos from the web** are stored as they were downloaded. Like all photos they are served at a random, unguessable address (see [Access, data and privacy](#access-data-and-privacy)) and they are removed when the draft is cancelled or the recipe is deleted. The shrinking and metadata removal of the browser only applies to photos you choose yourself.

## AI settings

The planned AI import does not use a fixed AI provider. It uses Home Assistant's [AI Task](https://www.home-assistant.io/integrations/ai_task/), so you decide which provider does which job. You could, for example, let one provider read videos and another one read images.

Open **Settings > Devices & services > Recipe Library > Configure** and choose an AI Task entity per job:

| Job | Meant for |
| --- | --- |
| Websites and text | recipes on web pages and pasted text |
| Images and screenshots | screenshots and photos, for example of a cookbook page |
| Videos | recipes in videos |

- **Empty field:** the preferred AI Task entity of Home Assistant is used (Settings > System > AI).
- **Change it any time:** open the form again. The choice is read when an import runs, so no restart or reload is needed.
- **Requirements:** entities for images and videos have to accept attachments, and whether a provider understands video at all depends on the provider. The list shows every AI Task entity, an entity that cannot do a job is reported when it is used.
- **Not active yet:** the import from web pages with structured data does not use AI. The choice is saved and will be used by the AI import (pages without structured data, pasted text, screenshots, videos) once it is released.
- **Privacy:** an AI import will send the imported content (page text, image or video) to the provider behind the entity you chose. The integration itself contacts nothing else.

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
| `recipe_library/import/url`      | `url` (address of a web page)                                                                | A draft `{title, time, servings, ingredients, steps, notes, source, image}`. Nothing is saved; `image` is a stored photo that no recipe uses yet, so use it in `recipe/save` or release it with `image/discard` |

A recipe's `image` field holds a file name; the photo itself is at `/api/recipe_library/image/<file name>`. Errors use the codes `invalid_format`, `not_found`, `name_exists`, `limit_reached` and `image_too_large`, and for the import `invalid_url`, `blocked_url`, `fetch_failed`, `page_too_large`, `not_html` and `no_recipe`.

## Roadmap

1. **Library**: storage, manual entry with photo, categories (create, rename, delete), search and filter, edit and delete, dashboard card. *Done.*
2. **Website import** from structured recipe data, no AI. *Done (this version).*
3. **AI import** through the AI Task entities from the AI settings: pages without structured data, pasted text, screenshots and cookbook photos.
4. **YouTube import**: uses the AI Task entity chosen for videos. How a video reaches the AI, and which providers can read video, is decided with that stage.
5. **TikTok and Instagram**: best effort, because downloading these videos is often blocked. Text and image import (pasted caption, screenshot, cookbook photo) is the reliable fallback and also works for any other source.

## Development

```
custom_components/recipe_library/
  __init__.py        setup: storage, WebSocket commands, card registration
  library.py         recipes and categories, all rules (no Home Assistant imports)
  storage.py         persistence in Home Assistant storage
  importer.py        reads a recipe from schema.org data of a page (no Home Assistant imports)
  fetch.py           safe download of pages and photos, only public addresses (no Home Assistant imports)
  web_import.py      puts the import together: download, read, store the photo
  images.py          photo checks and files (no Home Assistant imports)
  views.py           HTTP view that serves the photos
  ws_api.py          WebSocket commands used by the card
  config_flow.py     one-step setup (single instance) and the AI settings form
  ai_settings.py     which AI Task entity is chosen for which job (no Home Assistant imports)
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

Eine schlanke Rezept-Bibliothek für Home Assistant. Rezepte lassen sich von Hand anlegen (auf Wunsch mit Foto), mit eigenen Kategorien organisieren und über eine Karte im Dashboard durchsuchen und filtern. Mehrere Kategorien pro Rezept sind möglich, eine Umbenennung wirkt sofort in allen Rezepten und Filtern. Jedes Rezept bleibt jederzeit bearbeitbar und löschbar. Rezepte lassen sich von Webseiten importieren. Der KI-gestützte Import (Seiten ohne strukturierte Daten, Text, Screenshots, YouTube, Social Media) folgt in den nächsten Stufen.

Bewusst nicht enthalten: Essensplaner, Einkaufslisten, Zeitstrahl, Zutaten-Datenbank und eine eigene Benutzerverwaltung. Zutaten sind einfache Textzeilen im Rezept. Jeder angemeldete Home-Assistant-Benutzer kann die Bibliothek nutzen.

**Installation:** per HACS als benutzerdefiniertes Repository (Kategorie *Integration*) hinzufügen, Home Assistant neu starten und unter *Einstellungen > Geräte & Dienste* die Integration *Recipe Library* anlegen. Die Karte wird von der Integration selbst bereitgestellt; es ist keine Dashboard-Ressource und keine weitere Karte nötig. Im Dashboard die Karte *Recipe Library* hinzufügen oder per YAML `type: custom:recipe-library-card` verwenden (Optionen `title`, `columns`, `height`).

**Design:** Die Karte nutzt ausschließlich Theme-Variablen von Home Assistant und passt sich dem aktiven Theme (hell, dunkel, eigene Themes) automatisch an.

**Abhängigkeiten:** keine zu anderen Karten oder Integrationen, keine Python-Pakete, Netzwerkzugriff nur beim Import (die eingegebene Webseite und ihr Foto). Voraussetzung sind nur die Home-Assistant-Bordmittel `frontend`, `http` und `websocket_api`. Nur für den kommenden KI-Import wird optional ein KI-Anbieter mit AI-Task-Entität gebraucht (z. B. OpenAI, Google Gemini, Anthropic oder Ollama).

**Import von Webseiten:** Über den Import-Knopf im Kartenkopf einen Link einfügen. Das Rezept öffnet sich zum Prüfen im Bearbeiten-Formular und wird erst mit *Speichern* abgelegt. Gelesen werden die strukturierten Rezeptdaten (schema.org, JSON-LD), die die meisten Rezeptseiten für Suchmaschinen bereitstellen. Es wird **keine KI** benötigt. Nicht unterstützt: Seiten ohne solche Daten, Seiten die das Rezept erst per JavaScript anzeigen oder automatische Abrufe blockieren, und Seiten im eigenen Netzwerk. Zum Schutz lädt der Home-Assistant-Server nur öffentliche Webseiten (nur http/https auf den Standardports, keine Adressen im eigenen Netzwerk oder von Home Assistant selbst, auch nicht über Weiterleitungen oder Hostnamen, Größen- und Zeitlimits). Das Foto der Seite wird mit übernommen, sofern es JPEG, PNG oder WebP bis 2 MB ist.

**KI-Einstellungen:** Der geplante KI-Import nutzt die AI-Task-Funktion von Home Assistant statt eines festen Anbieters. Unter *Einstellungen > Geräte & Dienste > Recipe Library > Konfigurieren* lässt sich pro Aufgabe (Webseiten und Text, Bilder und Screenshots, Videos) eine AI-Task-Entität wählen, zum Beispiel ein Anbieter für Videos und ein anderer für Bilder. Ein leeres Feld nutzt die bevorzugte AI-Task-Entität von Home Assistant. Das Formular lässt sich jederzeit erneut öffnen und ändern, ein Neustart ist nicht nötig. Der Import von Webseiten mit strukturierten Daten braucht keine KI. Die Auswahl wird gespeichert und vom KI-Import verwendet, sobald er erscheint. Beim KI-Import werden die Inhalte (Seitentext, Bild, Video) an den Anbieter hinter der gewählten Entität gesendet.

**Fotos:** Im Bearbeiten-Formular lässt sich ein Foto wählen (am Handy Kamera oder Galerie). Es wird schon im Browser verkleinert und neu kodiert, dabei verschwinden Metadaten wie der Aufnahmeort. Achtung: Fotos werden unter einer zufälligen, nicht erratbaren URL **ohne Anmeldung** ausgeliefert (ein Bild-Tag im Browser kann die Home-Assistant-Anmeldung nicht mitsenden, wie bei der Bild-Funktion von Home Assistant selbst). Wer die genaue URL kennt, kann dieses eine Foto öffnen. Bitte keine privaten Bilder hochladen. Löscht man das Foto oder das Rezept, wird die Datei gelöscht.

**Daten:** gespeichert lokal in der Home-Assistant-Datei `.storage/recipe_library` und im Ordner `.storage/recipe_library_images/` (Fotos), beides enthalten in den normalen Backups.

**Entstehung:** Diese Integration ist mit Hilfe von KI entstanden („Vibe-Coding“, zusammen mit Claude von Anthropic). Sie ist getestet, kann aber wie jede Software Fehler enthalten. Bitte vor der Nutzung ein Backup von Home Assistant anlegen.
