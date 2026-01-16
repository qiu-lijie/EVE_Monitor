import pytest

from eve_monitor.contract_sniper import ContractSniper, InventoryType


class TestContractSniper:
    @pytest.fixture
    def contract_sniper(self):
        return ContractSniper()

    def test_sort_item_dict(self, contract_sniper):
        items = {
            InventoryType(11577, "Cloaking Device II", category_name="Module"): 10,
            InventoryType(12745, "Occator", category_name="Ship"): 5,
            InventoryType(11579, "Cloaking Device IV", category_name="Module"): 20,
        }
        sorted_items = contract_sniper.sort_item_dict(items)
        assert list(sorted_items.keys()) == [
            InventoryType(12745, "Occator", category_name="Ship"),
            InventoryType(11577, "Cloaking Device II", category_name="Module"),
            InventoryType(11579, "Cloaking Device IV", category_name="Module"),
        ]

    def test_should_ignore_contract(self, contract_sniper):
        assert contract_sniper.should_ignore_contract("") == True
        assert contract_sniper.should_ignore_contract("PLEX\t100\n") == True
        assert contract_sniper.should_ignore_contract("PLEX\t100\nPLEX\t123\n") == False
        assert (
            contract_sniper.should_ignore_contract("PLEX\t100\nOther Item\t123\n")
            == False
        )

    # TODO write some integration tests
    # def test_(self, contract_sniper):
    #     assert True == contract_sniper.should_ignore_unseen_contract(contract_sniper.get_contract_items(226413101)[0])
    #     assert False == contract_sniper.should_ignore_unseen_contract(contract_sniper.get_contract_items(226414056)[0])
