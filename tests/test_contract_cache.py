from eve_monitor.contract_sniper import (
    LAST_CONTRACTS_TO_CACHE,
    CONTRACT_SNIPER,
    ContractHistory,
)


class TestContractHistory:
    def test_init_empty(self):
        """Test initialization with no history"""
        history = ContractHistory()
        assert history.contracts == {}

    def test_init_with_history(self):
        """Test initialization with existing history dict"""
        existing_history = {
            CONTRACT_SNIPER: {
                "123": {"456": 1000, "789": 2000},
                "234": {"111": 3000},
            }
        }
        history = ContractHistory(existing_history)
        assert 123 in history.contracts
        assert 234 in history.contracts
        assert history.contracts[123][456] == 1000
        assert history.contracts[123][789] == 2000
        assert history.contracts[234][111] == 3000
        assert existing_history[CONTRACT_SNIPER] is history

    def test_init_with_history_missing_key(self):
        """Test initialization with history dict that doesn't have CONTRACT_SNIPER key"""
        existing_history = {"other_key": {}}
        history = ContractHistory(existing_history)
        assert history.contracts == {}
        assert existing_history[CONTRACT_SNIPER] is history

    def test_to_json_serializable(self):
        """Test conversion to JSON serializable format"""
        history = ContractHistory()
        history.contracts = {123: {456: 1000, 789: 2000}, 234: {111: 3000}}
        result = history.to_json_serializable()
        assert result == history.contracts
        assert result[123][456] == 1000

    def test_trim_no_trimming_needed(self):
        """Test trim when contracts are under the threshold"""
        history = ContractHistory()
        history.contracts = {123: {456: 1000, 789: 2000}}
        history.trim()
        assert len(history.contracts[123]) == 2

    def test_trim_excess_contracts(self):
        """Test trim removes excess contracts keeping newest"""
        history = ContractHistory()
        contracts = {i: i * 100 for i in range(LAST_CONTRACTS_TO_CACHE + 50)}
        history.contracts = {123: contracts}
        history.trim()
        assert len(history.contracts[123]) == LAST_CONTRACTS_TO_CACHE
        # Check that newest contracts are kept (highest timestamps)
        kept_timestamps = list(history.contracts[123].values())
        assert max(kept_timestamps) == (LAST_CONTRACTS_TO_CACHE + 49) * 100
        assert min(kept_timestamps) == 50 * 100

    def test_trim_multiple_regions(self):
        """Test trim works across multiple regions"""
        history = ContractHistory()
        history.contracts = {
            123: {i: i * 100 for i in range(LAST_CONTRACTS_TO_CACHE + 10)},
            234: {i: i * 100 for i in range(50)},
        }
        history.trim()
        assert len(history.contracts[123]) == LAST_CONTRACTS_TO_CACHE
        assert len(history.contracts[234]) == 50

    def test_add_and_check_contract_seen(self):
        """Test adding and checking seen contracts"""
        history = ContractHistory()
        history.add_contract_seen(123, 456)
        assert history.is_contract_seen(123, 456) is True
        assert history.is_contract_seen(123, 789) is False
        assert history.is_contract_seen(234, 456) is False
