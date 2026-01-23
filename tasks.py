import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time

from eve_monitor.constants import (
    SETTINGS,
    DEBUG,
    SETTINGS_DIR,
    LOG_TO_FILE,
    LOGS_DIR,
    MAIN_LOG_FILE,
    ERROR_LOG_FILE,
    NOTIFICATION_LOG_FILE,
    NOTIFICATION_LOG,
)
from eve_monitor.contract_sniper import CONTRACT_SNIPER, ContractSniper
from eve_monitor.core import BaseHistory
from eve_monitor.market_monitor import MARKET_MONITOR, MarketMonitor


MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 1
FEATURES = SETTINGS["features_enabled"]
POLL_RATE = SETTINGS["poll_rate_in_min"]
HISTORY_JSON = SETTINGS_DIR + "history.json"
if not os.path.exists(HISTORY_JSON):
    json.dump({}, open(HISTORY_JSON, "w+", encoding="utf-8", newline="\n"))

history_file = json.load(open(HISTORY_JSON, "r", encoding="utf-8"))
event = threading.Event()
features = []
threads = []


def config_logging():
    handlers = [logging.StreamHandler()]
    file_handler_args = {
        "mode": "a+",
        "maxBytes": MAX_LOG_SIZE,
        "backupCount": BACKUP_COUNT,
        "encoding": "utf-8",
    }
    if LOG_TO_FILE:
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)
        main_log_handler = logging.handlers.RotatingFileHandler(
            MAIN_LOG_FILE, **file_handler_args
        )
        error_log_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE, **file_handler_args
        )
        error_log_handler.setLevel(logging.WARNING)
        handlers += [main_log_handler, error_log_handler]

    logging.basicConfig(
        format="%(asctime)s %(name)15s %(levelname)s\t%(message)s",
        level=logging.INFO,
        handlers=handlers,
    )
    logging.getLogger("urllib3").setLevel(logging.INFO)

    notification_log = logging.getLogger(NOTIFICATION_LOG)
    notification_log.handlers.clear()
    notification_log.propagate = False
    if LOG_TO_FILE:
        notification_log.addHandler(
            logging.handlers.RotatingFileHandler(
                NOTIFICATION_LOG_FILE, **file_handler_args
            )
        )
    return


def dump_history(history: dict[str, BaseHistory]):
    """cleanup then dump history to file system"""
    for k in history:
        if issubclass(type(history[k]), BaseHistory):
            history[k].trim()
    temp_history = HISTORY_JSON + ".tmp"
    json.dump(
        history,
        open(temp_history, "w+", encoding="utf-8", newline="\n"),
        indent=4 if DEBUG else None,
        default=lambda c: c.to_json_serializable(),
    )
    os.replace(temp_history, HISTORY_JSON)
    return


def handle_interrupt(_, __):
    """dump file history then exist when interrupt"""
    event.set()
    for thread in threads:
        thread.join()
    dump_history(history_file)
    sys.exit(0)
    return


def main():
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)
    config_logging()

    if FEATURES[MARKET_MONITOR]:
        features.append(MarketMonitor(history_file, threaded=event))
    if FEATURES[CONTRACT_SNIPER]:
        features.append(ContractSniper(history_file, threaded=event))

    for feature in features:
        t = threading.Thread(target=feature.run, args=(POLL_RATE,))
        t.start()
        threads.append(t)

    if features == []:
        logging.error("Improperly configured, enable some features in settings")
    while True:
        time.sleep(60 * 60)
        dump_history(history_file)


if __name__ == "__main__":
    main()
