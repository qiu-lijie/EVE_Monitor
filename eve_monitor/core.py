import abc
import logging
import requests
import sqlite3
import sys
import threading
from plyer import notification

from .constants import (
    DB_PATH,
    TITLE,
    PUSHOVER_URL,
    APP_TOKEN,
    USER_KEY,
    DESKTOP_NOTIFICATION,
    PUSHOVER_NOTIFICATION,
)


def get_module_name(name: str) -> str:
    """get module name for use as constant"""
    return name[name.rfind(".") + 1 :]


class BaseCache(abc.ABC):
    @abc.abstractmethod
    def trim(self):
        """trim cache to keep size manageable"""
        return

    @abc.abstractmethod
    def to_json_serializable(self) -> str:
        """return a json serializable representation of the cache"""
        return ""


class Core(abc.ABC):
    def __init__(
        self,
        log_name: str,
        session: requests.Session = None,
        threaded: threading.Event = False,
    ):
        self.s = session if session else requests.Session()
        self.threaded = threaded
        if not threaded:
            self.cur = sqlite3.connect(DB_PATH).cursor()
        self.log = logging.getLogger(log_name)
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
                self.main()
                self.log.info("sleeping")
                if self.threaded.wait(poll_rate * 60):
                    self.log.info("Interrupt received, exiting")
                    break
        except:
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
                # TODO add mac support
                else:
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
        """logs a warning if unexpected status code is received"""
        if type(excepted_status_codes) == int:
            excepted_status_codes = (excepted_status_codes,)
        res = self.s.get(url, *args, **kwargs)
        if res.status_code not in excepted_status_codes:
            self.log.warning(
                f"Request failed at {res.url}, status code {res.status_code}\n\t{res.content}"
            )
        return res

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
