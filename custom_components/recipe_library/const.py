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

# Photos: stored in <config>/.storage/recipe_library_images and served here.
IMAGES_DIRNAME = "recipe_library_images"
IMAGE_URL_BASE = f"/api/{DOMAIN}/image"
IMAGE_CLEANUP_MIN_AGE = 24 * 60 * 60  # seconds an unused upload is kept

# AI settings (options of the config entry). Each job can use its own AI Task
# entity; an empty value means the preferred AI Task entity of Home Assistant
# (Settings > System > AI).
CONF_AI_TEXT = "ai_text"  # websites and pasted text
CONF_AI_IMAGE = "ai_image"  # screenshots and photos
CONF_AI_VIDEO = "ai_video"  # videos
AI_JOBS = (CONF_AI_TEXT, CONF_AI_IMAGE, CONF_AI_VIDEO)
