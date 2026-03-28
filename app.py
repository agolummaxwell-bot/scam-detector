import re
import os
import joblib
import sqlite3
import requests
import numpy as np
import pandas as pd
from datetime import datetime

from flask import Flask, request, render_template_string, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this")

# ====================== PAYSTACK ======================
PAYSTACK_SECRET_KEY = "sk_test_..."
PAYSTACK_PUBLIC_KEY = "pk_test_..."

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        paid INTEGER DEFAULT 0,
        checks INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        scam_probability REAL,
        is_scam INTEGER,
        timestamp TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# ====================== MODEL ======================
MODEL_PATH = "model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except:
    scam = [
        "you have won money", "urgent send money now",
        "verify your account now", "click here to claim prize"
    ]

    legit = [
        "hello how are you", "see you tomorrow",
        "thank you", "let's meet later"
    ]

    texts = scam * 30 + legit * 30
    labels = [1]*len(scam*30) + [0]*len(legit*30)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2))),
        ("clf", LogisticRegression(max_iter=2000))
    ])

    model = CalibratedClassifierCV(pipeline)
    model.fit(texts, labels)

    joblib.dump(model, MODEL_PATH)

# ====================== DETECTION ======================
KEYWORDS = ["urgent","money","prize","click","verify","bank"]

def detect(text):
    prob = model.predict_proba([text])[0][1]
    text_lower = text.lower()

    boost = 0
    matched = []

    for k in KEYWORDS:
        if k in text_lower:
            boost += 0.05
            matched.append(k)

    if "http" in text_lower:
        boost += 0.1

    final = min(prob + boost, 1)

    explanation = []
    if matched:
        explanation.append("Contains suspicious keywords")
    if "http" in text_lower:
        explanation.append("Contains link")

    return {
        "is_scam": final > 0.6,
        "scam_probability": round(final*100,1),
        "confidence": "High" if final>0.8 else "Medium",
        "matched_keywords": matched,
        "explanation": explanation,
        "recommendation": "🚨 Scam" if final>0.6 else "✅ Safe"
    }

# ====================== DB HELPERS ======================
def get_user(u):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT paid, checks FROM users WHERE username=?", (u,))
    data = c.fetchone()
    conn.close()
    return data

def update_checks(u):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET checks=checks+1 WHERE username=?", (u,))
    conn.commit()
    conn.close()

def set_paid(u):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET paid=1 WHERE username=?", (u,))
    conn.commit()
    conn.close()

def save(u, msg, r):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES(NULL,?,?,?,?,?)",
              (u, msg, r["scam_probability"], int(r["is_scam"]), datetime.now()))
    conn.commit()
    conn.close()

# ====================== HOME ======================
@app.route("/", methods=["GET","POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    paid, checks = get_user(user)

    result = None
    message = ""

    if request.method == "POST":

        if not paid and checks >= 5:
            return "Pay to continue"

        message = request.form.get("message","")

        if len(message) > 1000:
            return "Message too long"

        if message:
            result = detect(message)
            if not paid:
                update_checks(user)
            save(user, message, result)

    return render_template_string("""
    <h1>DetectorMax</h1>

    <form method="post">
        <textarea name="message">{{message}}</textarea><br>
        <button>Check</button>
    </form>

    {% if result %}
        <h2>{{result.recommendation}}</h2>
        <p>{{result.scam_probability}}%</p>
        <p>{{result.confidence}}</p>

        {% for e in result.explanation %}
            <p>• {{e}}</p>
        {% endfor %}
    {% endif %}

    """, result=result, message=message)

# ====================== AUTH ======================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u = request.form["username"]
        p = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
            conn.commit()
            return redirect("/login")
        except:
            return "User exists"

    return '''
    <form method="post">
    <input name="username">
    <input name="password" type="password">
    <button>Register</button>
    </form>
    '''

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (u,))
        user = c.fetchone()

        if user and check_password_hash(user[0], p):
            session["user"] = u
            return redirect("/")
        return "Invalid"

    return '''
    <form method="post">
    <input name="username">
    <input name="password" type="password">
    <button>Login</button>
    </form>
    '''

# ====================== RUN ======================
if __name__ == "__main__":
    app.run(debug=True)
