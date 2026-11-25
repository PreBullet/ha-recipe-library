"""Constants for the Recipe Library integration."""

# Integration domain; must match the folder name and manifest.json.
DOMAIN = "recipe_library"

# Display name used for the config entry.
NAME = "Recipe Library"

# Persistence: stored in <config>/.storage/recipe_library
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
SAVE_DELAY = 1  # seconds; changes are written shortly after the last edit

# Dispatcher signal sent whenever recipes or tags change.
SIGNAL_CHANGED = f"{DOMAIN}_changed"

# Dashboard card: file name in ./frontend and the URL it is served under.
CARD_FILENAME = "recipe-library-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
