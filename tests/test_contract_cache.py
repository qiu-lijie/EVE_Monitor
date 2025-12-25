from eve_monitor.contract_sniper import (
    LAST_CONTRACTS_TO_CACHE,
    CONTRACT_SNIPER,
    ContractCache,
)


class TestContractCache:
    def test_init_empty(self):
        """Test initialization with no cache"""
        cache = ContractCache()
        assert cache.contracts == {}

    def test_init_with_cache(self):
        """Test initialization with existing cache dict"""
        existing_cache = {
            CONTRACT_SNIPER: {
                "123": {"456": 1000, "789": 2000},
                "234": {"111": 3000},
            }
        }
        cache = ContractCache(existing_cache)
        assert 123 in cache.contracts
        assert 234 in cache.contracts
        assert cache.contracts[123][456] == 1000
        assert cache.contracts[123][789] == 2000
        assert cache.contracts[234][111] == 3000
        assert existing_cache[CONTRACT_SNIPER] is cache

    def test_init_with_cache_missing_key(self):
        """Test initialization with cache dict that doesn't have CONTRACT_SNIPER key"""
        existing_cache = {"other_key": {}}
        cache = ContractCache(existing_cache)
        assert cache.contracts == {}
        assert existing_cache[CONTRACT_SNIPER] is cache

    def test_to_json_serializable(self):
        """Test conversion to JSON serializable format"""
        cache = ContractCache()
        cache.contracts = {123: {456: 1000, 789: 2000}, 234: {111: 3000}}
        result = cache.to_json_serializable()
        assert result == cache.contracts
        assert result[123][456] == 1000

    def test_trim_no_trimming_needed(self):
        """Test trim when contracts are under the threshold"""
        cache = ContractCache()
        cache.contracts = {123: {456: 1000, 789: 2000}}
        cache.trim()
        assert len(cache.contracts[123]) == 2

    def test_trim_excess_contracts(self):
        """Test trim removes excess contracts keeping newest"""
        cache = ContractCache()
        contracts = {i: i * 100 for i in range(LAST_CONTRACTS_TO_CACHE + 50)}
        cache.contracts = {123: contracts}
        cache.trim()
        assert len(cache.contracts[123]) == LAST_CONTRACTS_TO_CACHE
        # Check that newest contracts are kept (highest timestamps)
        kept_timestamps = list(cache.contracts[123].values())
        assert max(kept_timestamps) == (LAST_CONTRACTS_TO_CACHE + 49) * 100
        assert min(kept_timestamps) == 50 * 100

    def test_trim_multiple_regions(self):
        """Test trim works across multiple regions"""
        cache = ContractCache()
        cache.contracts = {
            123: {i: i * 100 for i in range(LAST_CONTRACTS_TO_CACHE + 10)},
            234: {i: i * 100 for i in range(50)},
        }
        cache.trim()
        assert len(cache.contracts[123]) == LAST_CONTRACTS_TO_CACHE
        assert len(cache.contracts[234]) == 50

    def test_add_and_check_contract_seen(self):
        """Test adding and checking seen contracts"""
        cache = ContractCache()
        cache.add_contract_seen(123, 456)
        assert cache.is_contract_seen(123, 456) is True
        assert cache.is_contract_seen(123, 789) is False
        assert cache.is_contract_seen(234, 456) is False
