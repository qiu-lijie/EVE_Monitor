import requests
import json
import sqlite3
import logging
import os

from constants import DB_PATH

logging.basicConfig(format="%(asctime)s %(levelname)s\t%(message)s", level=logging.INFO)

URL = "https://evepraisal.com/appraisal/structured.json"
MINERALS = {
    34: "Tritanium",
    35: "Pyerite",
    36: "Mexallon",
    37: "Isogen",
    38: "Nocxium",
    39: "Zydrine",
    40: "Megacyte",
    11399: "Morphite",
}
MARKET = "jita"
# MARKET = 'amarr'
MIN_PAYLOAD = {
    "market_name": MARKET,
    "items": [{"type_id": k, "name": v} for k, v in MINERALS.items()],
}
REP_EFF = 0.5
TARGETS_LST = "targets.json"
# should be base tech I item that can be produced by BPOs
TARGETS = json.load(open(TARGETS_LST))[os.path.basename(__file__).replace(".py", "")]

res = requests.post(URL, data=json.dumps(MIN_PAYLOAD))
items = res.json()["appraisal"]["items"]
min_prices = {
    i["typeID"]: min(i["prices"]["buy"]["max"], i["prices"]["sell"]["min"])
    for i in items
}
min_prices

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

items = []
for tar in TARGETS:
    # get tech I all variants
    cur.execute(
        """
        select mt.typeID, t.typeName
        from invMetaTypes mt 
            inner join invTypes t on mt.typeID = t.typeID 
        where
            mt.metaGroupID = 1
            and (mt.typeID = ? or mt.parentTypeID = ?)
        ;
        """,
        (
            tar,
            tar,
        ),
    )
    items += [{"type_id": tup[0], "name": tup[1]} for tup in cur.fetchall()]

logging.info(f"Requested for {len(items)} items at {MARKET}")
payload = {"market_name": MARKET, "items": items}
res = requests.post(URL, data=json.dumps(payload))
items = res.json()["appraisal"]["items"]
logging.info(f"Receive {len(items)} items in respond")
for item in items:
    type_id = item["typeID"]
    name = item["typeName"]
    sell_price = item["prices"]["sell"]["min"]
    cur.execute(
        """
        select materialTypeID, quantity
        from invTypeMaterials
        where 
            typeID = ?
        ;
        """,
        (type_id,),
    )
    base_value = sum(
        [
            min_prices[tup[0]] * tup[1] if tup[0] in min_prices else 0
            for tup in cur.fetchall()
        ]
    )
    value = base_value * REP_EFF
    if sell_price < value:
        logging.info(
            f"{name} selling at {sell_price:,.0f} isk, has salvage value of {value:,.0f} isk is profitable!"
        )
