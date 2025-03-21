import logging
import requests

from .constants import REGIONS
from .utils import get_module_name, send_notification

CONTRACT_SNIPER = get_module_name(__name__)


local_cache = []
def watch_contract(s: requests.Session, cache: {str: [str]} = None, fetch_all = False):
    """watch for low priced low volume contract"""
    if cache == None:
        order_ids_seen = local_cache
    elif CONTRACT_SNIPER in cache:
        order_ids_seen = cache[CONTRACT_SNIPER]
    else:
        cache[CONTRACT_SNIPER] = local_cache
        order_ids_seen = local_cache

    for region in REGIONS:
        pass
    return
