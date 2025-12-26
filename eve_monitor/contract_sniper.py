import time
from operator import itemgetter

from .constants import APPRAISAL_URL, APPRAISAL_API_KEY, ESI_URL, REGIONS
from .core import BaseCache, Core, get_module_name

CONTRACT_SNIPER = get_module_name(__name__)
ARBITRAGE_THRESHOLD = 0.5
MIN_VALUE_THRESHOLD = 100_000_000
MIN_PULL_INTERVAL = 30 * 60  # cached for 30 min on ESI side
LAST_CONTRACTS_TO_CACHE = 3000  # 1000 per page, last 3 pages


class ContractCache(BaseCache):
    def __init__(self, cache: dict = None):
        """
        optionally takes a dict loaded from file cache, loaded the CONTRACT_SNIPER part if available
        modify input cache to point to initialized object if given
        """
        self.contracts: dict[int, dict[int, int]] = {}
        if cache != None and CONTRACT_SNIPER in cache:
            region_contracts = cache[CONTRACT_SNIPER]
            for k, v in region_contracts.items():
                self.contracts[int(k)] = {int(cid): t for cid, t in v.items()}
        if cache != None:
            cache[CONTRACT_SNIPER] = self
        return

    def trim(self):
        for region_id in self.contracts:
            if len(self.contracts[region_id]) <= LAST_CONTRACTS_TO_CACHE:
                continue
            contracts = [(cid, t) for cid, t in self.contracts[region_id].items()]
            contracts.sort(key=lambda c: c[1], reverse=True)
            self.contracts[region_id] = {
                cid: t for cid, t in contracts[:LAST_CONTRACTS_TO_CACHE]
            }
        return

    def to_json_serializable(self) -> dict[int, dict[int, int]]:
        return self.contracts

    def add_contract_seen(self, region_id: int, contract_id: int):
        if region_id not in self.contracts:
            self.contracts[region_id] = {}
        self.contracts[region_id][contract_id] = int(time.time())
        return

    def is_contract_seen(self, region_id: int, contract_id: int) -> bool:
        if region_id not in self.contracts:
            return False
        return contract_id in self.contracts[region_id]


class ContractSniper(Core):
    def __init__(self, cache: dict = None, *args, **kwargs):
        self.cache = ContractCache(cache)
        self.last_fetched: float = 0
        return super().__init__(CONTRACT_SNIPER, *args, **kwargs)

    def search_contract_in_region(self, region_id: int) -> list[dict]:
        """returns all unseen item exchange contracts in a region"""
        # TODO make use of Etag and If-None-Match maybe?
        res = self.get(ESI_URL + f"/contracts/public/{region_id}", 200)
        if res.status_code != 200:
            return []

        curr_page = 1
        curr_content = res.json()
        while res.status_code == 200:
            prev_content = curr_content
            curr_content = res.json()
            curr_page += 1
            self.log.debug(f"Attempting next page {curr_page}")
            res = self.get(
                ESI_URL + f"/contracts/public/{region_id}",
                (200, 404),
                params={"page": curr_page},
            )

        if curr_page == 2:
            content = curr_content
        else:
            content = prev_content + curr_content

        contracts = []
        for contract in content:
            contract_id = contract["contract_id"]
            if contract["type"] != "item_exchange":
                self.log.debug(f"Ignoring non item exchange contract {contract_id}")
                continue
            if self.cache.is_contract_seen(region_id, contract_id):
                self.log.debug(f"Ignoring previously seen contract {contract_id}")
                continue
            contracts.append(contract)
        return contracts

    def get_contract_items(self, contract_id: int) -> tuple[str, str]:
        """returns a tuple of (items sold, items requested), ignoring blue print copy"""
        # since contracts routes are cached for longer, sometimes we are querying already completed contracts
        # ESI either returns 204, or 200 with empty content
        res = self.get(ESI_URL + f"/contracts/public/items/{contract_id}", (200, 204))
        if res.status_code != 200 or len(res.content) == 0:
            return ("", "")

        items = res.json()
        sold, requested = "", ""
        for item in items:
            if item.get("is_blueprint_copy", False):
                continue

            is_included, quantity, type_id = itemgetter(
                "is_included", "quantity", "type_id"
            )(item)
            self.cur.execute(
                """
                select typeName from invTypes where typeID = ?
                """,
                (type_id,),
            )
            res = self.cur.fetchone()
            if not res:  # TODO temp fix, try to see if abyssal mods can be added to DB
                self.log.warning(
                    f"typeID {type_id} not found, likely abyssal related item"
                )
                continue

            type_name = res[0]
            if is_included:
                sold += f"{type_name}\t{quantity}\n"
            else:
                requested += f"{type_name}\t{quantity}\n"
        return (sold, requested)

    def get_appraisal_value(self, items: str, buy: bool = False) -> float:
        """returns appraisal value from third party website"""
        if items == "":
            return 0

        res = self.post(
            APPRAISAL_URL,
            200,
            headers={
                "X-ApiKey": APPRAISAL_API_KEY,
                "Accept": "application/json",
                "Content-Type": "text/plain",
            },
            params={"market": 2, "persist": False, "compactize": True},
            data=items.encode("utf-8"),
        )
        if res.status_code != 200:
            return 0

        res = res.json()
        return (
            res["effectivePrices"]["totalSellPrice"]
            if buy
            else res["effectivePrices"]["totalBuyPrice"]
        )

    def get_character_name(self, character_id: int) -> str:
        """Returns the character name of given character id, "" otherwise"""
        res = self.get(ESI_URL + f"/characters/{character_id}/", 200)
        if res.status_code != 200:
            return ""
        return res.json()["name"]

    def should_ignore_unseen_contract(self, sold: str) -> bool:
        """ignores contracts returned no parsed sold item, or only one single PLEX item"""
        return sold == "" or (
            sold[: sold.find("\t")] == "PLEX" and sold[sold.find("\n") :] == "\n"
        )

    def watch_contract(self):
        """watch for low priced low volume contract"""
        if time.time() < self.last_fetched + MIN_PULL_INTERVAL:
            return self.log.info("Last pulled within ESI cache period, no op")
        self.last_fetched = time.time()

        for region in REGIONS:
            region_name, region_id, known_space = itemgetter(
                "name", "region_id", "known_space"
            )(region)
            if not known_space:
                continue

            contracts = self.search_contract_in_region(region_id)
            self.log.info(
                f"Found {len(contracts)} unseen contracts in {region_name} ({region_id})"
            )
            for contract in contracts:
                contract_id, issuer_id, price, title, volume, station_id = itemgetter(
                    "contract_id",
                    "issuer_id",
                    "price",
                    "title",
                    "volume",
                    "start_location_id",
                )(contract)
                self.log.debug(f"Processing contract {contract_id} {title}")

                sold, requested = self.get_contract_items(contract_id)
                if self.should_ignore_unseen_contract(sold):
                    self.log.debug(f"Ignoring buy or BPC only contract {contract_id}")
                    self.cache.add_contract_seen(region_id, contract_id)
                    continue

                sold_price = self.get_appraisal_value(sold)
                requested_price = self.get_appraisal_value(requested, True)
                value = sold_price - requested_price
                station_name, system_id, *_ = self.get_station_info(station_id)
                system_name, security = self.get_system_info(system_id)
                msg = (
                    (f'Contract "{title}"' if title else "Item exchange contract")
                    + f" ({contract_id}) priced at {price:,.0f} isk, valued at {value:,.0f} isk, with {volume:,.0f} m3 volume"
                    + f"\n\tlocated in {station_name}, {system_name} (sec {security:.2}), {region_name}"
                    + f"\n\tselling {sold_price:,} isk\n{sold}"
                    + (
                        f"\n\trequesting {requested_price:,} isk\n{requested}"
                        if requested
                        else ""
                    )
                )
                self.log.debug(msg)

                if (
                    sold_price * ARBITRAGE_THRESHOLD >= (price + requested_price)
                    and value >= MIN_VALUE_THRESHOLD
                ):
                    issuer = self.get_character_name(issuer_id)
                    msg = f"{issuer}'s " + msg
                    self.log.info(msg)
                    self.send_notification(msg)

                self.cache.add_contract_seen(region_id, contract_id)
        return

    main = watch_contract
