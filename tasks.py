import json
import logging
import os
import signal
import sys
import threading
import time

from eve_monitor.constants import SETTINGS
from eve_monitor.contract_sniper import CONTRACT_SNIPER, ContractSniper
from eve_monitor.market_monitor import MARKET_MONITOR, MarketMonitor

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s\t%(message)s", level=logging.INFO
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
    # CACHE_LIMIT = 100 TODO some better clean up
    # for k in cache:
    #     if len(cache[k]) > CACHE_LIMIT:
    #         cache[k] = cache[k][-CACHE_LIMIT:]
    for k in cache:
        if type(cache[k]) == set:
            cache[k] = list(cache[k])

    json.dump(cache, open(CACHE_JSON, "w+", encoding="utf-8", newline="\n"), indent=4)
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
    features.append(MarketMonitor(threaded=event))
if FEATURES[CONTRACT_SNIPER]:
    features.append(ContractSniper(threaded=event))

for feature in features:
    t = threading.Thread(target=feature.run, args=(POLL_RATE, file_cache))
    t.start()
    threads.append(t)

if features == []:
    logging.error("Improperly configured, enable some features in settings")
while True:
    time.sleep(5)
