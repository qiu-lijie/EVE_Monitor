import logging
import operator
import sqlite3
import requests
import time

from .constants import APPRAISAL_URL, APPRAISAL_API_KEY, ESI_URL, DB_PATH, REGIONS
from .utils import get_module_name, send_notification

CONTRACT_SNIPER = get_module_name(__name__)
ARBITRAGE_THRESHOLD = 0.2
MIN_VALUE_THRESHOLD = 100_000_000

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# unlike orders, contracts are immutable upon creation, hence all contract seen can be added
contract_ids_seen: set[int] = set()


def search_contract_in_region(s: requests.Session, region_id: int) -> list[object]:
    """returns all unseen item exchange contracts in a region"""
    # TODO make use of Etag and If-None-Match maybe?
    res = s.get(ESI_URL + f"/contracts/public/{region_id}")
    if res.status_code != 200:
        logging.warning(
            f"Request failed, status code {res.status_code}\n\t{res.content}"
        )
        return []

    res = res.json()
    return [
        contract
        for contract in res
        if contract["type"] == "item_exchange"
        and contract["contract_id"] not in contract_ids_seen
    ]


def get_contract_items(s: requests.Session, contract_id: int) -> tuple[str, str]:
    """returns a tuple of (items sold, items requested), ignoring blue print copy"""
    res = s.get(ESI_URL + f"/contracts/public/items/{contract_id}")
    if res.status_code != 200:
        logging.warning(
            f"Request failed, status code {res.status_code}\n\t{res.content}"
        )
        return ("", "")

    items = res.json()
    sold = ""
    requested = ""
    for item in items:
        if item.get("is_blueprint_copy", False):
            continue

        (is_included, quantity, type_id) = operator.itemgetter(
            "is_included", "quantity", "type_id"
        )(item)
        cur.execute(
            """
            select typeName from invTypes where typeID = ?
            """,
            (type_id,),
        )
        res = cur.fetchone()
        if not res:  # TODO temp fix, try to see if abyssal mods can be added to DB
            logging.warning(f"typeID {type_id} not found, likely abyssal related item")
            continue

        type_name = res[0]
        if is_included:
            sold += f"{type_name}\t{quantity}\n"
        else:
            requested += f"{type_name}\t{quantity}\n"
    return (sold, requested)


def get_appraisal_value(s: requests.Session, items: str, buy: bool = False) -> float:
    """returns appraisal value from third party website"""
    if items == "":
        return 0

    res = s.post(
        APPRAISAL_URL,
        headers={
            "X-ApiKey": APPRAISAL_API_KEY,
            "Accept": "application/json",
            "Content-Type": "text/plain",
        },
        params={"market": 2, "persist": False, "compactize": True},
        data=items.encode("utf-8"),
    )
    if res.status_code != 200:
        logging.warning(
            f"Request failed, status code {res.status_code}\n\t{res.content}"
        )
        raise Exception("TODO get API key?")
        return 0

    res = res.json()
    return (
        res["effectivePrices"]["totalSellPrice"]
        if buy
        else max(
            res["effectivePrices"]["totalSellPrice"],
            res["effectivePrices"]["totalBuyPrice"],
        )
    )


def get_character_name(s: requests.Session, character_id: int) -> str:
    """Returns the character name of given character id, "" otherwise"""
    res = s.get(ESI_URL + f"/characters/{character_id}/")
    if res.status_code != 200:
        logging.warning(
            f"Request failed, status code {res.status_code}\n\t{res.content}"
        )
        return ""
    return res.json().get("name")


def watch_contract(s: requests.Session, cache: dict[str, list[str]] = None):
    """watch for low priced low volume contract"""
    global contract_ids_seen
    if cache != None and CONTRACT_SNIPER in cache:
        contract_ids_seen = set(cache[CONTRACT_SNIPER])
        cache[CONTRACT_SNIPER] = contract_ids_seen
    elif cache != None:
        cache[CONTRACT_SNIPER] = contract_ids_seen

    for region in REGIONS:
        (region_name, region_id, known_space) = operator.itemgetter(
            "name", "region_id", "known_space"
        )(region)
        if not known_space:
            continue

        logging.debug(f"Looking for contracts in {region_name}")
        contracts = search_contract_in_region(s, region_id)
        for contract in contracts:
            (contract_id, issuer_id, price, title, volume) = operator.itemgetter(
                "contract_id", "issuer_id", "price", "title", "volume"
            )(contract)
            logging.debug(f"Processing contract {contract_id} {title}")

            (sold, requested) = get_contract_items(s, contract_id)
            if sold == "":
                contract_ids_seen.add(contract_id)
                logging.debug("Ignoring buy only or bpc only contract")
                continue

            sold_price = get_appraisal_value(s, sold)
            requested_price = get_appraisal_value(s, requested, True)
            value = sold_price - requested_price
            base_msg = (
                f"Contract {title if title else 'item exchange'} priced at {price:,.0f} isk, valued at {value:,.0f} isk, with {volume:,.0f} m3 volume"
                + f"\n\tselling {sold_price:,} isk\n{sold}"
                + (
                    f"\n\trequesting {requested_price:,} isk\n{requested}"
                    if requested
                    else ""
                )
            )
            logging.debug(base_msg)

            if (
                sold_price * ARBITRAGE_THRESHOLD >= (price + requested_price)
                and value >= MIN_VALUE_THRESHOLD
            ):
                issuer = get_character_name(s, issuer_id)
                msg = (
                    f"The following contract by {issuer} is under valued, consider buying it"
                    + base_msg
                )
                logging.info(msg)
                send_notification(s, msg)

            contract_ids_seen.add(contract_id)
            time.sleep(1)
    return
