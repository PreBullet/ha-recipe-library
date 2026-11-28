/**
 * Recipe Library card for Home Assistant.
 *
 * One self-contained ES module: no build step, no dependencies on other cards
 * or integrations. It is served and registered by the "Recipe Library"
 * integration, so no manual dashboard resource is needed.
 *
 * Card type:   custom:recipe-library-card
 * Options:     title (text), columns (1-6, default 2), height (px or CSS length)
 * Look:        only Home Assistant theme variables are used, so the card
 *              follows the active theme (light, dark, custom) automatically.
 *
 * User content is only ever inserted as text (never as HTML).
 */

const CARD_TYPE = "recipe-library-card";
const WS = "recipe_library";
const RETRY_MS = 10000;
const IMAGE_URL = "/api/recipe_library/image/";
const IMAGE_NAME = /^[0-9a-f]{32}\.(jpg|png|webp)$/;
const PHOTO_MAX_EDGE = 960; // longest side in pixels after shrinking
const PHOTO_MAX_BYTES = 1500000; // stay far below the server limit of 2 MB

/* ------------------------------------------------------------------ i18n */

const STRINGS = {
  en: {
    title: "Recipes",
    saved: "{n} saved",
    filtered: "{n} of {total} recipes",
    search: "Search recipes",
    all: "All",
    allRecipes: "All recipes",
    recipes_one: "{n} recipe",
    recipes_other: "{n} recipes",
    noRecipes: "No recipes yet",
    noRecipesHint: "Tap + to add your first recipe.",
    noMatch: "No recipes match.",
    loading: "Loading…",
    notSetUp:
      "Recipe Library is not set up. Add the integration under Settings › Devices & services.",
    loadFailed: "Could not load the recipes.",
    manageTags: "Manage categories",
    addRecipe: "Add recipe",
    backToLibrary: "Back to library",
    back: "Back",
    edit: "Edit",
    delete: "Delete",
    openSource: "Open source",
    servings: "{n} servings",
    ingredients: "Ingredients",
    steps: "Instructions",
    notes: "Notes",
    deleteTitle: "Delete recipe?",
    deleteBody:
      "“{title}” will be permanently removed from the library. This cannot be undone.",
    cancel: "Cancel",
    confirmDelete: "Delete",
    newRecipe: "New recipe",
    editRecipe: "Edit recipe",
    fTitle: "Title",
    fTime: "Time",
    fServings: "Servings",
    fTags: "Categories",
    fIngredients: "Ingredients (one per line)",
    fSteps: "Instructions (one step per paragraph)",
    fNotes: "Notes",
    fSource: "Source",
    phSource: "Link or note",
    phTag: "e.g. Baking",
    newTag: "New category",
    tagName: "Name of the new category",
    add: "Add",
    manageTagsLink: "Manage categories",
    save: "Save",
    saving: "Saving…",
    tagsTitle: "Categories",
    tagsInfo:
      "A rename applies immediately to all recipes and to the filters in the library.",
    rename: "Rename {name}",
    deleteTag: "Delete {name}",
    newName: "New name",
    renameImpact: "Applies immediately to {recipes} and the filters in the library.",
    deleteTagTitle: "Delete “{name}”?",
    deleteTagBody:
      "The category is removed from {recipes}. The recipes themselves are kept.",
    create: "Create",
    errTitle: "Please enter a title.",
    errName: "Please enter a name.",
    errInvalid: "Some input is invalid or too long.",
    errNotFound: "This item no longer exists.",
    errNameExists: "A category with this name already exists.",
    errLimit: "The size limit of the library is reached.",
    errGeneric: "Something went wrong. Please try again.",
    fPhoto: "Photo",
    choosePhoto: "Choose photo",
    changePhoto: "Change photo",
    removePhoto: "Remove photo",
    uploading: "Uploading…",
    errPhoto: "This image could not be read. Try a JPEG or PNG photo.",
    errTooLarge: "The image is too large.",
    modesLabel: "How do you want to add the recipe?",
    modeLink: "Link",
    modeText: "Text or photo",
    modeManual: "Manual",
    soon: "Soon",
    soonHint: "Importing from text or a photo follows with the AI import.",
    pasteLink: "Paste from clipboard",
    errClipboard: "The clipboard could not be read. Paste the link into the field.",
    imgNotFound: "No photo was found on the page. You can add one yourself.",
    imgTooLarge: "The photo on the page is too large to import. You can add one yourself.",
    imgFailed: "The photo on the page could not be loaded. You can add one yourself.",
    importIntro:
      "Paste the link of a recipe page. You can check and change the recipe before it is saved.",
    importUrl: "Link to the recipe",
    phImportUrl: "https://",
    importGo: "Import",
    importing: "Loading…",
    importNote:
      "This works with pages that describe their recipe in a structured way, which most recipe sites do. The photo is imported too, if it is available.",
    importedHint: "Imported from the web. Please check the recipe before you save it.",
    errImportUrl: "That is not a valid web address.",
    errImportBlocked: "This address cannot be used. Only public web pages can be imported.",
    errImportFetch: "The page could not be loaded. It may be unavailable or block automatic access.",
    errImportLarge: "The page is too large to import.",
    errImportNotHtml: "This address does not lead to a web page.",
    errImportNoRecipe:
      "No recipe was found on this page. For now only pages with structured recipe data can be imported.",
  },
  de: {
    title: "Rezepte",
    saved: "{n} gespeichert",
    filtered: "{n} von {total} Rezepten",
    search: "Rezepte durchsuchen",
    all: "Alle",
    allRecipes: "Alle Rezepte",
    recipes_one: "{n} Rezept",
    recipes_other: "{n} Rezepte",
    noRecipes: "Noch keine Rezepte",
    noRecipesHint: "Mit + legst du dein erstes Rezept an.",
    noMatch: "Keine passenden Rezepte.",
    loading: "Lädt …",
    notSetUp:
      "Die Rezept-Bibliothek ist nicht eingerichtet. Füge die Integration unter Einstellungen › Geräte & Dienste hinzu.",
    loadFailed: "Die Rezepte konnten nicht geladen werden.",
    manageTags: "Kategorien verwalten",
    addRecipe: "Rezept hinzufügen",
    backToLibrary: "Zurück zur Bibliothek",
    back: "Zurück",
    edit: "Bearbeiten",
    delete: "Löschen",
    openSource: "Quelle öffnen",
    servings: "{n} Portionen",
    ingredients: "Zutaten",
    steps: "Zubereitung",
    notes: "Notizen",
    deleteTitle: "Rezept löschen?",
    deleteBody:
      "„{title}“ wird dauerhaft aus der Bibliothek entfernt. Das lässt sich nicht rückgängig machen.",
    cancel: "Abbrechen",
    confirmDelete: "Löschen",
    newRecipe: "Neues Rezept",
    editRecipe: "Rezept bearbeiten",
    fTitle: "Titel",
    fTime: "Zeit",
    fServings: "Portionen",
    fTags: "Kategorien",
    fIngredients: "Zutaten (eine pro Zeile)",
    fSteps: "Zubereitung (ein Schritt pro Absatz)",
    fNotes: "Notizen",
    fSource: "Quelle",
    phSource: "Link oder Hinweis",
    phTag: "z. B. Backen",
    newTag: "Neue Kategorie",
    tagName: "Name der neuen Kategorie",
    add: "Hinzufügen",
    manageTagsLink: "Kategorien verwalten",
    save: "Speichern",
    saving: "Speichert …",
    tagsTitle: "Kategorien",
    tagsInfo:
      "Eine Umbenennung gilt sofort für alle Rezepte und für die Filter in der Bibliothek.",
    rename: "{name} umbenennen",
    deleteTag: "{name} löschen",
    newName: "Neuer Name",
    renameImpact: "Gilt sofort für {recipes} und die Filter in der Bibliothek.",
    deleteTagTitle: "„{name}“ löschen?",
    deleteTagBody:
      "Die Kategorie wird von {recipes} entfernt. Die Rezepte selbst bleiben erhalten.",
    create: "Anlegen",
    errTitle: "Bitte gib einen Titel ein.",
    errName: "Bitte gib einen Namen ein.",
    errInvalid: "Eine Eingabe ist ungültig oder zu lang.",
    errNotFound: "Dieser Eintrag existiert nicht mehr.",
    errNameExists: "Eine Kategorie mit diesem Namen gibt es schon.",
    errLimit: "Die maximale Größe der Bibliothek ist erreicht.",
    errGeneric: "Etwas ist schiefgelaufen. Bitte versuche es erneut.",
    fPhoto: "Foto",
    choosePhoto: "Foto wählen",
    changePhoto: "Foto ändern",
    removePhoto: "Foto entfernen",
    uploading: "Lädt hoch …",
    errPhoto: "Dieses Bild konnte nicht gelesen werden. Versuche ein JPEG- oder PNG-Foto.",
    errTooLarge: "Das Bild ist zu groß.",
    modesLabel: "Wie möchtest du das Rezept hinzufügen?",
    modeLink: "Link",
    modeText: "Text oder Bild",
    modeManual: "Manuell",
    soon: "Bald",
    soonHint: "Der Import aus Text oder Bild folgt mit dem KI-Import.",
    pasteLink: "Aus der Zwischenablage einfügen",
    errClipboard: "Die Zwischenablage konnte nicht gelesen werden. Füge den Link direkt ins Feld ein.",
    imgNotFound: "Auf der Seite wurde kein Foto gefunden. Du kannst selbst eines hinzufügen.",
    imgTooLarge: "Das Foto der Seite ist zu groß für den Import. Du kannst selbst eines hinzufügen.",
    imgFailed: "Das Foto der Seite konnte nicht geladen werden. Du kannst selbst eines hinzufügen.",
    importIntro:
      "Füge den Link einer Rezeptseite ein. Das Rezept lässt sich prüfen und ändern, bevor es gespeichert wird.",
    importUrl: "Link zum Rezept",
    phImportUrl: "https://",
    importGo: "Importieren",
    importing: "Lädt …",
    importNote:
      "Das funktioniert bei Seiten, die ihr Rezept strukturiert beschreiben, was die meisten Rezeptseiten tun. Das Foto wird mit übernommen, sofern es verfügbar ist.",
    importedHint: "Aus dem Web importiert. Bitte das Rezept vor dem Speichern prüfen.",
    errImportUrl: "Das ist keine gültige Webadresse.",
    errImportBlocked: "Diese Adresse kann nicht verwendet werden. Es lassen sich nur öffentliche Webseiten importieren.",
    errImportFetch: "Die Seite konnte nicht geladen werden. Sie ist vielleicht nicht erreichbar oder blockiert automatische Abrufe.",
    errImportLarge: "Die Seite ist zu groß für den Import.",
    errImportNotHtml: "Diese Adresse führt nicht zu einer Webseite.",
    errImportNoRecipe:
      "Auf dieser Seite wurde kein Rezept gefunden. Bisher lassen sich nur Seiten mit strukturierten Rezeptdaten importieren.",
  },
};

/* --------------------------------------------------------------- helpers */

const ICONS = {
  back: '<path d="m15 18-6-6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
  tag: '<path d="M3 3h8l9.6 9.6a2 2 0 0 1 0 2.8l-5.2 5.2a2 2 0 0 1-2.8 0L3 11z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  people:
    '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-6 6.5-6s6.5 2.5 6.5 6"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2c2 .7 3.5 2.6 3.5 5.8"/>',
  link: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  dish: '<path d="M3 13h18a9 9 0 0 1-18 0z"/><path d="M12 4v3M8.5 5.5 9.5 8M15.5 5.5 14.5 8"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M4 20h16"/>',
  paste: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/>',
};

/** An icon from the constant table above (never built from user content). */
function icon(name, size = 22, width = 2) {
  const template = document.createElement("template");
  template.innerHTML =
    `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="${width}" stroke-linecap="round" ` +
    `stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
  return template.content.firstChild;
}

// Why an imported recipe has no photo (as reported by the server) -> text.
const ISSUE_TEXTS = {
  not_found: "imgNotFound",
  too_large: "imgTooLarge",
  download_failed: "imgFailed",
};

const PROPS = new Set(["value", "disabled", "type", "placeholder", "rows", "id"]);

/**
 * Tiny DOM builder. Children that are strings become text nodes, so user
 * content can never turn into markup.
 */
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "vars") {
      for (const [name, v] of Object.entries(value)) el.style.setProperty(name, v);
    } else if (key.startsWith("on")) {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (PROPS.has(key)) el[key] = value;
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function hashOf(text) {
  let hash = 0;
  for (const ch of text) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return hash;
}

/** http(s) URL or null: anything else (javascript:, data:, …) is never linked. */
function safeUrl(text) {
  try {
    const url = new URL(text);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch (_err) {
    return null;
  }
}

const splitLines = (text) =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

const splitParagraphs = (text) =>
  text
    .split(/\r?\n\s*\r?\n/)
    .map((part) => part.trim())
    .filter(Boolean);

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/**
 * Shrink a photo in the browser and return it as base64 JPEG. Phone photos are
 * several MB; this keeps uploads small and drops all EXIF data (such as the
 * location) because the picture is redrawn on a canvas.
 */
async function shrinkImage(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch (_err) {
    bitmap = await createImageBitmap(file); // older browsers
  }
  try {
    let edge = PHOTO_MAX_EDGE;
    let quality = 0.82;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const scale = Math.min(1, edge / Math.max(bitmap.width, bitmap.height));
      const width = Math.max(1, Math.round(bitmap.width * scale));
      const height = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      context.fillStyle = "#fff"; // transparent PNGs become white, not black
      context.fillRect(0, 0, width, height);
      context.drawImage(bitmap, 0, 0, width, height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      if (!blob) throw new Error("encoding failed");
      if (blob.size <= PHOTO_MAX_BYTES) return blobToBase64(blob);
      edge = Math.round(edge * 0.75);
      quality = Math.max(0.5, quality - 0.1);
    }
  } finally {
    if (typeof bitmap.close === "function") bitmap.close();
  }
  throw new Error("image too large");
}

/* ----------------------------------------------------------------- style */

const STYLE = `
:host {
  display: block;
  --rl-card: var(--ha-card-background, var(--card-background-color, #fff));
  --rl-text: var(--primary-text-color, #212121);
  --rl-muted: var(--secondary-text-color, #727272);
  --rl-accent: var(--primary-color, #03a9f4);
  --rl-on-accent: var(--text-primary-color, #fff);
  --rl-line: var(--divider-color, rgba(127, 127, 127, 0.3));
  --rl-danger: var(--error-color, #db4437);
  --rl-surface: var(--secondary-background-color, #eee);
}
@supports (color: color-mix(in srgb, red 50%, blue)) {
  :host {
    --rl-surface: color-mix(in srgb, var(--rl-text) 8%, var(--rl-card));
  }
}
ha-card { display: block; overflow: hidden; }
* { box-sizing: border-box; }
.rl {
  position: relative;
  display: flex;
  flex-direction: column;
  height: var(--rl-height, min(78vh, 720px));
  overflow: hidden;
  color: var(--rl-text);
  font-size: 15px;
  line-height: 22px;
}
button, input, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--rl-accent); outline-offset: 2px; }

.top { display: flex; align-items: center; gap: 10px; padding: 16px 16px 0; flex: none; }
.titles { flex: 1; min-width: 0; }
.h1 { font-size: 22px; line-height: 28px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub { font-size: 13px; line-height: 18px; color: var(--rl-muted); }
.icon-btn {
  flex: none; width: 44px; height: 44px; padding: 0; border: 0; border-radius: 50%;
  background: var(--rl-surface); display: flex; align-items: center; justify-content: center;
}
.actions { display: flex; gap: 10px; margin-left: auto; }

.search { position: relative; padding: 12px 16px 0; flex: none; }
.search svg { position: absolute; left: 30px; top: 25px; color: var(--rl-muted); pointer-events: none; }
.field {
  display: block; width: 100%; min-height: 48px; padding: 0 16px; border: 0;
  border-radius: 16px; background: var(--rl-surface);
}
.field::placeholder { color: var(--rl-muted); opacity: 1; }
.search .field { padding-left: 46px; border-radius: 999px; }
textarea.field { padding: 12px 16px; line-height: 24px; resize: vertical; min-height: 0; }

.chips { display: flex; gap: 8px; padding: 10px 16px 4px; overflow-x: auto; flex: none; scrollbar-width: none; }
.chips::-webkit-scrollbar { display: none; }
.chip {
  flex: none; min-height: 44px; padding: 0 18px; border: 0; border-radius: 999px;
  background: var(--rl-surface); display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
}
.chip[aria-pressed="true"] { background: var(--rl-accent); color: var(--rl-on-accent); font-weight: 500; padding-left: 14px; }
.chip[disabled] { opacity: 0.6; cursor: default; }
.badge { padding: 0 8px; border: 1px solid var(--rl-line); border-radius: 999px; font-size: 11px; line-height: 16px; color: var(--rl-muted); }
.input-wrap { position: relative; margin-top: 8px; }
.input-wrap .field { padding-right: 56px; }
.input-btn { position: absolute; right: 2px; top: 2px; background: transparent; }
.chip.dashed { background: transparent; border: 1.5px dashed var(--rl-line); color: var(--rl-muted); padding-left: 14px; }
.wrap { flex-wrap: wrap; overflow: visible; padding: 8px 0 0; }

.label { padding: 14px 16px 8px; flex: none; font-size: 12px; line-height: 16px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; color: var(--rl-muted); }
.section { margin-top: 24px; font-size: 12px; line-height: 16px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; color: var(--rl-muted); }
.scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 0 16px 24px; }

.grid { display: grid; grid-template-columns: repeat(var(--rl-cols, 2), minmax(0, 1fr)); gap: 12px; align-content: start; padding-bottom: 88px; }
.tile { display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start; width: 100%; padding: 8px 8px 12px; border: 0; border-radius: 18px; background: var(--rl-surface); text-align: left; }
.thumb, .hero, .photo-box { position: relative; overflow: hidden; }
.photo { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.photo-box { display: flex; align-items: center; justify-content: center; height: 180px; margin-top: 8px; border-radius: 16px; background: var(--rl-surface); color: var(--rl-muted); }
.photo-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.thumb {
  display: flex; flex: none; align-items: center; justify-content: center; height: 96px; border-radius: 12px;
  background: var(--rl-surface); color: var(--rl-muted);
}
@supports (color: color-mix(in srgb, red 50%, blue)) {
  .thumb { background: color-mix(in srgb, var(--rl-accent) calc(10% + var(--tone, 0) * 4%), var(--rl-card)); }
}
.tile .title { padding: 10px 4px 0; font-weight: 500; line-height: 20px; overflow-wrap: anywhere; }
.tile .meta { padding: 2px 4px 0; font-size: 13px; line-height: 18px; color: var(--rl-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { grid-column: 1 / -1; padding: 32px 8px; text-align: center; color: var(--rl-muted); }
.empty strong { display: block; color: var(--rl-text); font-weight: 500; margin-bottom: 4px; }

.fab {
  position: absolute; right: 16px; bottom: 16px; width: 56px; height: 56px; border: 0; border-radius: 50%;
  background: var(--rl-accent); color: var(--rl-on-accent); display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
}

.hero { display: flex; align-items: center; justify-content: center; height: 200px; margin-top: 12px; border-radius: 18px; background: var(--rl-surface); color: var(--rl-muted); }
@supports (color: color-mix(in srgb, red 50%, blue)) {
  .hero { background: color-mix(in srgb, var(--rl-accent) calc(10% + var(--tone, 0) * 4%), var(--rl-card)); }
}
.r-title { margin-top: 16px; font-size: 24px; line-height: 30px; font-weight: 500; overflow-wrap: anywhere; }
.facts { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 8px; font-size: 14px; color: var(--rl-muted); }
.fact { display: inline-flex; align-items: center; gap: 6px; }
.pill-link {
  display: inline-flex; align-items: center; gap: 8px; min-height: 44px; margin-top: 12px; padding: 0 18px;
  border: 0; border-radius: 999px; background: var(--rl-surface); text-decoration: none; color: var(--rl-text);
}
.source-text { margin-top: 12px; color: var(--rl-muted); overflow-wrap: anywhere; }
.ing { padding: 10px 0; border-bottom: 1px solid var(--rl-line); overflow-wrap: anywhere; }
.ing:last-child { border-bottom: 0; }
.step { display: flex; gap: 14px; padding: 10px 0; }
.step b { flex: none; width: 22px; color: var(--rl-accent); }
.step span { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 24px; }
.notes { margin-top: 8px; color: var(--rl-muted); white-space: pre-wrap; overflow-wrap: anywhere; }

.flabel { display: block; margin-top: 18px; font-size: 12px; line-height: 16px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; color: var(--rl-muted); }
.flabel + .field, .flabel + .field-row { margin-top: 8px; }
.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.link-btn { display: inline-flex; align-items: center; min-height: 44px; padding: 0; border: 0; background: none; color: var(--rl-accent); }
.error { margin-top: 12px; color: var(--rl-danger); font-size: 14px; }
.bar { display: flex; gap: 12px; flex: none; padding: 12px 16px; border-top: 1px solid var(--rl-line); }
.btn {
  min-height: 48px; padding: 0 22px; border: 0; border-radius: 999px; background: var(--rl-surface);
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
}
.btn.primary { flex: 1; background: var(--rl-accent); color: var(--rl-on-accent); font-weight: 500; }
.btn.danger { background: var(--rl-danger); color: var(--rl-on-accent); font-weight: 500; }
.btn[disabled] { opacity: 0.6; cursor: default; }
.new-tag { display: flex; gap: 8px; margin-top: 8px; }
.new-tag .field { flex: 1; }

.info { display: flex; gap: 10px; padding: 12px 20px 0; flex: none; font-size: 14px; line-height: 20px; color: var(--rl-muted); }
.info svg { flex: none; color: var(--rl-accent); margin-top: 1px; }
.info.inline { padding: 14px 0 0; }
.rows { display: flex; flex-direction: column; gap: 10px; padding-top: 14px; }
.row { display: flex; align-items: center; gap: 10px; min-height: 64px; padding: 8px 8px 8px 16px; border-radius: 18px; background: var(--rl-surface); }
.row .grow { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.row .name { font-weight: 500; }
.row .count { font-size: 13px; color: var(--rl-muted); }
.row .icon-btn { background: var(--rl-card); }
.editor { padding: 14px; border-radius: 18px; background: var(--rl-surface); border: 1.5px solid var(--rl-accent); }
.editor.danger { border-color: var(--rl-danger); }
.editor .field { background: var(--rl-card); margin-top: 8px; }
.editor .note { margin-top: 10px; font-size: 13px; line-height: 19px; color: var(--rl-muted); }
.editor .buttons { display: flex; gap: 10px; margin-top: 12px; }
.editor .buttons .btn { flex: 1; background: var(--rl-card); }
.editor .buttons .btn.primary { background: var(--rl-accent); }
.editor .buttons .btn.danger { background: var(--rl-danger); }
.editor .name { font-weight: 500; }
.add-row { min-height: 52px; border: 1.5px dashed var(--rl-line); border-radius: 999px; background: transparent; color: var(--rl-muted); display: flex; align-items: center; justify-content: center; gap: 8px; }

.scrim { position: absolute; inset: 0; z-index: 5; display: flex; flex-direction: column; justify-content: flex-end; background: rgba(0, 0, 0, 0.5); }
.dialog { padding: 22px 16px 20px; border-radius: 22px 22px 0 0; background: var(--rl-card); box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.25); }
.dialog h2 { margin: 0; font-size: 20px; line-height: 26px; font-weight: 500; }
.dialog p { margin: 8px 0 0; color: var(--rl-muted); overflow-wrap: anywhere; }
.dialog .buttons { display: flex; gap: 12px; margin-top: 20px; }
.dialog .buttons .btn { flex: 1; }
.status { padding: 32px 20px; text-align: center; color: var(--rl-muted); }
`;

/* ------------------------------------------------------------------ card */

class RecipeLibraryCard extends HTMLElement {
  constructor() {
    super();
    this._config = { title: null, columns: 2, height: null };
    this._hass = null;
    this._data = { tags: [], recipes: [] };
    this._tagById = new Map();
    this._recipeById = new Map();
    this._tagCounts = new Map();
    this._loaded = false;
    this._loadError = null;
    this._unsub = null;
    this._subscribing = false;
    this._retryAfter = 0;

    this._view = { name: "library" };
    this._shown = null; // name of the view that is currently rendered
    this._query = "";
    this._filter = new Set();
    this._libScroll = 0;
    this._draft = null;
    this._add = null; // state of the add view
    this._importToken = 0; // changes when an import is cancelled or finished
    this._confirm = null;
    this._tagUi = null;
    this._lib = null;

    this.attachShadow({ mode: "open" });
    this.shadowRoot.append(h("style", null, STYLE));
    this._frame = h("div", { class: "rl" });
    this.shadowRoot.append(h("ha-card", null, this._frame));
  }

  /* ---- Home Assistant card API ---- */

  setConfig(config) {
    const cfg = config && typeof config === "object" ? config : {};
    const columns = Math.round(Number(cfg.columns));
    let height = null;
    if (typeof cfg.height === "number" && cfg.height > 0) height = `${cfg.height}px`;
    else if (typeof cfg.height === "string" && CSS.supports("height", cfg.height)) {
      height = cfg.height;
    }
    this._config = {
      title: typeof cfg.title === "string" ? cfg.title : null,
      columns: Number.isFinite(columns) ? Math.min(6, Math.max(1, columns)) : 2,
      height,
    };
    this._frame.style.setProperty("--rl-cols", String(this._config.columns));
    if (height) this._frame.style.setProperty("--rl-height", height);
    else this._frame.style.removeProperty("--rl-height");
    if (this.isConnected) this._render();
  }

  set hass(hass) {
    const before = this._lang();
    this._hass = hass;
    if (this.isConnected && !this._unsub && !this._subscribing) this._subscribe();
    if (this._lang() !== before && this.isConnected) this._render();
  }

  getCardSize() {
    return 12;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getStubConfig() {
    return {};
  }

  connectedCallback() {
    this._render();
    if (this._hass && !this._unsub && !this._subscribing) this._subscribe();
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  /* ---- language ---- */

  _lang() {
    const code =
      this._hass?.locale?.language || this._hass?.language || navigator.language || "en";
    return code.toLowerCase().startsWith("de") ? "de" : "en";
  }

  _t(key, vars) {
    const text = STRINGS[this._lang()][key] ?? STRINGS.en[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (_m, name) => String(vars?.[name] ?? ""));
  }

  _recipes(n) {
    return this._t(n === 1 ? "recipes_one" : "recipes_other", { n });
  }

  _errorText(err) {
    switch (err?.code) {
      case "invalid_format":
        return this._t("errInvalid");
      case "not_found":
        return this._t("errNotFound");
      case "name_exists":
        return this._t("errNameExists");
      case "limit_reached":
        return this._t("errLimit");
      case "invalid_url":
        return this._t("errImportUrl");
      case "blocked_url":
        return this._t("errImportBlocked");
      case "fetch_failed":
        return this._t("errImportFetch");
      case "page_too_large":
        return this._t("errImportLarge");
      case "not_html":
        return this._t("errImportNotHtml");
      case "no_recipe":
        return this._t("errImportNoRecipe");
      default:
        return this._t("errGeneric");
    }
  }

  /* ---- data ---- */

  async _subscribe() {
    if (!this._hass?.connection || Date.now() < this._retryAfter) return;
    this._subscribing = true;
    try {
      const unsub = await this._hass.connection.subscribeMessage(
        (snapshot) => this._onSnapshot(snapshot),
        { type: `${WS}/subscribe` },
      );
      if (this.isConnected) this._unsub = unsub;
      else unsub();
    } catch (err) {
      const missing = err?.code === "unknown_command" || err?.code === "not_loaded";
      this._loadError = missing ? "notSetUp" : "loadFailed";
      this._retryAfter = Date.now() + RETRY_MS;
      if (this.isConnected) this._render();
    } finally {
      this._subscribing = false;
    }
  }

  _onSnapshot(snapshot) {
    const collator = new Intl.Collator(this._lang(), { numeric: true, sensitivity: "base" });
    const tags = [...(snapshot?.tags || [])].sort((a, b) => collator.compare(a.name, b.name));
    const recipes = [...(snapshot?.recipes || [])].sort((a, b) =>
      collator.compare(a.title, b.title),
    );
    this._data = { tags, recipes };
    this._tagById = new Map(tags.map((tag) => [tag.id, tag]));
    this._recipeById = new Map(recipes.map((recipe) => [recipe.id, recipe]));
    this._tagCounts = new Map();
    for (const recipe of recipes) {
      for (const id of recipe.tags) {
        this._tagCounts.set(id, (this._tagCounts.get(id) || 0) + 1);
      }
    }
    this._loaded = true;
    this._loadError = null;
    for (const id of [...this._filter]) if (!this._tagById.has(id)) this._filter.delete(id);

    if (!this.isConnected) return;
    switch (this._view.name) {
      case "library":
        if (this._shown === "library" && this._lib) this._refreshLibrary();
        else this._render();
        break;
      case "edit":
        // Never rebuild the form while someone types in it.
        if (this._draft) {
          for (const id of [...this._draft.tags]) {
            if (!this._tagById.has(id)) this._draft.tags.delete(id);
          }
        }
        this._refreshDraftChips();
        break;
      case "recipe":
        if (!this._recipeById.has(this._view.id)) this._go({ name: "library" });
        else this._render();
        break;
      default:
        this._render();
    }
  }

  /* ---- navigation / rendering ---- */

  _go(view) {
    if (this._view.name === "library") {
      this._libScroll = this._frame.querySelector("[data-scroll]")?.scrollTop || 0;
    }
    this._view = view;
    this._confirm = null;
    if (view.name !== "tags") this._tagUi = null;
    if (view.name !== "add") {
      this._add = null;
      this._importToken += 1; // an import that is still running is dropped
    }
    this._render({ resetScroll: true });
  }

  _render({ resetScroll = false } = {}) {
    const root = this.shadowRoot;
    const active = root.activeElement;
    const focusKey = active?.dataset?.focusKey;
    const selection =
      active && typeof active.selectionStart === "number"
        ? [active.selectionStart, active.selectionEnd]
        : null;
    const sameView = this._shown === this._view.name;
    const scrollTop = this._frame.querySelector("[data-scroll]")?.scrollTop || 0;

    this._lib = null;
    let nodes;
    switch (this._view.name) {
      case "recipe":
        nodes = this._buildRecipe();
        break;
      case "edit":
        nodes = this._buildEdit();
        break;
      case "tags":
        nodes = this._buildTags();
        break;
      case "add":
        nodes = this._buildAdd();
        break;
      default:
        nodes = this._buildLibrary();
    }
    this._frame.replaceChildren(...nodes);
    this._shown = this._view.name;

    const scroller = this._frame.querySelector("[data-scroll]");
    if (scroller) {
      if (resetScroll || !sameView) {
        scroller.scrollTop = this._view.name === "library" ? this._libScroll : 0;
      } else scroller.scrollTop = scrollTop;
    }
    if (focusKey && sameView) {
      const el = this._frame.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`);
      if (el) {
        el.focus({ preventScroll: true });
        if (selection && typeof el.setSelectionRange === "function") {
          el.setSelectionRange(selection[0], selection[1]);
        }
      }
    }
  }

  /** Replace the children of a container but keep keyboard focus on the same control. */
  _swap(container, nodes) {
    const active = this.shadowRoot.activeElement;
    const key = active && container.contains(active) ? active.dataset.focusKey : null;
    const selection =
      key && typeof active.selectionStart === "number"
        ? [active.selectionStart, active.selectionEnd]
        : null;
    container.replaceChildren(...nodes.filter(Boolean)); // null would become the text "null"
    if (!key) return;
    const el = container.querySelector(`[data-focus-key="${CSS.escape(key)}"]`);
    if (!el) return;
    el.focus({ preventScroll: true });
    if (selection) el.setSelectionRange(selection[0], selection[1]);
  }

  _iconButton(name, label, onClick) {
    return h("button", { class: "icon-btn", type: "button", "aria-label": label, onClick }, icon(name, 22));
  }

  _backButton(label, target) {
    return this._iconButton("back", label, () => this._go(target));
  }

  /* ---- library view ---- */

  _title() {
    return this._config.title !== null ? this._config.title : this._t("title");
  }

  _buildLibrary() {
    this._lib = {
      subtitle: h("div", { class: "sub" }),
      chips: h("div", { class: "chips" }),
      label: h("div", { class: "label" }),
      grid: h("div", { class: "grid" }),
      search: h("input", {
        class: "field",
        type: "text",
        id: "rl-search",
        value: this._query,
        placeholder: this._t("search"),
        "aria-label": this._t("search"),
        enterkeyhint: "search",
        autocomplete: "off",
        onInput: (event) => {
          this._query = event.target.value;
          this._refreshLibrary();
        },
      }),
    };
    const lib = this._lib;
    const nodes = [
      h(
        "div",
        { class: "top" },
        h("div", { class: "titles" }, h("div", { class: "h1" }, this._title()), lib.subtitle),
        this._iconButton("tag", this._t("manageTags"), () => this._go({ name: "tags" })),
      ),
      h("div", { class: "search" }, icon("search", 20), lib.search),
      lib.chips,
      lib.label,
      h("div", { class: "scroll", "data-scroll": "" }, lib.grid),
      h(
        "button",
        {
          class: "fab",
          type: "button",
          "aria-label": this._t("addRecipe"),
          onClick: () => this._startAdd(),
        },
        icon("plus", 26),
      ),
    ];
    this._refreshLibrary();
    return nodes;
  }

  _matches(recipe, needle) {
    if (!needle) return true;
    const haystack = [
      recipe.title,
      recipe.notes,
      ...recipe.ingredients,
      ...recipe.tags.map((id) => this._tagById.get(id)?.name || ""),
    ]
      .join("\n")
      .toLowerCase();
    return haystack.includes(needle);
  }

  _refreshLibrary() {
    const lib = this._lib;
    if (!lib) return;
    const { tags, recipes } = this._data;
    const needle = this._query.trim().toLowerCase();
    const shown = recipes.filter(
      (recipe) =>
        [...this._filter].every((id) => recipe.tags.includes(id)) &&
        this._matches(recipe, needle),
    );
    const filtering = this._filter.size > 0 || needle !== "";

    lib.subtitle.textContent = !this._loaded
      ? ""
      : filtering
        ? this._t("filtered", { n: shown.length, total: recipes.length })
        : this._t("saved", { n: recipes.length });

    const toggle = (id) => {
      if (this._filter.has(id)) this._filter.delete(id);
      else this._filter.add(id);
      this._refreshLibrary();
    };
    this._swap(lib.chips, [
      h(
        "button",
        {
          class: "chip",
          type: "button",
          "data-focus-key": "chip-all",
          "aria-pressed": String(this._filter.size === 0),
          onClick: () => {
            this._filter.clear();
            this._refreshLibrary();
          },
        },
        this._t("all"),
      ),
      ...tags.map((tag) => {
        const on = this._filter.has(tag.id);
        return h(
          "button",
          {
            class: "chip",
            type: "button",
            "data-focus-key": `chip-${tag.id}`,
            "aria-pressed": String(on),
            onClick: () => toggle(tag.id),
          },
          on ? icon("check", 18, 2.4) : null,
          tag.name,
        );
      }),
    ]);

    const names = [...this._filter].map((id) => this._tagById.get(id)?.name).filter(Boolean);
    lib.label.textContent = names.length
      ? `${names.join(" + ")} · ${this._recipes(shown.length)}`
      : this._t("allRecipes");

    if (!this._loaded) {
      lib.grid.replaceChildren(
        h("div", { class: "empty" }, this._loadError ? this._t(this._loadError) : this._t("loading")),
      );
    } else if (recipes.length === 0) {
      lib.grid.replaceChildren(
        h("div", { class: "empty" }, h("strong", null, this._t("noRecipes")), this._t("noRecipesHint")),
      );
    } else if (shown.length === 0) {
      lib.grid.replaceChildren(h("div", { class: "empty" }, this._t("noMatch")));
    } else {
      lib.grid.replaceChildren(...shown.map((recipe) => this._tile(recipe)));
    }
  }

  _tagSummary(recipe) {
    const names = recipe.tags.map((id) => this._tagById.get(id)?.name).filter(Boolean);
    if (names.length === 0) return "";
    return names.length > 1 ? `${names[0]} +${names.length - 1}` : names[0];
  }

  _imageUrl(name) {
    if (typeof name !== "string" || !IMAGE_NAME.test(name)) return null;
    const path = `${IMAGE_URL}${name}`;
    return typeof this._hass?.hassUrl === "function" ? this._hass.hassUrl(path) : path;
  }

  /** A box with the recipe photo, or a placeholder icon when there is none. */
  _photo(recipe, className, iconSize, iconWidth) {
    const box = h(
      "div",
      { class: className, vars: { "--tone": hashOf(recipe.title) % 5 } },
      icon("dish", iconSize, iconWidth),
    );
    const url = this._imageUrl(recipe.image);
    if (url) {
      const img = h("img", { class: "photo", src: url, alt: "", loading: "lazy", decoding: "async" });
      // If the photo cannot be loaded, the placeholder underneath stays visible.
      img.addEventListener("error", () => img.remove());
      box.append(img);
    }
    return box;
  }

  _tile(recipe) {
    const meta = [recipe.time, this._tagSummary(recipe)].filter(Boolean).join(" · ");
    return h(
      "button",
      {
        class: "tile",
        type: "button",
        onClick: () => this._go({ name: "recipe", id: recipe.id }),
      },
      this._photo(recipe, "thumb", 28, 1.8),
      h("div", { class: "title" }, recipe.title),
      meta ? h("div", { class: "meta" }, meta) : null,
    );
  }

  /* ---- recipe view ---- */

  _buildRecipe() {
    const recipe = this._recipeById.get(this._view.id);
    if (!recipe) {
      this._view = { name: "library" };
      return this._buildLibrary();
    }
    const servings = /^\d+([.,]\d+)?$/.test(recipe.servings)
      ? this._t("servings", { n: recipe.servings })
      : recipe.servings;
    const url = recipe.source ? safeUrl(recipe.source) : null;

    const facts = [
      recipe.time ? h("span", { class: "fact" }, icon("clock", 18), recipe.time) : null,
      servings ? h("span", { class: "fact" }, icon("people", 18), servings) : null,
    ].filter(Boolean);

    const tagChips = recipe.tags
      .map((id) => this._tagById.get(id))
      .filter(Boolean)
      .map((tag) =>
        h(
          "button",
          {
            class: "chip",
            type: "button",
            onClick: () => {
              this._filter = new Set([tag.id]);
              this._query = "";
              this._libScroll = 0;
              this._go({ name: "library" });
            },
          },
          tag.name,
        ),
      );

    const body = [
      this._photo(recipe, "hero", 40, 1.6),
      h("div", { class: "r-title" }, recipe.title),
      facts.length ? h("div", { class: "facts" }, facts) : null,
      tagChips.length ? h("div", { class: "chips wrap" }, tagChips) : null,
    ];
    if (url) {
      body.push(
        h(
          "a",
          { class: "pill-link", href: url.href, target: "_blank", rel: "noopener noreferrer" },
          this._t("openSource"),
          h("span", { class: "fact" }, `(${url.hostname.replace(/^www\./, "")})`),
          icon("link", 18),
        ),
      );
    } else if (recipe.source) {
      body.push(h("div", { class: "source-text" }, recipe.source));
    }
    if (recipe.ingredients.length) {
      body.push(
        h("div", { class: "section" }, this._t("ingredients")),
        h("div", null, recipe.ingredients.map((line) => h("div", { class: "ing" }, line))),
      );
    }
    if (recipe.steps.length) {
      body.push(
        h("div", { class: "section" }, this._t("steps")),
        h(
          "div",
          null,
          recipe.steps.map((text, i) => h("div", { class: "step" }, h("b", null, String(i + 1)), h("span", null, text))),
        ),
      );
    }
    if (recipe.notes) {
      body.push(h("div", { class: "section" }, this._t("notes")), h("div", { class: "notes" }, recipe.notes));
    }

    const nodes = [
      h(
        "div",
        { class: "top" },
        this._backButton(this._t("backToLibrary"), { name: "library" }),
        h(
          "div",
          { class: "actions" },
          this._iconButton("edit", this._t("edit"), () => this._startEdit(recipe)),
          this._iconButton("trash", this._t("delete"), () => {
            this._confirm = { type: "recipe", id: recipe.id, error: null };
            this._render();
          }),
        ),
      ),
      h("div", { class: "scroll", "data-scroll": "" }, body),
    ];
    if (this._confirm?.type === "recipe") nodes.push(this._buildRecipeDialog(recipe));
    return nodes;
  }

  _dialog(title, text, error, confirmLabel, onConfirm, onCancel) {
    const cancel = h("button", { class: "btn", type: "button", onClick: onCancel }, this._t("cancel"));
    const scrim = h(
      "div",
      {
        class: "scrim",
        onClick: (event) => {
          if (event.target === scrim) onCancel();
        },
        onKeydown: (event) => {
          if (event.key === "Escape") onCancel();
        },
      },
      h(
        "div",
        { class: "dialog", role: "dialog", "aria-modal": "true", "aria-label": title },
        h("h2", null, title),
        h("p", null, text),
        error ? h("div", { class: "error" }, error) : null,
        h(
          "div",
          { class: "buttons" },
          cancel,
          h("button", { class: "btn danger", type: "button", onClick: onConfirm }, confirmLabel),
        ),
      ),
    );
    queueMicrotask(() => cancel.focus({ preventScroll: true }));
    return scrim;
  }

  _buildRecipeDialog(recipe) {
    return this._dialog(
      this._t("deleteTitle"),
      this._t("deleteBody", { title: recipe.title }),
      this._confirm.error,
      this._t("confirmDelete"),
      async () => {
        try {
          await this._hass.callWS({ type: `${WS}/recipe/delete`, recipe_id: recipe.id });
          this._libScroll = 0;
          this._go({ name: "library" });
        } catch (err) {
          this._confirm = { ...this._confirm, error: this._errorText(err) };
          this._render();
        }
      },
      () => {
        this._confirm = null;
        this._render();
      },
    );
  }

  /* ---- add view: choose how to add a recipe ---- */

  _startAdd() {
    this._add = { url: "", busy: false, error: null };
    this._go({ name: "add" });
  }

  _buildAdd() {
    const s = this._add;
    if (!s) {
      this._view = { name: "library" };
      return this._buildLibrary();
    }
    this._addEls = {
      input: h("input", {
        class: "field",
        id: "rl-import-url",
        type: "text",
        inputmode: "url",
        value: s.url,
        placeholder: this._t("phImportUrl"),
        "data-focus-key": "rl-import-url",
        autocomplete: "off",
        autocapitalize: "off",
        spellcheck: "false",
        enterkeyhint: "go",
        onInput: (event) => {
          s.url = event.target.value;
        },
        onKeydown: (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            this._runImport();
          }
        },
      }),
      error: h("div", { class: "error", role: "alert" }),
      go: h("button", { class: "btn primary", type: "button", onClick: () => this._runImport() }),
    };
    const els = this._addEls;
    const canPaste = typeof navigator.clipboard?.readText === "function";
    const nodes = [
      h(
        "div",
        { class: "top" },
        this._backButton(this._t("back"), { name: "library" }),
        h("div", { class: "h1" }, this._t("addRecipe")),
      ),
      h(
        "div",
        { class: "chips", role: "group", "aria-label": this._t("modesLabel") },
        h("button", { class: "chip", type: "button", "aria-pressed": "true" }, icon("check", 18, 2.4), this._t("modeLink")),
        h(
          "button",
          { class: "chip", type: "button", disabled: true, "aria-pressed": "false", title: this._t("soonHint") },
          this._t("modeText"),
          h("span", { class: "badge" }, this._t("soon")),
        ),
        h(
          "button",
          { class: "chip", type: "button", "aria-pressed": "false", onClick: () => this._startEdit(null) },
          this._t("modeManual"),
        ),
      ),
      h(
        "div",
        { class: "scroll", "data-scroll": "" },
        h("label", { class: "flabel", for: "rl-import-url" }, this._t("importUrl")),
        h(
          "div",
          { class: "input-wrap" },
          els.input,
          canPaste
            ? h(
                "button",
                {
                  class: "icon-btn input-btn",
                  type: "button",
                  "aria-label": this._t("pasteLink"),
                  onClick: () => this._pasteLink(),
                },
                icon("paste", 20),
              )
            : null,
        ),
        els.error,
        h("div", { class: "info inline" }, icon("info", 20), this._t("importIntro")),
        h("div", { class: "info inline" }, icon("info", 20), this._t("importNote")),
      ),
      h(
        "div",
        { class: "bar" },
        h("button", { class: "btn", type: "button", onClick: () => this._go({ name: "library" }) }, this._t("cancel")),
        els.go,
      ),
    ];
    this._refreshAdd();
    return nodes;
  }

  _refreshAdd() {
    const s = this._add;
    const els = this._addEls;
    if (!s || !els || this._view.name !== "add") return;
    els.error.textContent = s.error || "";
    els.input.disabled = s.busy;
    els.go.disabled = s.busy;
    els.go.replaceChildren(icon("download", 20, 2.2), s.busy ? this._t("importing") : this._t("importGo"));
  }

  async _pasteLink() {
    const s = this._add;
    if (!s || s.busy) return;
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (!text || this._add !== s) return;
      s.url = text;
      s.error = null;
      this._addEls.input.value = text;
    } catch (_err) {
      // No permission, or a browser that does not allow reading the clipboard.
      if (this._add !== s) return;
      s.error = this._t("errClipboard");
    }
    this._refreshAdd();
  }

  async _runImport() {
    const s = this._add;
    if (!s || s.busy) return;
    const url = s.url.trim();
    if (!url) {
      s.error = this._t("errImportUrl");
      this._refreshAdd();
      this._addEls.input.focus();
      return;
    }
    const token = ++this._importToken;
    s.busy = true;
    s.error = null;
    this._refreshAdd();
    let draft;
    try {
      draft = await this._hass.callWS({ type: `${WS}/import/url`, url });
    } catch (err) {
      if (token !== this._importToken) return; // cancelled meanwhile
      s.busy = false;
      s.error = this._errorText(err);
      this._refreshAdd();
      return;
    }
    if (token !== this._importToken) {
      // The view was left while loading: nobody will save the picture.
      if (draft?.image) this._discardPhoto(draft.image);
      return;
    }
    this._startEdit(draft, { imported: true });
  }

  /* ---- edit view ---- */

  _startEdit(recipe, { imported = false } = {}) {
    const saved = Boolean(recipe) && !imported; // an imported draft is not in the library yet
    this._draft = {
      id: saved ? recipe.id : null,
      imported,
      title: recipe?.title ?? "",
      time: recipe?.time ?? "",
      servings: recipe?.servings ?? "",
      tags: new Set(recipe?.tags ?? []),
      ingredients: (recipe?.ingredients ?? []).join("\n"),
      steps: (recipe?.steps ?? []).join("\n\n"),
      notes: recipe?.notes ?? "",
      source: recipe?.source ?? "",
      image: recipe?.image ?? "",
      imageIssue: imported ? (recipe?.image_issue ?? "") : "",
      originalImage: saved ? (recipe.image ?? "") : "",
      uploading: false,
      photoError: null,
      saving: false,
      error: null,
      newTag: null, // null = closed, string = text of the open "new category" input
      newTagError: null,
    };
    this._go({ name: "edit" });
  }

  _leaveEdit() {
    const id = this._draft?.id;
    this._discardNewPhoto();
    this._draft = null;
    this._go(id && this._recipeById.has(id) ? { name: "recipe", id } : { name: "library" });
  }

  _textField(key, label, props = {}) {
    const id = `rl-${key}`;
    const multiline = props.rows !== undefined;
    return [
      h("label", { class: "flabel", for: id }, label),
      h(multiline ? "textarea" : "input", {
        class: "field",
        id,
        type: multiline ? null : "text",
        value: this._draft[key],
        rows: props.rows,
        placeholder: props.placeholder,
        "data-focus-key": id,
        autocomplete: "off",
        onInput: (event) => {
          this._draft[key] = event.target.value;
        },
      }),
    ];
  }

  _buildEdit() {
    const d = this._draft;
    if (!d) {
      this._view = { name: "library" };
      return this._buildLibrary();
    }
    this._editEls = {
      photo: h("div", { class: "photo-field" }),
      file: h("input", {
        type: "file",
        accept: "image/*",
        hidden: true,
        onChange: (event) => {
          const file = event.target.files?.[0];
          event.target.value = ""; // allow choosing the same file again
          if (file) this._pickPhoto(file);
        },
      }),
      chips: h("div", { class: "chips wrap", role: "group", "aria-labelledby": "rl-tags-label" }),
      newTag: h("div", { class: "new-tag-wrap" }),
      error: h("div", { class: "error", role: "alert" }),
      save: h("button", { class: "btn primary", type: "button", onClick: () => this._save() }),
    };
    const els = this._editEls;
    const nodes = [
      h(
        "div",
        { class: "top" },
        this._iconButton("back", this._t("back"), () => this._leaveEdit()),
        h("div", { class: "h1" }, d.id ? this._t("editRecipe") : this._t("newRecipe")),
      ),
      h(
        "div",
        { class: "scroll", "data-scroll": "" },
        d.imported ? h("div", { class: "info inline" }, icon("info", 20), this._t("importedHint")) : null,
        this._textField("title", this._t("fTitle")),
        h("div", { class: "flabel", id: "rl-photo-label" }, this._t("fPhoto")),
        els.photo,
        els.file,
        h(
          "div",
          { class: "two" },
          h("div", null, this._textField("time", this._t("fTime"))),
          h("div", null, this._textField("servings", this._t("fServings"))),
        ),
        h("div", { class: "flabel", id: "rl-tags-label" }, this._t("fTags")),
        els.chips,
        els.newTag,
        h(
          "button",
          {
            class: "link-btn",
            type: "button",
            onClick: () => this._go({ name: "tags", back: { name: "edit" } }),
          },
          this._t("manageTagsLink"),
        ),
        ...this._textField("ingredients", this._t("fIngredients"), { rows: 8 }),
        ...this._textField("steps", this._t("fSteps"), { rows: 9 }),
        ...this._textField("notes", this._t("fNotes"), { rows: 2 }),
        ...this._textField("source", this._t("fSource"), { placeholder: this._t("phSource") }),
        els.error,
      ),
      h(
        "div",
        { class: "bar" },
        h("button", { class: "btn", type: "button", onClick: () => this._leaveEdit() }, this._t("cancel")),
        els.save,
      ),
    ];
    this._refreshDraftChips();
    this._refreshPhoto();
    this._refreshSaveState();
    return nodes;
  }

  _refreshPhoto() {
    const els = this._editEls;
    const d = this._draft;
    if (!els || !d || this._view.name !== "edit") return;
    const box = h("div", { class: "photo-box" }, icon("dish", 40, 1.6));
    const url = this._imageUrl(d.image);
    if (url) {
      const img = h("img", { class: "photo", src: url, alt: "" });
      img.addEventListener("error", () => img.remove());
      box.append(img);
    }
    const actions = h(
      "div",
      { class: "photo-actions" },
      h(
        "button",
        {
          class: "btn",
          type: "button",
          disabled: d.uploading,
          "data-focus-key": "photo-choose",
          onClick: () => els.file.click(),
        },
        d.uploading ? this._t("uploading") : d.image ? this._t("changePhoto") : this._t("choosePhoto"),
      ),
      d.image && !d.uploading
        ? h(
            "button",
            { class: "btn", type: "button", "data-focus-key": "photo-remove", onClick: () => this._removePhoto() },
            this._t("removePhoto"),
          )
        : null,
    );
    const issue = !d.image && ISSUE_TEXTS[d.imageIssue];
    this._swap(els.photo, [
      box,
      actions,
      issue ? h("div", { class: "info inline" }, icon("info", 20), this._t(issue)) : null,
      d.photoError ? h("div", { class: "error", role: "alert" }, d.photoError) : null,
    ]);
  }

  async _pickPhoto(file) {
    const d = this._draft;
    if (!d || d.uploading) return;
    d.photoError = null;
    d.uploading = true;
    this._refreshPhoto();
    this._refreshSaveState();
    let uploaded = null;
    let data = null;
    try {
      data = await shrinkImage(file);
    } catch (_err) {
      d.photoError = this._t("errPhoto"); // not an image, or one this browser cannot read
    }
    if (data) {
      try {
        uploaded = (await this._hass.callWS({ type: `${WS}/image/upload`, data })).image;
      } catch (err) {
        d.photoError = err?.code === "image_too_large" ? this._t("errTooLarge") : this._errorText(err);
      }
    }
    d.uploading = false;
    if (uploaded && this._draft !== d) {
      // The form was closed while uploading: nobody will save this photo.
      this._discardPhoto(uploaded);
      return;
    }
    if (uploaded) {
      this._discardNewPhoto(); // an earlier, unsaved upload of this form
      d.image = uploaded;
      d.imageIssue = "";
    }
    this._refreshPhoto();
    this._refreshSaveState();
  }

  _removePhoto() {
    const d = this._draft;
    if (!d) return;
    this._discardNewPhoto();
    d.image = "";
    d.imageIssue = "";
    d.photoError = null;
    this._refreshPhoto();
  }

  /** Delete a photo of this form that was uploaded but not saved. */
  _discardNewPhoto() {
    const d = this._draft;
    if (d && d.image && d.image !== d.originalImage) this._discardPhoto(d.image);
  }

  _discardPhoto(name) {
    // Best effort: the server only deletes photos that no recipe uses, and
    // leftovers are cleaned up when Home Assistant starts.
    Promise.resolve(this._hass.callWS({ type: `${WS}/image/discard`, image: name })).catch(() => {});
  }

  _refreshDraftChips() {
    const els = this._editEls;
    const d = this._draft;
    if (!els || !d || this._view.name !== "edit") return;
    const chips = this._data.tags.map((tag) => {
      const on = d.tags.has(tag.id);
      return h(
        "button",
        {
          class: "chip",
          type: "button",
          "aria-pressed": String(on),
          "data-focus-key": `dchip-${tag.id}`,
          onClick: () => {
            if (d.tags.has(tag.id)) d.tags.delete(tag.id);
            else d.tags.add(tag.id);
            this._refreshDraftChips();
          },
        },
        on ? icon("check", 18, 2.4) : null,
        tag.name,
      );
    });
    chips.push(
      h(
        "button",
        {
          class: "chip dashed",
          type: "button",
          "data-focus-key": "dchip-new",
          onClick: () => {
            d.newTag = d.newTag === null ? "" : null;
            d.newTagError = null;
            d.focusNewTag = d.newTag !== null;
            this._refreshDraftChips();
          },
        },
        icon("plus", 18, 2.2),
        this._t("newTag"),
      ),
    );
    this._swap(els.chips, chips);

    if (d.newTag === null) {
      this._swap(els.newTag, []);
      return;
    }
    const input = h("input", {
      class: "field",
      type: "text",
      value: d.newTag,
      placeholder: this._t("phTag"),
      "aria-label": this._t("tagName"),
      "data-focus-key": "rl-newtag",
      autocomplete: "off",
      onInput: (event) => {
        d.newTag = event.target.value;
      },
      onKeydown: (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          this._createDraftTag();
        } else if (event.key === "Escape") {
          d.newTag = null;
          this._refreshDraftChips();
        }
      },
    });
    this._swap(els.newTag, [
      h(
        "div",
        { class: "new-tag" },
        input,
        h("button", { class: "btn primary", type: "button", onClick: () => this._createDraftTag() }, this._t("add")),
      ),
      d.newTagError ? h("div", { class: "error" }, d.newTagError) : null,
    ].filter(Boolean));
    if (d.focusNewTag) {
      d.focusNewTag = false;
      els.newTag.querySelector("input")?.focus({ preventScroll: true });
    }
  }

  async _createDraftTag() {
    const d = this._draft;
    const name = (d.newTag || "").trim();
    if (!name) {
      d.newTagError = this._t("errName");
      this._refreshDraftChips();
      return;
    }
    try {
      const tag = await this._hass.callWS({ type: `${WS}/tag/create`, name });
      d.tags.add(tag.id);
      d.newTag = null;
      d.newTagError = null;
    } catch (err) {
      d.newTagError = this._errorText(err);
    }
    this._refreshDraftChips();
  }

  _refreshSaveState() {
    const d = this._draft;
    const els = this._editEls;
    if (!d || !els) return;
    els.error.textContent = d.error || "";
    els.save.disabled = d.saving || d.uploading;
    els.save.replaceChildren(icon("check", 20, 2.2), d.saving ? this._t("saving") : this._t("save"));
  }

  async _save() {
    const d = this._draft;
    if (!d || d.saving || d.uploading) return;
    if (!d.title.trim()) {
      d.error = this._t("errTitle");
      this._refreshSaveState();
      this._frame.querySelector("#rl-title")?.focus();
      return;
    }
    d.saving = true;
    d.error = null;
    this._refreshSaveState();
    const message = {
      type: `${WS}/recipe/save`,
      title: d.title,
      time: d.time,
      servings: d.servings,
      tags: [...d.tags],
      ingredients: splitLines(d.ingredients),
      steps: splitParagraphs(d.steps),
      notes: d.notes,
      source: d.source,
      image: d.image,
    };
    if (d.id) message.recipe_id = d.id;
    try {
      const saved = await this._hass.callWS(message);
      this._draft = null;
      this._go({ name: "recipe", id: saved.id });
    } catch (err) {
      d.saving = false;
      d.error = this._errorText(err);
      this._refreshSaveState();
    }
  }

  /* ---- categories view ---- */

  _buildTags() {
    const ui = this._tagUi || (this._tagUi = { mode: null, id: null, value: "", error: null });
    const back = this._view.back || { name: "library" };
    const rows = this._data.tags.map((tag) => {
      const count = this._tagCounts.get(tag.id) || 0;
      if (ui.mode === "rename" && ui.id === tag.id) return this._renameEditor(tag, count);
      if (ui.mode === "delete" && ui.id === tag.id) return this._deleteEditor(tag, count);
      return h(
        "div",
        { class: "row" },
        h("div", { class: "grow" }, h("div", { class: "name" }, tag.name), h("div", { class: "count" }, this._recipes(count))),
        this._iconButton("edit", this._t("rename", { name: tag.name }), () => {
          this._tagUi = { mode: "rename", id: tag.id, value: tag.name, error: null };
          this._render();
          this._frame.querySelector('[data-focus-key="rl-tag-input"]')?.select();
        }),
        this._iconButton("trash", this._t("deleteTag", { name: tag.name }), () => {
          this._tagUi = { mode: "delete", id: tag.id, value: "", error: null };
          this._render();
        }),
      );
    });
    rows.push(ui.mode === "add" ? this._addEditor() : this._addButton());

    return [
      h(
        "div",
        { class: "top" },
        this._backButton(this._t("back"), back),
        h("div", { class: "h1" }, this._t("tagsTitle")),
      ),
      h("div", { class: "info" }, icon("info", 20), h("div", null, this._t("tagsInfo"))),
      h("div", { class: "scroll", "data-scroll": "" }, h("div", { class: "rows" }, rows)),
    ];
  }

  _closeTagUi() {
    this._tagUi = { mode: null, id: null, value: "", error: null };
    this._render();
  }

  _tagInput(label) {
    const ui = this._tagUi;
    return h("input", {
      class: "field",
      type: "text",
      value: ui.value,
      "aria-label": label,
      "data-focus-key": "rl-tag-input",
      autocomplete: "off",
      onInput: (event) => {
        ui.value = event.target.value;
      },
      onKeydown: (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          this._submitTagUi();
        } else if (event.key === "Escape") this._closeTagUi();
      },
    });
  }

  _renameEditor(tag, count) {
    const ui = this._tagUi;
    return h(
      "div",
      { class: "editor" },
      h("div", { class: "flabel", style: "margin-top:0" }, this._t("newName")),
      this._tagInput(this._t("newName")),
      h("div", { class: "note" }, this._t("renameImpact", { recipes: this._recipes(count) })),
      ui.error ? h("div", { class: "error" }, ui.error) : null,
      h(
        "div",
        { class: "buttons" },
        h("button", { class: "btn", type: "button", onClick: () => this._closeTagUi() }, this._t("cancel")),
        h("button", { class: "btn primary", type: "button", onClick: () => this._submitTagUi() }, this._t("save")),
      ),
    );
  }

  _deleteEditor(tag, count) {
    const ui = this._tagUi;
    return h(
      "div",
      { class: "editor danger" },
      h("div", { class: "name" }, this._t("deleteTagTitle", { name: tag.name })),
      h("div", { class: "note" }, this._t("deleteTagBody", { recipes: this._recipes(count) })),
      ui.error ? h("div", { class: "error" }, ui.error) : null,
      h(
        "div",
        { class: "buttons" },
        h("button", { class: "btn", type: "button", onClick: () => this._closeTagUi() }, this._t("cancel")),
        h("button", { class: "btn danger", type: "button", onClick: () => this._submitTagUi() }, this._t("confirmDelete")),
      ),
    );
  }

  _addEditor() {
    const ui = this._tagUi;
    return h(
      "div",
      { class: "editor" },
      h("div", { class: "flabel", style: "margin-top:0" }, this._t("tagName")),
      this._tagInput(this._t("tagName")),
      ui.error ? h("div", { class: "error" }, ui.error) : null,
      h(
        "div",
        { class: "buttons" },
        h("button", { class: "btn", type: "button", onClick: () => this._closeTagUi() }, this._t("cancel")),
        h("button", { class: "btn primary", type: "button", onClick: () => this._submitTagUi() }, this._t("create")),
      ),
    );
  }

  _addButton() {
    return h(
      "button",
      {
        class: "add-row",
        type: "button",
        onClick: () => {
          this._tagUi = { mode: "add", id: null, value: "", error: null };
          this._render();
          this._frame.querySelector('[data-focus-key="rl-tag-input"]')?.focus();
        },
      },
      icon("plus", 18, 2.2),
      this._t("newTag"),
    );
  }

  async _submitTagUi() {
    const ui = this._tagUi;
    if (!ui || !ui.mode) return;
    try {
      if (ui.mode === "delete") {
        await this._hass.callWS({ type: `${WS}/tag/delete`, tag_id: ui.id });
      } else {
        const name = ui.value.trim();
        if (!name) {
          ui.error = this._t("errName");
          this._render();
          return;
        }
        if (ui.mode === "rename") {
          await this._hass.callWS({ type: `${WS}/tag/rename`, tag_id: ui.id, name });
        } else {
          await this._hass.callWS({ type: `${WS}/tag/create`, name });
        }
      }
      this._closeTagUi();
    } catch (err) {
      ui.error = this._errorText(err);
      this._render();
    }
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, RecipeLibraryCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Recipe Library",
    description: "Browse, search and manage your recipes. Needs the Recipe Library integration.",
    preview: false,
  });
}
