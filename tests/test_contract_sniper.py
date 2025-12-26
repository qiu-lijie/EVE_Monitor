import pytest

from eve_monitor.contract_sniper import ContractSniper


class TestContractSniper:
    @pytest.fixture
    def contract_sniper(self):
        return ContractSniper()

    def test_should_ignore_unseen_contract(self, contract_sniper):
        assert contract_sniper.should_ignore_unseen_contract("") == True
        assert contract_sniper.should_ignore_unseen_contract("PLEX\t100\n") == True
        assert (
            contract_sniper.should_ignore_unseen_contract("PLEX\t100\nPLEX\t123\n")
            == False
        )
        assert (
            contract_sniper.should_ignore_unseen_contract(
                "PLEX\t100\nOther Item\t123\n"
            )
            == False
        )

    # def test_(self, contract_sniper):
    #     assert True == contract_sniper.should_ignore_unseen_contract(contract_sniper.get_contract_items(226413101)[0])
    #     assert False == contract_sniper.should_ignore_unseen_contract(contract_sniper.get_contract_items(226414056)[0])
