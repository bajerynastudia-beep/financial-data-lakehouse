import pytest
import requests

from conftest import FakeResponse
from fin_lakehouse.http_client import SourceError, get_with_retry


class Session:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def test_retries_transient_errors_then_succeeds():
    s = Session([requests.ConnectionError("down"), FakeResponse(503), FakeResponse(200, "ok")])
    sleeps = []
    resp = get_with_retry("https://x", session=s, max_retries=3, backoff_s=1, sleep=sleeps.append)
    assert resp.text == "ok"
    assert s.calls == 3
    assert sleeps == [1, 2]  # rosnący odstęp


def test_404_is_returned_not_raised():
    s = Session([FakeResponse(404, "Brak danych")])
    assert get_with_retry("https://x", session=s, sleep=lambda _: None).status_code == 404


def test_client_error_is_not_retried():
    s = Session([FakeResponse(400, "Bad Request - Przekroczony limit")])
    with pytest.raises(SourceError, match="400"):
        get_with_retry("https://x", session=s, sleep=lambda _: None)
    assert s.calls == 1


def test_gives_up_after_max_retries():
    s = Session([FakeResponse(500)] * 3)
    with pytest.raises(SourceError, match="3 próbach"):
        get_with_retry("https://x", session=s, max_retries=2, sleep=lambda _: None)
