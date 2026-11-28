# Frontend

`recipe-library-card.js` is the dashboard card (`custom:recipe-library-card`): one
self-contained ES module without a build step or dependencies.

The integration serves this file under `/recipe_library/recipe-library-card.js`
and registers it with the Home Assistant frontend (with the integration version
as a cache-busting query), so no separate card repository and no manual
dashboard resource are needed.

Notes for changes:

- Styling uses only Home Assistant theme variables (see the README), no fixed
  colours, so the card follows the active theme.
- User content is inserted as text only (`textContent`), never as HTML. Links
  are only created for `http`/`https` URLs.
- Photos: the card shrinks a chosen picture on a canvas (longest side 960 px,
  JPEG, EXIF dropped, orientation applied) and uploads it with
  `recipe_library/image/upload`. The returned file name goes into
  `recipe/save`. A photo that is replaced, removed or not saved is released
  again by the card (`image/discard`) or by the server. Image URLs are built
  from `hass.hassUrl` and only for names that match the stored file name
  pattern.
- Add view: the **+** button opens it (view `add`) with the ways to add a recipe:
  Link (the import, the default), Text or photo (disabled until the AI import
  exists) and Manual (opens the empty form with `_startEdit(null)`).
- Import: the add view sends the address with `recipe_library/import/url` and
  opens the returned draft in the edit form with `_startEdit(draft, { imported: true })`.
  The draft's photo is already stored on the server, so leaving the form or the
  add view (also while it still loads) releases it with `image/discard`. If the
  draft has no photo, `image_issue` tells the form which hint to show.
- The card talks to the integration through the WebSocket commands in
  `../ws_api.py`. A change is announced to subscribers before the answer to the
  request arrives, so the data is already current when a request returns.
