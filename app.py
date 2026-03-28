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
            return "❌ User already exists"
        finally:
            conn.close()

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Register</title>
        <style>
            body {
                background: #020617;
                color: white;
                font-family: Arial;
                text-align: center;
                padding-top: 100px;
            }

            input {
                padding: 12px;
                margin: 10px;
                border-radius: 8px;
                border: none;
                width: 250px;
            }

            button {
                padding: 12px 30px;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
            }

            a { color: #60a5fa; }
        </style>
    </head>
    <body>

    <h1>📝 Create Account</h1>

    <form method="post">
        <input name="username" placeholder="Username" required><br>
        <input name="password" type="password" placeholder="Password" required><br><br>
        <button type="submit">Register</button>
    </form>

    <p>Already have account? <a href="/login">Login</a></p>

    </body>
    </html>
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

   return """
<!DOCTYPE html>
<html>
<head>
    <title>Login - DetectorMax</title>
    <style>
        body {
            background: #020617;
            color: white;
            font-family: Arial;
            text-align: center;
            padding-top: 100px;
        }

        input {
            padding: 12px;
            margin: 10px;
            border-radius: 8px;
            border: none;
            width: 250px;
        }

        button {
            padding: 12px 30px;
            background: #22c55e;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }

        a {
            color: #60a5fa;
        }
    </style>
</head>
<body>

<h1>🔐 Login to DetectorMax</h1>

<form method="post">
    <input name="username" placeholder="Username" required><br>
    <input name="password" type="password" placeholder="Password" required><br><br>
    <button type="submit">Login</button>
</form>

<p>New user? <a href="/register">Create account</a></p>

</body>
</html>
"""

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
