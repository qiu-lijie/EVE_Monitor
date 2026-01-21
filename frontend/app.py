import select
import subprocess
import threading
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit


app = Flask(__name__)
socketio = SocketIO(app)


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_message():
    print("Client connected")
    emit("update", "Connected")


def update():
    """broadcast log updates to connected clients"""
    f = subprocess.Popen(
        ["tail", "-F", "logs/temp.log"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p = select.poll()
    p.register(f.stdout)
    while True:
        if p.poll(1):
            line = str(f.stdout.readline(), "utf-8")
            if line != "":
                socketio.emit("update", line)
    return


if __name__ == "__main__":
    threading.Thread(target=update).start()
    socketio.run(app)
