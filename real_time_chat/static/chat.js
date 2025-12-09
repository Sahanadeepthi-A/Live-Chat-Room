// connect to Socket.IO
const socket = io();
let currentRoom = "General";
const username = document.getElementById("username").textContent.trim();
let roomMessages = {};

// SOCKET EVENT LISTENERS
socket.on("connect", () => {
    joinRoom(currentRoom);
});

socket.on("message", (data) => {
    addMessage(
        data.username,
        data.msg,
        data.username === username ? "own" : "other"
    );
});

socket.on("private_message", (data) => {
    addMessage(
        data.from,
        `[Private] ${data.msg}`,
        "private"
    );
});

socket.on("status", (data) => {
    addMessage("System", data.msg, "system");
});

socket.on("active_users", (data) => {
    const userList = document.getElementById("active-users");
    userList.innerHTML = data.users
        .map((user) => `
            <div class="user-item" onclick="insertPrivateMessage('${user}')">
                ${user} ${user === username ? "(you)" : ""}
            </div>
        `)
        .join("");
});

// ADD MESSAGE TO CHAT
function addMessage(sender, message, type) {
    if (!roomMessages[currentRoom]) {
        roomMessages[currentRoom] = [];
    }

    roomMessages[currentRoom].push({ sender, message, type });

    const chat = document.getElementById("chat");
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = `${sender}: ${message}`;
    chat.appendChild(messageDiv);
    chat.scrollTop = chat.scrollHeight;
}

// SEND MESSAGE
function sendMessage() {
    const input = document.getElementById("message");
    const message = input.value.trim();
    if (!message) return;

    // Private message: starts with @username
    if (message.startsWith("@")) {
        const [target, ...msgParts] = message.substring(1).split(" ");
        const privateMsg = msgParts.join(" ").trim();

        if (target && privateMsg) {
            socket.emit("message", {
                msg: privateMsg,
                type: "private",
                target: target,
            });
            addMessage(`To ${target}`, privateMsg, "private");
        }
    } else {
        // Public room message
        socket.emit("message", {
            msg: message,
            room: currentRoom,
            type: "message",
        });
    }

    input.value = "";
    input.focus();
}

// JOIN ROOM
function joinRoom(room) {
    // leave previous room if any
    if (currentRoom) {
        socket.emit("leave", { room: currentRoom });
    }

    currentRoom = room;
    socket.emit("join", { room });

    // clear chat window
    const chat = document.getElementById("chat");
    chat.innerHTML = "";

    // restore saved messages for this room
    if (roomMessages[room]) {
        roomMessages[room].forEach((msg) => {
            addMessage(msg.sender, msg.message, msg.type);
        });
    }

    // update active room highlight
    document.querySelectorAll(".room-item").forEach((item) => {
        item.classList.toggle(
            "active-room",
            item.textContent.trim() === room
        );
    });
}

// INSERT PRIVATE MESSAGE PREFIX
function insertPrivateMessage(user) {
    // don't DM yourself
    if (user === username) return;

    const input = document.getElementById("message");
    input.value = `@${user} `;
    input.focus();
}

// HANDLE ENTER KEY
function handleKeyPress(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// INITIALIZE CHAT UI
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".room-item").forEach((item) => {
        if (item.textContent.trim() === currentRoom) {
            item.classList.add("active-room");
        }
    });
});
