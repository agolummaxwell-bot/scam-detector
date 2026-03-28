import re
import joblib
import sqlite3
import requests
import numpy as np
from datetime import datetime

from flask import Flask, request, render_template_string, session, redirect, url_for

# Password Hashing
from werkzeug.security import generate_password_hash, check_password_hash

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler

app = Flask(__name__)
import os
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this")

# ====================== PAYSTACK CONFIG ======================
PAYSTACK_SECRET_KEY = "sk_test_917114ef65bc6471f416567126bac1e625d127df"
PAYSTACK_PUBLIC_KEY = "pk_test_53472e03ba2d63a4a5f9de9c49d88e901a2ab56a"

# ====================== DATABASE SETUP ======================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
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

# ====================== ADVANCED SCAM INDICATORS ======================
SCAM_KEYWORDS = [
    "urgent", "immediately", "asap", "right now", "today only", "limited time", "act now", "last chance",
    "before it's too late", "expire", "final notice", "hurry", "don't delay", "24 hours", "48 hours",
    "congratulations", "you have won", "lucky winner", "prize", "jackpot", "claim now",
    "guaranteed returns", "double your money", "100% guaranteed", "high yield", "investment opportunity",
    "send money", "wire transfer", "western union", "moneygram", "mtcn", "processing fee", "clearance fee",
    "account suspended", "account locked", "verify your account", "reset your password", "login now",
    "my love", "darling", "sweetheart", "i need your help", "stuck abroad", "hospital bill",
    "419", "yahoo boy", "yahoo yahoo", "one chance", "herbalist", "spiritualist", "native doctor",
    "juju", "ritual", "uba", "zenith", "gtbank", "first bank", "customs clearance", "airport release"
]

EXTRA_PHRASES = ["this is not a scam", "free money", "instant cash", "life changing", "act immediately"]
ALL_SCAM_INDICATORS = list(set(SCAM_KEYWORDS + EXTRA_PHRASES))

class ScamFeatureExtractor(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        features = []
        for text in X:
            text_lower = text.lower()
            length = len(text)
            caps_ratio = sum(1 for c in text if c.isupper()) / (length + 1)
            excl_count = text.count('!') + text.count('?')
            keyword_hits = sum(1 for kw in ALL_SCAM_INDICATORS if kw.lower() in text_lower)
            urgency_score = sum(1 for w in ["urgent", "immediately", "now", "asap", "today"] if w in text_lower)
            features.append([length, caps_ratio, excl_count, keyword_hits, urgency_score])
        return np.array(features)

# ====================== LOAD OR TRAIN MODEL ======================
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

MODEL_PATH = 'advanced_scam_detector_v3.pkl'

try:
    model = joblib.load(MODEL_PATH)
    print("✅ Loaded improved model")
except:
    print("🔄 Training improved model...")

    scam_messages = [
        "Congratulations! You have won $1,000,000. Claim now!",
        "Urgent! Send money immediately to receive funds.",
        "Your bank account is locked. Verify now.",
        "Investment opportunity with guaranteed returns",
        "Click this link to claim your reward now",
        "Send your OTP now",
        "Act fast before it expires",
        "You are selected for a grant",
        "Pay clearance fee to receive package",
        "We need your bank details urgently"
    ]

    legit_messages = [
        "Hello how are you?",
        "Let's meet tomorrow",
        "Please review this document",
        "Happy birthday bro",
        "Lunch at 2pm?",
        "Call me when you’re free",
        "Thanks for your help",
        "See you later",
        "Good morning",
        "Let’s schedule a meeting"
    ]

    texts = scam_messages * 20 + legit_messages * 20
    labels = [1]*len(scam_messages*20) + [0]*len(legit_messages*20)

    df = pd.DataFrame({"text": texts})

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1,2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True
        )),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced"))
    ])

    calibrated_model = CalibratedClassifierCV(pipeline, method='sigmoid')

    calibrated_model.fit(df["text"], labels)

    model = calibrated_model
    joblib.dump(model, MODEL_PATH)

    print("✅ Improved model trained")

# ====================== DETECTION FUNCTION ======================
def detect_scam_advanced(text: str, threshold: float = 0.60):
    if not text or len(text.strip()) < 5:
        return {
            "is_scam": False,
            "scam_probability": 0.0,
            "confidence": "Low",
            "recommendation": "Message too short",
            "matched_keywords": []
        }

    text_lower = text.lower()

    # ML probability
    prob = model.predict_proba([text])[0][1]

    # RULE BOOSTING (VERY IMPORTANT)
    score_boost = 0

    # Keywords
    matched_keywords = []
    for kw in ALL_SCAM_INDICATORS:
        if kw in text_lower:
            score_boost += 0.03
            matched_keywords.append(kw)

    # Links
    if re.search(r"http[s]?://", text_lower):
        score_boost += 0.10

    # Money patterns
    if re.search(r"\$\d+|\d+naira|\d{5,}", text_lower):
        score_boost += 0.08

    # Urgency
    if any(w in text_lower for w in ["urgent", "now", "asap", "immediately"]):
        score_boost += 0.05

    # ALL CAPS
    if text.isupper():
        score_boost += 0.05

    # Final probability
    final_prob = min(prob + score_boost, 1.0)

    is_scam = final_prob >= threshold

    return {
        "is_scam": bool(is_scam),
        "scam_probability": round(final_prob * 100, 1),
        "confidence": (
            "High" if final_prob > 0.8 or final_prob < 0.2
            else "Medium" if abs(final_prob - 0.5) > 0.15
            else "Low"
        ),
        "matched_keywords": matched_keywords[:6],
        "recommendation": (
            "🚨 HIGH RISK - BLOCK & REPORT"
            if is_scam else
            "⚠️ Be cautious" if final_prob > 0.4 else
            "✅ Likely Legitimate"
        )
    }
# ====================== DATABASE HELPERS ======================
def get_user(username):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT paid, checks FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def update_checks(username):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET checks = checks + 1 WHERE username=?", (username,))
    conn.commit()
    conn.close()

def set_paid(username):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET paid = 1 WHERE username=?", (username,))
    conn.commit()
    conn.close()

def save_history(username, message, result):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""INSERT INTO history 
                 (username, message, scam_probability, is_scam, timestamp) 
                 VALUES (?, ?, ?, ?, ?)""",
              (username, message, result["scam_probability"], int(result["is_scam"]), datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ====================== ROUTES ======================
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    user_data = get_user(username)

    if not user_data:
        return "User not found", 404

    paid, checks = user_data
    result = None
    message_text = ""

    if request.method == "POST":

        # 🚫 Free limit check
        if not paid and checks >= 5:
            return render_template_string("""
            <h2>🚫 Free Limit Reached (5 checks)</h2>
            <p>Unlock unlimited checks for ₦2,000</p>
            <button onclick="payWithPaystack()">💳 Pay with Paystack</button>

            <script src="https://js.paystack.co/v1/inline.js"></script>
            <script>
            function payWithPaystack(){
                var handler = PaystackPop.setup({
                    key: '{{ public_key }}',
                    email: '{{ session["user"] }}@detectormax.com',
                    amount: 200000,
                    currency: "NGN",
                    callback: function(response){
                        window.location.href = "/verify?reference=" + response.reference;
                    }
                });
                handler.openIframe();
            }
            </script>
            """, public_key=PAYSTACK_PUBLIC_KEY)

        message_text = request.form.get("message", "").strip()

        if message_text:

            # 🚫 Anti-spam protection
            if len(message_text) > 1000:
                return render_template_string("""
                    <h2>🚫 Message too long</h2>
                    <p>Please keep your message under 1000 characters.</p>
                    <a href="/">⬅ Go Back</a>
                """)

            # ✅ AI detection
            result = detect_scam_advanced(message_text)

            if not paid:
                update_checks(username)

            save_history(username, message_text, result)

    # ✅ ALWAYS render UI (GET + POST)
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DetectorMax AI</title>
        <style>
            body {
                font-family: Arial;
                background: linear-gradient(135deg, #0f172a, #020617);
                color: white;
                text-align: center;
                padding: 30px;
            }

            .container {
                max-width: 800px;
                margin: auto;
            }

            textarea {
                width: 100%;
                height: 140px;
                border-radius: 12px;
                padding: 15px;
                font-size: 16px;
            }

            button {
                padding: 14px 30px;
                font-size: 18px;
                background: #22c55e;
                border: none;
                border-radius: 10px;
                color: white;
                cursor: pointer;
            }

            .meter {
                height: 20px;
                width: 100%;
                background: #1e293b;
                border-radius: 10px;
                margin-top: 15px;
                overflow: hidden;
            }

            .meter-fill {
                height: 100%;
                width: 0%;
                transition: 0.5s;
            }

            .result-box {
                margin-top: 25px;
                padding: 20px;
                border-radius: 12px;
            }

            .safe { background: #166534; }
            .warn { background: #92400e; }
            .danger { background: #991b1b; }

            .explain {
                margin-top: 10px;
                font-size: 14px;
                color: #cbd5f5;
            }
        </style>
    </head>

    <body>
    <div class="container">

        <h1>🛡️ DetectorMax AI</h1>

        {% if not paid %}
            <p>Free checks left: {{ 5 - checks }}</p>
        {% else %}
            <p>✅ Unlimited Access</p>
        {% endif %}

        <form method="post">
            <textarea name="message" placeholder="Paste suspicious message...">{{message_text}}</textarea><br><br>
            <button>🔍 Analyze</button>
        </form>

        {% if result %}
        <div class="result-box 
            {% if result.scam_probability > 70 %}danger
            {% elif result.scam_probability > 40 %}warn
            {% else %}safe{% endif %}">

            <h2>{{ result.recommendation }}</h2>

            <h3>{{ result.scam_probability }}% Risk</h3>

            <!-- 🔥 Risk Meter -->
            <div class="meter">
                <div class="meter-fill" id="meter"></div>
            </div>

            <p>Confidence: {{ result.confidence }}</p>

            {% if result.matched_keywords %}
                <p>⚠️ Signals: {{ result.matched_keywords | join(', ') }}</p>
            {% endif %}

            {% if result.explanation %}
                <div class="explain">
                    <b>Why this was flagged:</b><br>
                    {% for e in result.explanation %}
                        • {{ e }}<br>
                    {% endfor %}
                </div>
            {% endif %}
        </div>

        <script>
        let score = {{ result.scam_probability }};
        let meter = document.getElementById("meter");

        meter.style.width = score + "%";

        if(score < 40){
            meter.style.background = "#22c55e";
        }else if(score < 70){
            meter.style.background = "#f59e0b";
        }else{
            meter.style.background = "#ef4444";
        }
        </script>
        {% endif %}

        <br><br>
        <a href="/history" style="color:#60a5fa;">📜 History</a> |
        <a href="/logout" style="color:#f87171;">Logout</a>

    </div>
    </body>
    </html>
    """, result=result, checks=checks, paid=paid, message_text=message_text)

    # 🚫 Anti-spam / length protection
    if len(message_text) > 1000:
        return render_template_string("""
            <h2>🚫 Message too long</h2>
            <p>Please keep your message under 1000 characters.</p>
            <a href="/">⬅ Go Back</a>
        """)

    # ✅ Run AI detection
    result = detect_scam_advanced(message_text)

    if not paid:
        update_checks(username)

    save_history(username, message_text, result)
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DetectorMax - Advanced Scam Detector</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; text-align: center; padding: 40px; }
            textarea { width: 85%; height: 140px; padding: 15px; border-radius: 10px; font-size: 16px; }
            button { padding: 14px 30px; font-size: 18px; background: #22c55e; color: white; border: none; border-radius: 8px; cursor: pointer; }
            .result { margin: 30px auto; padding: 20px; border-radius: 12px; max-width: 700px; }
            .high-risk { background: #991b1b; }
            .safe { background: #166534; }
        </style>
    </head>
    <body>
        <h1>🛡️ DetectorMax</h1>
        {% if not paid %}
            <p><strong>Free checks left:</strong> {{ 5 - checks }}</p>
        {% else %}
            <p>✅ Unlimited Access</p>
        {% endif %}

        <form method="post">
            <textarea name="message" placeholder="Paste suspicious message here...">{{ message_text }}</textarea><br><br>
            <button type="submit">🔍 Analyze Message</button>
        </form>

        {% if result %}
        <div class="result {{ 'high-risk' if result.is_scam else 'safe' }}">
            <h2>{{ result.recommendation }}</h2>
            <h3>Scam Probability: {{ result.scam_probability }}%</h3>
            <p>Confidence: {{ result.confidence }}</p>
            {% if result.matched_keywords %}
                <p>Key Signals: {{ result.matched_keywords | join(', ') }}</p>
            {% endif %}
        </div>
        {% endif %}

        <br>
        <a href="/history" style="color:#60a5fa;">📜 View History</a> | 
        <a href="/logout" style="color:#f87171;">Logout</a>
    </body>
    </html>
    """, result=result, checks=checks, paid=paid, message_text=message_text)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return "Username and password are required"

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "❌ Username already exists. Please choose another."
        finally:
            conn.close()

    return '''
    <h2>Register New Account</h2>
    <form method="post">
        <input name="username" placeholder="Username" required><br><br>
        <input name="password" type="password" placeholder="Password" required><br><br>
        <button type="submit">Register</button>
    </form>
    <p>Already have an account? <a href="/login">Login here</a></p>
    '''

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session["user"] = username
            return redirect(url_for("home"))
        else:
            return "❌ Invalid username or password"

    return '''
    <h2>Login to DetectorMax</h2>
    <form method="post">
        <input name="username" placeholder="Username" required><br><br>
        <input name="password" type="password" placeholder="Password" required><br><br>
        <button type="submit">Login</button>
    </form>
    <p>New user? <a href="/register">Create an account</a></p>
    '''

@app.route("/verify")
def verify_payment():
    reference = request.args.get("reference")
    username = session.get("user")

    if not reference or not username:
        return "Invalid request", 400

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("status") and data["data"].get("status") == "success":
            set_paid(username)
            return redirect(url_for("home"))
    except Exception as e:
        print("Payment verification error:", e)

    return "Payment verification failed. Please contact support."

@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""SELECT message, scam_probability, is_scam, timestamp 
                 FROM history WHERE username=? ORDER BY id DESC LIMIT 30""", (username,))
    records = c.fetchall()
    conn.close()

    html = "<h2>Your Detection History</h2><hr>"
    for msg, prob, is_scam, ts in records:
        status = "🚨 SCAM" if is_scam else "✅ Safe"
        html += f"<p><strong>{status}</strong> — {prob}% — {msg[:100]}{'...' if len(msg) > 100 else ''} <small>({ts[:10]})</small></p>"

    html += '<br><a href="/">← Back to Home</a>'
    return html

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ====================== RUN APP ======================
if __name__ == "__main__":
    print("🚀 DetectorMax Scam Detector is running...")
    app.run(debug=True)
