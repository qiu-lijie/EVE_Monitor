import abc
import logging
import requests
import sqlite3
import sys
import threading
import time
import traceback
from calendar import timegm
from email.utils import parsedate
from plyer import notification

from .constants import (
    DB_PATH,
    TITLE,
    PUSHOVER_URL,
    APP_TOKEN,
    USER_KEY,
    DESKTOP_NOTIFICATION,
    PUSHOVER_NOTIFICATION,
    DEBUG,
)

ESI_PAGE_KEY = "X-Pages"


def get_module_name(name: str) -> str:
    """get module name for use as constant"""
    return name[name.rfind(".") + 1 :]


class BaseCache(abc.ABC):
    @abc.abstractmethod
    def trim(self):
        """trim cache to keep size manageable"""
        return

    @abc.abstractmethod
    def to_json_serializable(self) -> object:
        """return a json serializable representation of the cache"""
        return object()


class Core(abc.ABC):
    def __init__(
        self,
        name: str,
        session: requests.Session = None,
        threaded: threading.Event = False,
    ):
        self.name = name
        self.log = logging.getLogger(name)
        self.s = session if session else requests.Session()
        self.threaded = threaded
        if not threaded:
            self.cur = sqlite3.connect(DB_PATH).cursor()

        self.get_etags: dict[str, str] = {}
        self.next_poll: int | float = float("inf")
        return

    @abc.abstractmethod
    def main(self):
        """used by self.run in it's main loop"""
        return

    def run(self, poll_rate: int):
        # creates the cursor as SQLite objects created in a thread can only be used in that same thread
        self.cur = sqlite3.connect(DB_PATH).cursor()
        try:
            while True:
                if time.time() >= self.next_poll or self.next_poll == float("inf"):
                    self.next_poll = float("inf")
                    self.main()
                    if self.next_poll == float("inf"):
                        self.log.warning(
                            "No next poll time fetched, defaulting to fixed interval polling"
                        )
                    else:
                        self.log.info(
                            f"sleeping, next poll after {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.next_poll))}"
                        )
                if self.threaded.wait(poll_rate * 60):
                    self.log.info("Interrupt received, exiting")
                    break
        except:
            if not DEBUG:
                error_trace = traceback.format_exc()
                self.send_notification(
                    f"Unexpected error occurred in {self.name}\n{error_trace}"
                )
            self.log.exception("Unexpected error occurred")
        return

    def send_notification(self, msg: str):
        """send desktop and pushover notification"""
        if DESKTOP_NOTIFICATION:
            try:
                if sys.platform.startswith("win"):
                    notification.notify(
                        title=TITLE,
                        message=msg[:256],
                        app_name=TITLE,
                    )
                else:  # TODO add mac support
                    self.log.warning(
                        "No supported desktop notification implementation found"
                    )
            except:
                self.log.exception("Unable to send desktop notification")

        if PUSHOVER_NOTIFICATION:
            try:
                data = {
                    "token": APP_TOKEN,
                    "user": USER_KEY,
                    "title": TITLE,
                    "message": msg,
                    "priority": 0,
                    "sound": "eve_chime",
                }
                r = self.s.post(PUSHOVER_URL, data=data)
                if r.status_code != 200:
                    raise Exception(f"Status code {r.status_code}, {r.content}")
            except:
                self.log.exception("Unable to send pushover notification")
        return

    def get(
        self,
        url: str,
        excepted_status_codes: int | tuple[int] = (200,),
        *args,
        **kwargs,
    ) -> requests.Response:
        """logs a warning if unexpected status code is received, transparently handles ETag caching"""
        if type(excepted_status_codes) == int:
            excepted_status_codes = (excepted_status_codes,)
        if url in self.get_etags:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["If-None-Match"] = self.get_etags[url]
        res = self.s.get(url, *args, **kwargs)
        if res.status_code not in excepted_status_codes:
            self.log.warning(
                f"Request failed at {res.url}, status code {res.status_code}\n\t{res.content}"
            )
        if "ETag" in res.headers:
            self.get_etags[url] = res.headers["ETag"]
        return res

    def page_aware_get(
        self,
        url: str,
        last_n_page: int = float("inf"),
        update_next_poll: bool = False,
        *args,
        **kwargs,
    ) -> list:
        """return a list of objects over potentially many pages, only keeping last n pages"""
        expected_status_codes = (200, 304)
        if "expected_status_codes" in kwargs:
            expected_status_codes = (
                *expected_status_codes,
                *kwargs.pop("expected_status_codes"),
            )
        res = self.get(url, expected_status_codes, *args, **kwargs)

        EXPIRES = "Expires"
        if update_next_poll and EXPIRES in res.headers:
            expiry = timegm(parsedate(res.headers[EXPIRES]))
            next_poll = min(self.next_poll, expiry)
            self.log.debug(
                f"resource expiry {expiry}, next poll {self.next_poll} -> {next_poll}"
            )
            self.next_poll = next_poll

        if res.status_code != 200 or len(res.content) == 0:
            return []
        if ESI_PAGE_KEY not in res.headers:
            return res.json()

        total_pages = int(res.headers.get(ESI_PAGE_KEY, 1))
        curr_page = max(1, total_pages - last_n_page)
        contents = res.json() if curr_page == 1 else []
        while curr_page < total_pages:
            curr_page += 1
            res = self.get(
                url, expected_status_codes, params={"page": curr_page}, *args, **kwargs
            )
            if res.status_code == 200 and len(res.content) > 0:
                contents += res.json()
        return contents

    def post(
        self,
        url: str,
        excepted_status_codes: int | tuple[int] = (200,),
        *args,
        **kwargs,
    ) -> requests.Response:
        """logs a warning if unexpected status code is received"""
        if type(excepted_status_codes) == int:
            excepted_status_codes = (excepted_status_codes,)
        res = self.s.post(url, *args, **kwargs)
        if res.status_code not in excepted_status_codes:
            self.log.warning(
                f"Request failed at {res.url}, status code {res.status_code}\n\t{res.content}"
            )
        return res

    def get_station_info(self, station_id: int) -> tuple[str, int, float]:
        """returns a tuple of (station_name, system_id, security)"""
        self.cur.execute(
            """select stationName, solarSystemID, security from staStations where stationID = ?""",
            (station_id,),
        )
        res = self.cur.fetchone()
        if res == None:
            return ("player citadel", 0)
        return res

    def get_system_info(self, system_id: int) -> tuple[str, float]:
        """returns a tuple of (system_name, security)"""
        self.cur.execute(
            """select solarSystemName, security from mapSolarSystems where solarSystemID = ?""",
            (system_id,),
        )
        res = self.cur.fetchone()
        if res == None:
            return ("unknown system", 0.0)
        return res
