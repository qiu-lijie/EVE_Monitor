import pytest
import time

from eve_monitor.market_monitor import (
    LAST_ORDER_TO_CACHE,
    MARKET_MONITOR,
    ItemRecord,
    MarketHistory,
)


class TestItemRecord:
    @pytest.fixture
    def item(self):
        return ItemRecord(34, "Tritanium")

    def test_init(self, item):
        assert item.type_id == 34
        assert item.name == "Tritanium"
        assert isinstance(item.orders_seen, dict)

    def test_trim_no_trimming_needed(self, item):
        item.orders_seen = {1: 100, 2: 200}
        item.trim()
        assert len(item.orders_seen) == 2
        assert item.orders_seen == {1: 100, 2: 200}

    def test_trim_removes_old_orders(self, item):
        # Add more orders than LAST_ORDER_TO_CACHE
        for i in range(LAST_ORDER_TO_CACHE + 10):
            item.orders_seen[i] = i * 10

        assert len(item.orders_seen) == LAST_ORDER_TO_CACHE + 10
        item.trim()
        assert len(item.orders_seen) == LAST_ORDER_TO_CACHE
        # Should keep the most recent orders, oldest kept item has timestamp i * 10 where i = 10
        assert all(v >= (10 * 10) for v in item.orders_seen.values())


class TestMarketHistory:
    @pytest.fixture
    def history(self):
        return MarketHistory()

    def test_init_empty(self, history):
        assert isinstance(history.items, dict)
        assert len(history.items) == 0

    def test_init_with_history_data(self):
        history_data = {
            MARKET_MONITOR: [
                {
                    "type_id": 34,
                    "name": "Tritanium",
                    "orders_seen": {"1": 100, "2": 200},
                }
            ]
        }
        history = MarketHistory(history_data)
        assert 34 in history.items
        assert history.items[34].type_id == 34
        assert history.items[34].name == "Tritanium"
        assert history.items[34].orders_seen == {1: 100, 2: 200}
        assert history_data[MARKET_MONITOR] is history

    def test_init_modifies_input_dict(self):
        history_data = {MARKET_MONITOR: []}
        history = MarketHistory(history_data)
        assert history_data[MARKET_MONITOR] is history

    def test_add_order_seen_new_item(self, history):
        time_before = int(time.time())
        history.add_order_seen(34, "Tritanium", 1001)
        time_after = int(time.time())
        assert 34 in history.items
        assert history.items[34].name == "Tritanium"
        assert 1001 in history.items[34].orders_seen
        assert time_before <= history.items[34].orders_seen[1001] <= time_after

    def test_add_order_seen_existing_item(self, history):
        history.add_order_seen(34, "Tritanium", 1001)
        history.add_order_seen(34, "Tritanium", 1002)
        assert len(history.items[34].orders_seen) == 2
        assert 1001 in history.items[34].orders_seen
        assert 1002 in history.items[34].orders_seen

    def test_is_order_seen_not_seen(self, history):
        assert history.is_order_seen(34, 1001) is False

    def test_is_order_seen_seen(self, history):
        history.add_order_seen(34, "Tritanium", 1001)
        assert history.is_order_seen(34, 1001) is True

    def test_is_order_seen_different_type_id(self, history):
        history.add_order_seen(34, "Tritanium", 1001)
        assert history.is_order_seen(35, 1001) is False

    def test_trim(self, monkeypatch):
        def _load_targets():
            return [{"type_id": 34}, {"type_id": 36}]

        monkeypatch.setattr("eve_monitor.market_monitor.load_targets", _load_targets)
        history_data = {
            MARKET_MONITOR: [
                {
                    "type_id": 34,
                    "name": "Tritanium",
                    "orders_seen": {
                        str(i): i * 10 for i in range(LAST_ORDER_TO_CACHE + 10)
                    },
                },
                {
                    "type_id": 35,
                    "name": "Pyerite",
                    "orders_seen": {str(i): i * 20 for i in range(5)},
                },
            ]
        }
        history = MarketHistory(history_data)
        history.trim()
        assert len(history.items) == 1  # Only Tritanium should remain
        assert 34 in history.items
        assert len(history.items[34].orders_seen) == LAST_ORDER_TO_CACHE
        assert all(v >= (10 * 10) for v in history.items[34].orders_seen.values())

    def test_to_json_serializable(self, history):
        history.add_order_seen(34, "Tritanium", 1001)
        history.add_order_seen(36, "Pyerite", 2001)
        data = history.to_json_serializable()
        assert isinstance(data, list)
        assert len(data) == 2
        type_ids = {item["type_id"] for item in data}
        assert type_ids == {34, 36}
        order_ids = {list(item["orders_seen"])[0] for item in data}
        assert order_ids == {1001, 2001}
