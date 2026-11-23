# ha-recipe-library

Simple recipe library for Home Assistant: AI-assisted import from websites, YouTube and social media, manual entry, tags and a dashboard card.

> **Status: early development (v0.1.0).** The integration currently only sets itself up. None of the features below are implemented yet; see the [roadmap](#roadmap).

## What it is

A small, focused library for recipes you want to keep:

- **Import** a recipe from a website, a YouTube video or a social media video, or **enter it manually**. AI does the extraction; you review the result before it is saved.
- **Browse** your recipes in a library on your dashboard, with search and filtering by tags.
- **Organise** with tags you define yourself (for example *Pasta*, *Sauces & marinades*, *Braised dishes*). A recipe can have several tags. Renaming a tag updates every recipe and filter that uses it.

## What it deliberately is not

No meal planner, no shopping lists, no timeline, no ingredient database, and no separate login or user management. Ingredients are plain text lines inside each recipe. Access follows your Home Assistant users, so everyone who can open your dashboard can use the library.

Every recipe stays fully editable and deletable after it has been created, no matter whether it was imported or entered by hand.

## Roadmap

1. **Library**: storage, manual entry, tags (create, rename, delete), search and filter, edit and delete, dashboard card.
2. **Website import**: structured recipe data first, AI extraction as fallback.
3. **YouTube import**: the video is read directly by the AI provider.
4. **TikTok and Instagram**: best effort, because downloading these videos is often blocked. Text and image import (pasted caption, screenshot, cookbook photo) is the reliable fallback and also works for any other source.

## Requirements

- Home Assistant 2025.8 or newer
- For the AI import (from stage 2): an AI provider configured in Home Assistant, or an API key. Imported content is sent to the provider you choose.

## Installation

Not usable yet. Once stage 1 is released, the integration can be added in HACS as a custom repository (category *Integration*) and set up under *Settings > Devices & services*.

## Development

```
custom_components/recipe_library/
  __init__.py        integration setup
  config_flow.py     one-step setup, single instance
  const.py           constants
  manifest.json      integration manifest
  translations/      en, de
  frontend/          dashboard card (served by the integration)
hacs.json            HACS metadata
```

## License

[MIT](LICENSE)

---

## Kurzfassung auf Deutsch

Eine schlanke Rezept-Bibliothek für Home Assistant. Rezepte lassen sich von Websites, YouTube und Social Media KI-gestützt importieren oder manuell anlegen, mit eigenen Tags organisieren und über eine Karte im Dashboard durchsuchen und filtern. Mehrere Tags pro Rezept sind möglich, eine Umbenennung wirkt überall.

Bewusst nicht enthalten: Essensplaner, Einkaufslisten, Zeitstrahl, Zutaten-Datenbank und eine eigene Benutzerverwaltung. Zutaten sind einfache Textzeilen im Rezept, der Zugriff läuft über die Home-Assistant-Benutzer. Jedes Rezept bleibt nach dem Anlegen jederzeit bearbeitbar und löschbar.

Stand: frühe Entwicklung, noch keine Funktionen. Die Reihenfolge steht oben in der Roadmap.
