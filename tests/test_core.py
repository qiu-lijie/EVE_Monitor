import json
import pytest
from unittest.mock import Mock

from eve_monitor.core import ESI_PAGE_KEY, Core


URL = "http://example.com/api"


class TestCore:
    @pytest.fixture
    def session(self):
        return Mock()

    @pytest.fixture
    def core(self, monkeypatch, session):
        monkeypatch.setattr(Core, "__abstractmethods__", set())
        return Core("test_core", session)

    def basic_response(self, n_pages, status_code=200, json_data=None):
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.headers = {ESI_PAGE_KEY: str(n_pages)}
        mock_response.content = (
            json.dumps(json_data).encode("utf-8") if json_data else b""
        )
        mock_response.json.return_value = json_data or []
        return mock_response

    def setup_multiple_pages(self, session, n_pages):
        responses = {}
        for page in range(1, n_pages + 1):
            responses[page] = self.basic_response(n_pages, 200, [{"id": page}])

        def side_effect(_, params={}, **__):
            page = params.get("page", 1)
            return responses[page]

        session.get.side_effect = side_effect
        return

    def test_get_etag_caching(self, core, session):
        """Test ETag caching behavior in get method"""
        # First request returns 200 with ETag
        mock_resp1 = self.basic_response(1, 200)
        mock_resp1.headers = {"ETag": "etag123"}
        session.get.return_value = mock_resp1

        res1 = core.get(URL)
        assert res1.status_code == 200
        assert core.get_etags[URL] == "etag123"
        session.get.assert_called_with(URL)

        # Second request should include If-None-Match header
        mock_resp2 = self.basic_response(1, 304)
        session.get.return_value = mock_resp2

        res2 = core.get(URL)
        assert res2.status_code == 304
        session.get.assert_called_with(URL, headers={"If-None-Match": "etag123"})
        return

    def test_page_aware_get_single_page(self, core, session):
        """Test when response has no pagination"""
        session.get.return_value = self.basic_response(1, 200, [{"id": 1}, {"id": 2}])

        result = core.page_aware_get(URL)
        assert result == [{"id": 1}, {"id": 2}]
        assert session.get.call_count == 1
        return

    def test_page_aware_get_multiple_pages(self, core, session):
        """Test when response spans multiple pages"""
        self.setup_multiple_pages(session, 3)
        result = core.page_aware_get(URL)
        assert result == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert session.get.call_count == 3
        return

    def test_page_aware_get_last_n_pages(self, core, session):
        """Test keeping only last n pages"""
        self.setup_multiple_pages(session, 5)
        result = core.page_aware_get(URL, last_n_page=2)
        assert result == [{"id": 4}, {"id": 5}]
        assert session.get.call_count == 1 + 2  # initial + last 2 pages
        return

    def test_page_aware_get_non_200_status(self, core, session):
        """Test returns empty list on non-200 status"""
        session.get.return_value = self.basic_response(3, 304)

        result = core.page_aware_get(URL)
        assert result == []
        assert session.get.call_count == 1
        return

    def test_page_aware_get_empty_content(self, core, session):
        """Test returns empty list on empty content"""
        session.get.return_value = self.basic_response(3, 200, json_data=[])

        result = core.page_aware_get(URL)
        assert result == []
        assert session.get.call_count == 1
        return

    def test_page_aware_get_failed_page_request(self, core, session):
        """Test handles failed page requests gracefully"""
        mock_resp1 = self.basic_response(3, 200, [{"id": 1}])
        mock_resp2 = self.basic_response(1, 500)
        session.get.side_effect = [mock_resp1, mock_resp2, mock_resp1]

        result = core.page_aware_get(URL)
        # note the current behaviour is to skip that page and keep going
        assert result == [{"id": 1}, {"id": 1}]
        assert session.get.call_count == 3
        return

    def test_page_aware_get_with_kwargs(self, core, session):
        """Test passing additional kwargs to get method"""
        self.setup_multiple_pages(session, 2)

        result = core.page_aware_get(URL, headers={"Authorization": "Bearer token"})
        assert result == [{"id": 1}, {"id": 2}]
        assert session.get.call_count == 2
        session.get.assert_any_call(URL, headers={"Authorization": "Bearer token"})
        return

    def test_page_aware_get_update_next_poll(self, core, session):
        """Test updating next_poll based on Expires header"""
        mock_resp1 = self.basic_response(2, 200, [{"id": 1}])
        mock_resp1.headers["Expires"] = "Tue, 21 Oct 2025 07:28:00 GMT"
        mock_resp2 = self.basic_response(2, 200, [{"id": 2}])
        mock_resp2.headers["Expires"] = "Tue, 21 Oct 2025 08:28:00 GMT"
        session.get.side_effect = [mock_resp1, mock_resp2]

        result = core.page_aware_get(URL, update_next_poll=True)
        assert result == [{"id": 1}, {"id": 2}]
        assert session.get.call_count == 2

        expected_expiry = 1761031680  # Epoch time for "Tue, 21 Oct 2025 07:28:00 GMT"
        assert core.next_poll == expected_expiry
        return
