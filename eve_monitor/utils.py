import logging
import requests
import sys
import traceback
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


def send_notification(s: requests.Session, msg: str):
    """send desktop and pushover notification"""
    if DESKTOP_NOTIFICATION:
        try:
            if sys.platform.startswith("win"):
                notification.notify(
                    title=TITLE,
                    message=msg,
                    app_name=TITLE,
                )
            # TODO add mac support
            else:
                logging.warning(
                    "No supported desktop notification implementation found"
                )
        except:
            logging.error("Unable to send desktop notification")
            traceback.print_exc()

    if PUSHOVER_NOTIFICATION:
        try:
            data = {
                "token": APP_TOKEN,
                "user": USER_KEY,
                "title": TITLE,
                "message": msg,
                "priority": 0,
            }
            r = s.post(PUSHOVER_URL, data=data)
            if r.status_code != 200:
                raise Exception(f"Status code {r.status_code}, {r.content}")
        except:
            logging.error("Unable to send pushover notification")
            traceback.print_exc()
    return
