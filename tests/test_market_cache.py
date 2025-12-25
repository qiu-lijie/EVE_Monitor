import pytest

from eve_monitor.market_monitor import ItemRecord, LAST_ORDER_TO_CACHE


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
