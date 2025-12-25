import dataclasses
import json
import time
from operator import itemgetter

from .constants import ESI_URL, TARGETS_JSON, REGIONS_JSON, REGIONS
from .core import Core, get_module_name

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


class MarketMonitor(Core):
    def __init__(self, *args, **kwargs):
        # only stores order_ids that has been sent to client
        self.order_ids_seen = set()
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
        Returns:
            Returns list of order found, [] otherwise
        Note, no pagination as the assumption is there will be less then 1000 orders for any given type
            as ESI page size seems to be 1000. Only really matter for PLEX
        """
        res = self.get(
            ESI_URL + f"/markets/{region_id}/orders/",
            200,
            params={"type_id": type_id, "order_type": order_type},
        )
        if res.status_code != 200:
            return []

        res = res.json()
        if len(res) >= 1000:
            self.log.warning(
                f"fetching for type {type_id} in region {region_id} returns more than 1000 orders"
            )
        return res

    def watch_market(self, cache: dict[str, list[int]] = None):
        """watch market orders for items in TARGETS.market_monitor"""
        if cache != None and MARKET_MONITOR in cache:
            self.order_ids_seen = set(cache[MARKET_MONITOR])
        if cache != None:
            cache[MARKET_MONITOR] = self.order_ids_seen

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
                    if price <= threshold and order_id not in self.order_ids_seen:
                        system = self.get_system_info(system_id)[0]
                        msg = f"{name} selling for {price:,.0f} isk in {system}, {region_name}, {volume_remain}/{volume_total}"
                        self.log.info(msg)
                        self.send_notification(msg)
                        self.order_ids_seen.add(order_id)

            if orders_seen == 0:
                self.log.warning(f"Done looking for {name}, no order found")
        return

    main = watch_market
