"""UI configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

# API Configuration
API_BASE_URL = os.getenv("DOCEATER_UI_API_URL", "http://192.222.54.152:8000")

# Extract admin API key from DOCEATER_API_KEYS
api_keys_str = os.getenv("DOCEATER_API_KEYS", "")
API_KEY = ""

if api_keys_str:
    # Parse format: "key1:user1,key2:user2"
    for pair in api_keys_str.split(","):
        if ":" in pair:
            key, user = pair.strip().split(":", 1)
            if "prod" in key or "admin" in user:
                API_KEY = key
                break
    # Fallback to first key if no prod/admin found
    if not API_KEY and ":" in api_keys_str:
        API_KEY = api_keys_str.split(",")[0].split(":")[0].strip()

# UI Configuration
UI_HOST = os.getenv("DOCEATER_UI_HOST", "127.0.0.1")
UI_PORT = int(os.getenv("DOCEATER_UI_PORT", "7860"))
UI_SHARE = os.getenv("DOCEATER_UI_SHARE", "false").lower() == "true"

