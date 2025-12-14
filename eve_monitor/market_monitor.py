import json
import logging
import operator
import requests

from .constants import ESI_URL, TARGETS_JSON, REGIONS_JSON, REGIONS
from .utils import get_module_name, send_notification

MARKET_MONITOR = get_module_name(__name__)


def get_region_info(s=None):
    """
    Get the region info, save to regions.json
    Args:
        s (requests.Session object): Session to use, will create one if none provided
    Returns:
        Returns True when successfully made all requests
    """
    if s == None:
        s = requests.Session()
    r = s.get(ESI_URL + '/universe/regions/')
    if r.status_code != 200:
        return False
    
    res = []
    for rid in r.json():
        r = s.get(ESI_URL + f'/universe/regions/{rid}/')
        if r.status_code == 200:
            r = r.json()
            res.append({
                'name': r['name'],
                'region_id': r['region_id'],
                'known_space': True if r.get('description') else False,
            })

    json.dump(res, open(REGIONS_JSON, 'w+', encoding='utf-8', newline='\n'), indent=4)
    return True


def get_item_orders_in_region(item, region, s=None, order_type='sell'):
    """
    Get the given item orders in given region
    Args:
        item (int): item type_id
        region (int): region_id
        s (requests.Session object): Session to use, will create one if none provided
        order_type (str): one of buy, sell, all; default to sell
    Returns:
        Returns list of order found, None otherwise
    """
    if s == None:
        s = requests.Session()
    res = None
    r = s.get(
        ESI_URL + f'/markets/{region}/orders/', params = {'type_id': item, 'order_type': order_type})
    if r.status_code == 200:
        res = r.json()
    return res


def get_system_name(system, s=None):
    """Returns the system name of given system id, None otherwise"""
    if s == None:
        s =requests.Session()
    res = None
    r = s.get(ESI_URL + f'/universe/systems/{system}/')
    if r.status_code == 200:
        res = r.json().get('name')
    return res


local_cache = []
def watch_market(s: requests.Session, cache: {str: [str]} = None):
    """watch market orders for items in TARGETS.market_monitor"""
    if cache == None:
        order_ids_seen = local_cache
    elif MARKET_MONITOR in cache:
        order_ids_seen = cache[MARKET_MONITOR]
    else:
        cache[MARKET_MONITOR] = local_cache
        order_ids_seen = local_cache
    # load each time to enable hot reload
    targets = json.load(open(TARGETS_JSON))[MARKET_MONITOR]

    for target in targets:
        orders_seen = 0
        res = []
        type_id = target['type_id']
        name = target['name']
        tres = target['threshold']
        tar_region_id = target.get('region', None)
        logging.info(f'Looking for {name} below {tres:,} isk')

        for region in REGIONS:
            (region_name, region_id, known_space) = operator.itemgetter('name', 'region_id', 'known_space')(region)
            if ((tar_region_id != None and tar_region_id != region_id) 
                or (tar_region_id == None and not known_space)): continue

            orders = get_item_orders_in_region(type_id, region_id, s)
            if not orders: continue
            orders_seen += len(orders)
            for o in orders:
                if o['price'] <= tres and o['order_id'] not in order_ids_seen:
                    order_ids_seen.append(o['order_id'])
                    system = get_system_name(o['system_id'], s)
                    out = f"{name} selling for {o['price']:,.0f} isk in {system}, {region_name}, {o['volume_remain']}/{o['volume_total']}"
                    logging.info(out)
                    res.append(out)

        if orders_seen == 0:
            logging.warning(f'Done looking for {name}, no order found')

        for msg in res:
            send_notification(s, msg)
    return
