import logging
import select
import subprocess
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO, emit


LOG_FILE = "logs/tasks.log"
UPDATE = "update"
SEND_LAST_LINES = 500

app = Flask(__name__)
socketio = SocketIO(app)
logger = logging.getLogger(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    logger.info("client connected")
    lines = tail(LOG_FILE, SEND_LAST_LINES)
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


def update():
    """broadcast log updates to connected clients"""
    f = subprocess.Popen(
        ["tail", "-Fn", "0", LOG_FILE],
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
    return


if __name__ == "__main__":
    threading.Thread(target=update).start()
    socketio.run(app)
