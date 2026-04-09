import smtplib
from email.mime.text import MIMEText
import re
import os
import joblib
import sqlite3
import random
from datetime import datetime

from flask import Flask, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

# ================= GOOGLE LOGIN =================
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    client_kwargs={'scope': 'openid email profile'},
)

# ================= EMAIL OTP =================
OTP_STORE = {}

def send_otp_email(to_email, otp):
    sender = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")

    msg = MIMEText(f"Your verification code is: {otp}")
    msg["Subject"] = "DetectorMax Login Code"
    msg["From"] = sender
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        name TEXT,
        password TEXT,
        paid INTEGER DEFAULT 0,
        checks INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        scam_probability REAL,
        is_scam INTEGER,
        timestamp TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        amount TEXT,
        status TEXT,
        date TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= MODEL =================
MODEL_PATH = "model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except:
    scam = ["you have won money", "urgent send money now", "verify your account now", "click here to claim prize"]
    legit = ["hello how are you", "see you tomorrow", "thank you", "let's meet later"]

    texts = scam * 30 + legit * 30
    labels = [1]*len(scam*30) + [0]*len(legit*30)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2))),
        ("clf", LogisticRegression(max_iter=2000))
    ])

    model = CalibratedClassifierCV(pipeline)
    model.fit(texts, labels)
    joblib.dump(model, MODEL_PATH)

# ================= DETECTION =================
KEYWORDS = ["urgent","money","prize","click","verify","bank"]

def extra_checks(text):
    score = 0
    if re.search(r"\$\d+", text):
        score += 0.1
    if text.isupper():
        score += 0.1
    if "!!!" in text:
        score += 0.05
    return score

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

    final = min(prob + boost + extra_checks(text), 1)

    return {
        "is_scam": final > 0.6,
        "scam_probability": round(final*100,1),
        "confidence": "High" if final>0.8 else "Medium",
        "matched_keywords": matched,
        "recommendation": "🚨 Scam" if final>0.6 else "✅ Safe"
    }

# ================= HELPERS =================
def get_user(u):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT paid, checks FROM users WHERE email=?", (u,))
    data = c.fetchone()
    conn.close()
    return data

def update_checks(u):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET checks=checks+1 WHERE email=?", (u,))
    conn.commit()
    conn.close()

def save(u, msg, r):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES(NULL,?,?,?,?,?)",
              (u, msg, r["scam_probability"], int(r["is_scam"]), datetime.now()))
    conn.commit()
    conn.close()

def is_premium(email):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT paid FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
    return user and user[0] == 1

# ================= EMAIL LOGIN =================
@app.route("/email-login", methods=["GET","POST"])
def email_login():
    if request.method == "POST":
        email = request.form["email"]

        otp = str(random.randint(100000, 999999))
        OTP_STORE[email] = otp

        send_otp_email(email, otp)

        return render_template("verify.html", email=email)

    return render_template("email_login.html")

@app.route("/verify", methods=["POST"])
def verify():
    email = request.form["email"]
    user_otp = request.form["otp"]

    if OTP_STORE.get(email) == user_otp:

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()

        if not user:
            c.execute(
                "INSERT INTO users (email, name, paid, checks, created_at) VALUES (?, ?, 0, 0, ?)",
                (email, email, datetime.now())
            )
            conn.commit()

        conn.close()

        session["user"] = email
        return redirect("/")

    return "❌ Invalid code"

# ================= GOOGLE LOGIN =================
@app.route("/google-login")
def google_login():
    return google.authorize_redirect("https://detectormax.com/authorize")

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token)

    email = user_info["email"]
    name = user_info["name"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()

    if not user:
        c.execute(
            "INSERT INTO users (email, name, paid, checks, created_at) VALUES (?, ?, 0, 0, ?)",
            (email, name, datetime.now())
        )
        conn.commit()

    conn.close()

    session["user"] = email
    return redirect("/")

# ================= HOME =================
@app.route("/", methods=["GET","POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    paid, checks = get_user(user)

    result = None
    message = ""

    if request.method == "POST":

        if not is_premium(user) and checks >= 5:
            return "🚫 Upgrade to premium to continue"

        message = request.form.get("message","")

        if message:
            result = detect(message)
            update_checks(user)
            save(user, message, result)

    return render_template("home.html", result=result, message=message, user=user)

# ================= PAYMENT =================
@app.route("/pay")
def pay():
    user = session.get("user")

    if not user:
        return redirect("/login")

    return redirect(
        f"https://flutterwave.com/pay/nipvbc62jp3x"
        f"?email={user}"
        f"&redirect_url=https://detectormax.com/payment-success"
    )

@app.route("/payment-success")
def payment_success():
    email = session.get("user")

    if not email:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("UPDATE users SET paid=1 WHERE email=?", (email,))
    c.execute("INSERT INTO payments VALUES(NULL,?,?,?,?)",
              (email, "Premium Plan", "success", datetime.now()))

    conn.commit()
    conn.close()

    return redirect("/")

# ================= AUTH =================
@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
