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
- The card talks to the integration through the WebSocket commands in
  `../ws_api.py`. A change is announced to subscribers before the answer to the
  request arrives, so the data is already current when a request returns.
