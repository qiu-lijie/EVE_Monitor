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
USER_AGENT = SETTINGS["USER_AGENT"]
LOG_TO_FILE = SETTINGS["LOG_TO_FILE"]

APPRAISAL_URL = SETTINGS["APPRAISAL_URL"]
APPRAISAL_API_KEY = SETTINGS["APPRAISAL_API_KEY"]

LOGS_DIR = "./logs/"
MAIN_LOG_FILE = LOGS_DIR + "main.log"
ERROR_LOG_FILE = LOGS_DIR + "error.log"
NOTIFICATION_LOG_FILE = LOGS_DIR + "notification.log"
NOTIFICATION_LOG = "notification"
