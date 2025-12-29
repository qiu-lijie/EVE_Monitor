import json
import logging
import os
import signal
import sys
import threading
import time

from eve_monitor.constants import SETTINGS, DEBUG
from eve_monitor.contract_sniper import CONTRACT_SNIPER, ContractSniper
from eve_monitor.core import BaseCache
from eve_monitor.market_monitor import MARKET_MONITOR, MarketMonitor

logging.basicConfig(
    format="%(asctime)s %(name)15s %(levelname)s\t%(message)s", level=logging.INFO
)
logging.getLogger("urllib3").setLevel(logging.INFO)

FEATURES = SETTINGS["features_enabled"]
POLL_RATE = SETTINGS["poll_rate_in_min"]
CACHE_JSON = "cache.json"
if not os.path.exists(CACHE_JSON):
    json.dump({}, open(CACHE_JSON, "w+", encoding="utf-8", newline="\n"), indent=4)

file_cache = json.load(open(CACHE_JSON, "r", encoding="utf-8"))
event = threading.Event()
features = []
threads = []


def dump_cache(cache: dict[str, list[str]]):
    """cleanup then dump cache to file system"""
    for k in cache:
        if issubclass(type(cache[k]), BaseCache):
            cache[k].trim()
    json.dump(
        cache,
        open(CACHE_JSON, "w+", encoding="utf-8", newline="\n"),
        indent=4 if DEBUG else None,
        default=lambda c: c.to_json_serializable(),
    )
    return


def handle_interrupt(_, __):
    """dump file cache then exist when interrupt"""
    event.set()
    for thread in threads:
        thread.join()
    dump_cache(file_cache)
    sys.exit(0)
    return


signal.signal(signal.SIGINT, handle_interrupt)

if FEATURES[MARKET_MONITOR]:
    features.append(MarketMonitor(file_cache, threaded=event))
if FEATURES[CONTRACT_SNIPER]:
    features.append(ContractSniper(file_cache, threaded=event))

for feature in features:
    t = threading.Thread(target=feature.run, args=(POLL_RATE,))
    t.start()
    threads.append(t)

if features == []:
    logging.error("Improperly configured, enable some features in settings")
while True:
    time.sleep(1000)
