import dataclasses
import json
import time
from operator import itemgetter

from .constants import ESI_URL, TARGETS_JSON, REGIONS_JSON, REGIONS
from .core import BaseCache, Core, get_module_name

MARKET_MONITOR = get_module_name(__name__)
LAST_ORDER_TO_CACHE = 50


def load_targets() -> list[dict]:
    return json.load(open(TARGETS_JSON))[MARKET_MONITOR]


@dataclasses.dataclass
class ItemRecord:
    type_id: int
    name: str
    orders_seen: dict[int, int] = dataclasses.field(default_factory=dict)

    def trim(self):
        if len(self.orders_seen) <= LAST_ORDER_TO_CACHE:
            return
        orders = [(oid, t) for oid, t in self.orders_seen.items()]
        orders.sort(key=lambda o: o[1], reverse=True)
        self.orders_seen = {oid: t for oid, t in orders[:LAST_ORDER_TO_CACHE]}
        return


class MarketCache(BaseCache):
    def __init__(self, cache: dict = None):
        """
        optionally takes a dict loaded from file cache, loaded the MARKET_MONITOR part if available
        modify input cache to point to initialized object if given
        """
        self.items: dict[int, ItemRecord] = {}
        if cache != None and MARKET_MONITOR in cache:
            items = cache[MARKET_MONITOR]
            for item in items:
                type_id, name, orders_seen = itemgetter(
                    "type_id", "name", "orders_seen"
                )(item)
                self.items[type_id] = ItemRecord(
                    type_id, name, {int(oid): t for oid, t in orders_seen.items()}
                )
        if cache != None:
            cache[MARKET_MONITOR] = self
        return

    def add_order_seen(self, type_id: int, name: str, order_id: int):
        if type_id not in self.items:
            self.items[type_id] = ItemRecord(type_id=type_id, name=name)
        self.items[type_id].orders_seen[order_id] = int(time.time())
        return

    def is_order_seen(self, type_id: int, order_id: int) -> bool:
        if type_id not in self.items:
            return False
        return order_id in self.items[type_id].orders_seen

    def trim(self):
        targets = {t["type_id"] for t in load_targets()}
        items = {}
        for item in self.items.values():
            if item.type_id not in targets:
                continue
            item.trim()
            items[item.type_id] = item
        self.items = items
        return

    def to_json_serializable(self) -> list:
        return [dataclasses.asdict(item) for item in self.items.values()]


class MarketMonitor(Core):
    def __init__(self, cache: dict = None, *args, **kwargs):
        # only stores order_ids that has been sent to client
        self.cache = MarketCache(cache)
        return super().__init__(MARKET_MONITOR, *args, **kwargs)

    def get_region_info(self):
        """
        Get the region info, save to regions.json
        Returns True when successfully made all requests
        """
        res = self.get(ESI_URL + "/universe/regions/", 200)
        if res.status_code != 200:
            return False

        regions = []
        for region_id in res.json():
            res = self.get(ESI_URL + f"/universe/regions/{region_id}/", 200)
            if res.status_code != 200:
                continue
            res = res.json()
            regions.append(
                {
                    "name": res["name"],
                    "region_id": res["region_id"],
                    "known_space": True if res.get("description") else False,
                }
            )

        json.dump(
            regions, open(REGIONS_JSON, "w+", encoding="utf-8", newline="\n"), indent=4
        )
        return True

    def get_item_orders_in_region(
        self, type_id: int, region_id: int, order_type: str = "sell"
    ):
        """
        Get the given item orders in given region
        Args:
            order_type (str): one of "buy", "sell", "all"; default to sell
        Returns a list of order found, [] otherwise
        """
        return self.page_aware_get(
            ESI_URL + f"/markets/{region_id}/orders/",
            update_next_poll=True,
            params={"type_id": type_id, "order_type": order_type},
        )

    def watch_market(self):
        """watch market orders for items in TARGETS.market_monitor"""
        # load each time to enable hot reload
        targets = load_targets()
        for target in targets:
            orders_seen = 0
            tar_region_id = target.get("region", None)
            type_id, name, threshold = itemgetter("type_id", "name", "threshold")(
                target
            )
            self.log.info(f"Looking for {name} below {threshold:,} isk")

            for region in REGIONS:
                region_name, region_id, known_space = itemgetter(
                    "name", "region_id", "known_space"
                )(region)
                if (tar_region_id != None and tar_region_id != region_id) or (
                    tar_region_id == None and not known_space
                ):
                    continue

                orders = self.get_item_orders_in_region(type_id, region_id)
                orders_seen += len(orders)
                self.log.debug(
                    f"Found {len(orders)} orders for {name} in {region_name}"
                )
                for order in orders:
                    order_id, price, system_id, volume_remain, volume_total = (
                        itemgetter(
                            "order_id",
                            "price",
                            "system_id",
                            "volume_remain",
                            "volume_total",
                        )(order)
                    )
                    if price <= threshold and not self.cache.is_order_seen(
                        type_id, order_id
                    ):
                        system = self.get_system_info(system_id)[0]
                        msg = f"{name} selling for {price:,.0f} isk in {system}, {region_name}, {volume_remain}/{volume_total}"
                        self.log.info(msg)
                        self.send_notification(msg)
                        self.cache.add_order_seen(type_id, name, order_id)

            if orders_seen == 0:
                self.log.warning(f"Done looking for {name}, no order found")
        return

    main = watch_market
