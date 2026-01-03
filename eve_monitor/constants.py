import json


TITLE = "EVE Market Monitor"
ESI_URL = "https://esi.evetech.net/latest"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

SETTINGS_DIR = "./settings/"
TARGETS_JSON = SETTINGS_DIR + "targets.json"
TARGETS = json.load(open(TARGETS_JSON, "r", encoding="utf-8"))
REGIONS_JSON = SETTINGS_DIR + "regions.json"
REGIONS = json.load(open(REGIONS_JSON, "r", encoding="utf-8"))
SETTINGS = json.load(open(SETTINGS_DIR + "appsettings.json", "r", encoding="utf-8"))
APP_TOKEN = SETTINGS["APP_TOKEN"]
USER_KEY = SETTINGS["USER_KEY"]
DB_PATH = SETTINGS["DB_PATH"]
DEBUG = SETTINGS["DEBUG"]
DESKTOP_NOTIFICATION = SETTINGS.get("DESKTOP_NOTIFICATION", True)
PUSHOVER_NOTIFICATION = SETTINGS.get("PUSHOVER_NOTIFICATION", True)

APPRAISAL_URL = SETTINGS["APPRAISAL_URL"]
APPRAISAL_API_KEY = SETTINGS["APPRAISAL_API_KEY"]
