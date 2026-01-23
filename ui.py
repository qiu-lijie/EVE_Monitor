import logging
import multiprocessing
import select
import signal
import subprocess
import sys
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from eve_monitor.constants import MAIN_LOG_FILE, ERROR_LOG_FILE, NOTIFICATION_LOG_FILE
from tasks import main


UPDATE = "update"
SEND_LAST_LINES = 500

app = Flask(
    __name__, static_folder="frontend/static", template_folder="frontend/templates"
)
socketio = SocketIO(app)
logger = logging.getLogger(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/notifications")
@app.route("/errors")
def static_logs():
    log_file_mapping = {
        "/notifications": NOTIFICATION_LOG_FILE,
        "/errors": ERROR_LOG_FILE,
    }
    lines = tail(log_file_mapping[request.path], SEND_LAST_LINES)
    lines = [str(line, "utf-8") for line in lines]
    return render_template("static_logs.html", logs=lines)


@socketio.on("connect")
def handle_connect():
    logger.info("client connected")
    lines = tail(MAIN_LOG_FILE, SEND_LAST_LINES)
    res = "Connected\n"
    for line in lines:
        res += str(line, "utf-8")
    emit(UPDATE, (res, True))
    return


def tail(file: str, n: int) -> list[bytes]:
    """return last n lines from file f with unix tail"""
    proc = subprocess.Popen(["tail", "-n", str(n), file], stdout=subprocess.PIPE)
    if proc.stdout == None:  # only to suppress type warnings
        raise Exception("unexpected error")
    lines = proc.stdout.readlines()
    return lines


event = threading.Event()


def update():
    """broadcast log updates to connected clients"""
    f = subprocess.Popen(
        ["tail", "-Fn", "0", MAIN_LOG_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p = select.poll()
    if f.stdout == None:  # only to suppress type warnings
        raise Exception("unexpected error")
    p.register(f.stdout)
    while True:
        if p.poll(1):
            line = str(f.stdout.readline(), "utf-8")
            if line != "":
                socketio.emit(UPDATE, line)
        if event.is_set():
            break
    return


def handle_interrupt(_, __):
    event.set()
    logger.info("Interrupt received, exiting")
    sys.exit(0)
    return


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_interrupt)
    multiprocessing.Process(target=main).start()
    threading.Thread(target=update).start()
    socketio.run(app)
