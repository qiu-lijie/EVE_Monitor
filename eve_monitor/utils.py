import logging
import requests
import sys
from plyer import notification

from .constants import (
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


class Core:
    def __init__(self, log_name: str, s: requests.Session = None):
        self.s = s if s else requests.Session()
        self.log = logging.getLogger(log_name)
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
        excepted_status_codes: int | tuple[int],
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
        excepted_status_codes: int | tuple[int],
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
