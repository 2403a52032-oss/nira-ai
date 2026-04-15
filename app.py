import streamlit as st
import sqlite3
import uuid
import pandas as pd
import re
import hashlib
from groq import Groq

# ================= EXTRA IMPORTS (ADDED) =================
from cryptography.fernet import Fernet
import base64
import datetime
import plotly.express as px


# ================= 1. AI CONFIG =================
API_KEY = "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"
client = Groq(api_key=API_KEY)

def get_nira_response(user_input, context):
    try:
        prompt = f"""
You are Nira 🌿, a warm emotional AI friend.

Be natural, human-like, empathetic, short.

Context:
{context}

User:
{user_input}
"""
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    except Exception as e:
        return "I'm having trouble responding right now 🌿 Please try again."


# ================= 2. MOOD =================
def extract_mood(text):
    text = text.lower()
    if re.search(r"sad|cry|depressed|lonely", text):
        return 2
    elif re.search(r"angry|mad|frustrated", text):
        return 3
    elif re.search(r"happy|good|love|nice", text):
        return 8
    elif re.search(r"awesome|best|amazing|excited", text):
        return 10
    return 6


# ================= 3. SECURITY =================
def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


# ================= PIN ENCRYPTION (ADDED) =================
SECRET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"nira_secret_key").digest())
cipher = Fernet(SECRET_KEY)

def encrypt_pin(pin):
    return cipher.encrypt(pin.encode()).decode()

def decrypt_pin(encrypted_pin):
    return cipher.decrypt(encrypted_pin.encode()).decode()


# ================= 4. DATABASE =================
def get_db():
    conn = sqlite3.connect("nira_v3.db", check_same_thread=False)
    return conn


conn = get_db()
conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    email TEXT,
    pin TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    username TEXT,
    role TEXT,
    message TEXT,
    mood_score INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()


# ================= 5. SESSION =================
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if "pin_ok" not in st.session_state:
    st.session_state.pin_ok = False


# ================= 6. UI =================
def ui():
    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)),
        url("https://i.pinimg.com/736x/d9/3f/7c/d93f7cc2226c4bdf8b0dd4a039719966.jpg");
        background-size: cover;
    }
    h1,h2,h3,p,label,span {color:black!important;}

    div.stButton > button {
        background:#00b894!important;
        color:black!important;
        border-radius:10px;
    }

    input {
        background:white!important;
        color:blue!important;
    }
    </style>
    """, unsafe_allow_html=True)


# ================= 7. AUTH =================
def auth():
    ui()
    st.title("🌿 Nira AI")

    mode = st.radio("Choose", ["Login", "Register"])

    conn = get_db()

    if mode == "Register":
        u = st.text_input("Username")
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        pin = st.text_input("PIN", type="password")

        if st.button("Register"):
            if u and p and pin:
                conn.execute(
                    "INSERT OR REPLACE INTO users VALUES (?,?,?,?)",
                    (u, hash_text(p), e, encrypt_pin(pin))   # ✅ CHANGED
                )
                conn.commit()
                st.success("Registered!")
            else:
                st.error("Fill all fields")

    else:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            res = conn.execute(
                "SELECT password FROM users WHERE username=?",
                (u,)
            ).fetchone()

            if res and res[0] == hash_text(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Invalid login")

    conn.close()


# ================= 8. CHAT =================
def show_weekly_mood():
    conn = get_db()

    data = conn.execute("""
        SELECT timestamp, mood_score
        FROM chats
        WHERE mood_score IS NOT NULL
        AND timestamp >= datetime('now', '-7 days')
    """).fetchall()

    conn.close()

    if not data:
        st.info("No mood data for last 7 days 🌿")
        return

    df = pd.DataFrame(data, columns=["time", "mood"])
    df["time"] = pd.to_datetime(df["time"])

    fig = px.line(df, x="time", y="mood", title="🌿 Weekly Mood Graph")
    st.plotly_chart(fig)


def update_message(msg, new_text):
    conn = get_db()
    conn.execute("""
        UPDATE chats
        SET message = ?
        WHERE message = ?
        AND role = 'user'
    """, (new_text, msg))
    conn.commit()
    conn.close()


def chat():
    ui()
    st.sidebar.title(st.session_state.user)

    # ================= LOGOUT =================
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.chat_id = str(uuid.uuid4())
        st.session_state.pin_ok = False
        st.rerun()

    # ================= NEW CHAT (ADDED) =================
    if st.sidebar.button("➕ New Chat"):
        st.session_state.chat_id = str(uuid.uuid4())
        st.session_state.pin_ok = False
        st.rerun()

    # ================= MOOD GRAPH (ADDED) =================
    if st.sidebar.button("📊 Weekly Mood Graph"):
        show_weekly_mood()

    # ================= HISTORY =================
    st.sidebar.subheader("Chats")

    conn = get_db()
    history = conn.execute("""
        SELECT chat_id, MAX(message)
        FROM chats
        WHERE username=?
        GROUP BY chat_id
        ORDER BY MAX(id) DESC
    """, (st.session_state.user,)).fetchall()

    for cid, msg in history:
        col1, col2 = st.sidebar.columns([4,1])

        if col1.button(msg[:20], key=cid):
            st.session_state.chat_id = cid
            st.rerun()

        if col2.button("🗑️", key=f"del_{cid}"):
            conn.execute("DELETE FROM chats WHERE chat_id=?", (cid,))
            conn.commit()
            st.rerun()

    # ================= PIN LOCK =================
    pin = conn.execute(
        "SELECT pin FROM users WHERE username=?",
        (st.session_state.user,)
    ).fetchone()

    if pin and not st.session_state.pin_ok:
        lock = st.sidebar.checkbox("🔒 Lock Chat")

        if lock:
            p = st.text_input("Enter PIN", type="password")

            if st.button("Unlock"):
                if p == decrypt_pin(pin[0]):   # ✅ CHANGED
                    st.session_state.pin_ok = True
                    st.rerun()
                else:
                    st.error("Wrong PIN")
            st.stop()

    st.title("Peaceful Space 🌿")

    messages = conn.execute("""
        SELECT role, message FROM chats
        WHERE chat_id=?
        ORDER BY id ASC
    """, (st.session_state.chat_id,)).fetchall()

    # ================= EDIT FEATURE (ADDED) =================
    for role, msg in messages:
        col1, col2 = st.columns([6,1])

        with col1:
            with st.chat_message(role):
                st.write(msg)

        if role == "user":
            if col2.button("✏️", key=f"edit_{msg}"):
                st.session_state.edit_msg = msg

    if "edit_msg" in st.session_state:
        st.warning("Edit your message")
        new_text = st.text_area("Edit:", st.session_state.edit_msg)

        col1, col2 = st.columns(2)

        if col1.button("Save Edit"):
            update_message(st.session_state.edit_msg, new_text)
            del st.session_state.edit_msg
            st.rerun()

        if col2.button("Cancel"):
            del st.session_state.edit_msg
            st.rerun()

    prompt = st.chat_input("Talk to Nira...")

    if prompt:
        conn.execute("""
            INSERT INTO chats (chat_id, username, role, message)
            VALUES (?,?,?,?)
        """, (st.session_state.chat_id, st.session_state.user, "user", prompt))
        conn.commit()

        context = "\n".join([f"{r}:{m}" for r,m in messages[-5:]])
        reply = get_nira_response(prompt, context)
        mood = extract_mood(prompt)

        conn.execute("""
            INSERT INTO chats (chat_id, username, role, message, mood_score)
            VALUES (?,?,?,?,?)
        """, (st.session_state.chat_id, st.session_state.user, "assistant", reply, mood))
        conn.commit()

        st.rerun()


# ================= 9. RUN =================
st.set_page_config(page_title="Nira AI", layout="wide")

if st.session_state.user is None:
    auth()
else:
    chat()