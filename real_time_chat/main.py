import os
import random
import logging
from datetime import datetime
from typing import Dict
from flask import Flask, request, session, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.middleware.proxy_fix import ProxyFix

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24)
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # Chat rooms (must match what the client sends)
    CHAT_ROOMS = ["General", "Random", "Tech", "Games"]


app = Flask(__name__)
app.config.from_object(Config)

# Handle reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set up Socket.IO
socketIO = SocketIO(
    app,
    cors_allowed_origins=app.config["CORS_ORIGINS"],
    logger=True,
    engineio_logger=True,
)

# "Database" of active users: sid -> {username, room?, connected_at}
active_users: Dict[str, dict] = {}


# Generate a guest username
def generate_guest_username() -> str:
    timestamp = datetime.now().strftime("%H%M")
    return f"Guest{timestamp}{random.randint(1000, 9999)}"


# Home route
@app.route("/")
def home():
    if "username" not in session:
        session["username"] = generate_guest_username()
        logger.info(f"New user assigned username: {session['username']}")
    return render_template(
        "index.html",
        username=session["username"],
        rooms=app.config["CHAT_ROOMS"],
    )


# Connection event
@socketIO.event
def connect():
    try:
        if "username" not in session:
            session["username"] = generate_guest_username()

        active_users[request.sid] = {
            "username": session["username"],
            "connected_at": datetime.now().isoformat(),
        }

        # Broadcast updated active users
        emit(
            "active_users",
            {"users": [user["username"] for user in active_users.values()]},
            broadcast=True,
        )
        logger.info(f"User Connected: {session['username']}")
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return False


# Disconnect event
@socketIO.event
def disconnect():
    try:
        username = None
        if request.sid in active_users:
            username = active_users[request.sid]["username"]
            del active_users[request.sid]

        emit(
            "active_users",
            {"users": [user["username"] for user in active_users.values()]},
            broadcast=True,
        )

        if username:
            logger.info(f"User disconnected: {username}")
        else:
            logger.info("User disconnected: unknown")
    except Exception as e:
        logger.error(f"Disconnection error: {str(e)}")
        return False


# Join room
@socketIO.on("join")
def on_join(data: dict):
    try:
        username = session["username"]
        room = data.get("room", "General")

        if room not in app.config["CHAT_ROOMS"]:
            logger.warning("No room available")
            return

        join_room(room)
        active_users[request.sid]["room"] = room

        emit(
            "status",
            {
                "msg": f"{username} has joined the room",
                "type": "join",
                "timestamp": datetime.now().isoformat(),
            },
            room=room,
        )

        logger.info(f"User {username} has joined room {room}")
    except Exception as e:
        logger.error(str(e))


# Leave room
@socketIO.on("leave")
def on_leave(data: dict):
    try:
        username = session["username"]
        room = data.get("room", "General")

        leave_room(room)
        if request.sid in active_users:
            active_users[request.sid].pop("room", None)

        emit(
            "status",
            {
                "msg": f"{username} has left the room",
                "type": "leave",
                "timestamp": datetime.now().isoformat(),
            },
            room=room,
        )
        logger.info(f"User {username} has left the room {room}")
    except Exception as e:
        logger.error(str(e))


# Handle messages (public + private)
@socketIO.on("message")
def handle_messages(data: dict):
    """
    data = {
        "room": "General",
        "type": "message" | "private",
        "msg": "hello",
        "target": "GuestXXXX" (for private)
    }
    """
    try:
        username = session["username"]
        room = data.get("room", "General")
        msg_type = data.get("type", "message")
        message = data.get("msg", "").strip()

        if not message:
            return

        timestamp = datetime.now().isoformat()

        # Private message
        if msg_type == "private":
            target_user = data.get("target")
            if not target_user:
                return

            for sid, user_data in active_users.items():
                if user_data["username"] == target_user:
                    emit(
                        "private_message",
                        {
                            "msg": message,
                            "from": username,
                            "to": target_user,
                            "timestamp": timestamp,
                        },
                        room=sid,
                    )
                    logger.info(
                        f"Private message from {username} to {target_user}: {message}"
                    )
                    return
            # If target not found, you could optionally send an error back

        # Public / room message
        else:
            if room not in app.config["CHAT_ROOMS"]:
                return

            emit(
                "message",
                {
                    "msg": message,
                    "username": username,
                    "room": room,
                    "timestamp": timestamp,
                },
                room=room,
            )
            logger.info(f"Message in {room} from {username}: {message}")

    except Exception as e:
        logger.error(str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketIO.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=app.config["DEBUG"],
        use_reloader=app.config["DEBUG"],
    )
