from app.core.config import settings

# Google Veo Configuration
GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID
GOOGLE_CLOUD_LOCATION = settings.GOOGLE_CLOUD_LOCATION
VEO_MODEL_ID = "veo-2.0-generate-exp"  # Supports referenceImages (image-to-video)

# Runway ML Configuration
RUNWAY_API_KEY = settings.RUNWAY_API_KEY
RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_DEFAULT_MODEL = "gen4_turbo"
RUNWAY_DURATION = 5  # 5 seconds (cheaper option)

# MiniMax Configuration
MINIMAX_API_KEY = settings.MINIMAX_API_KEY
MINIMAX_BASE_URL = "https://api.minimax.io/v1"
MINIMAX_DEFAULT_MODEL = "MiniMax-Hailuo-2.3"  # I2V model