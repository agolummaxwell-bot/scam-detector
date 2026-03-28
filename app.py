from flask import Flask, request, render_template_string, session, redirect
import sqlite3
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

app = Flask(__name__)
app.secret_key = "secret123"

# 🔐 PAYSTACK SECRET KEY
PAYSTACK_SECRET_KEY = "sk_test_917114ef65bc6471f416567126bac1e625d127df"

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        paid INTEGER DEFAULT 0,
        checks INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        score INTEGER
    )''')

    conn.commit()
    conn.close()

init_db()

import re
import joblib
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler

# ====================== ADVANCED SCAM INDICATORS (2026 Edition) ======================
SCAM_KEYWORDS = [
    # Urgency & Pressure
    "urgent", "immediately", "asap", "right now", "today only", "limited time", "act now", "last chance",
    "before it's too late", "expire", "final notice", "hurry", "don't delay", "24 hours", "48 hours",

    # Prize, Lottery, Winner
    "congratulations", "you have won", "lucky winner", "prize", "jackpot", "selected", "claim now",
    "collect your winnings", "winner alert", "you are the winner",

    # Financial Promises & Greed
    "guaranteed returns", "double your money", "100% guaranteed", "risk free", "no risk", "high yield",
    "passive income", "financial freedom", "earn cash", "make money fast", "investment opportunity",
    "multiply your investment", "crypto investment", "forex", "bitcoin", "usdt", "multiply",

    # Money Transfer & Fees
    "send money", "wire transfer", "western union", "moneygram", "mtcn", "processing fee", "clearance fee",
    "customs duty", "activation fee", "release the funds", "overpayment", "refund", "return the balance",

    # Account & Security
    "account suspended", "account locked", "verify your account", "confirm identity", "security alert",
    "unusual activity", "reset your password", "login now", "update your details", "card blocked",

    # Romance & Emotional
    "my love", "darling", "sweetheart", "honey", "i need your help", "stuck abroad", "hospital bill",
    "my mother is sick", "emergency", "please help me", "god bless you",

    # Impersonation & Official
    "irs", "tax refund", "government grant", "inheritance", "unclaimed funds", "barrister", "lawyer fees",
    "diplomat", "prince", "federal agent",

    # Job & Opportunity
    "work from home", "no experience needed", "earn thousands weekly", "secret shopper", "mystery shopper",

    # Delivery & Package
    "your package", "delivery issue", "undelivered", "pay customs", "shipping fee", "held at customs",

    # Crypto & Modern Scams (2025-2026)
    "pig butchering", "recovery scam", "scam coins", "deepfake", "ai generated", "tap to pay",

    # Nigerian / 419 Specific (highly relevant for Lagos)
    "419", "yahoo boy", "yahoo yahoo", "one chance", "herbalist", "spiritualist", "native doctor",
    "juju", "ritual", "uba", "zenith", "gtbank", "first bank", "customs clearance", "airport release",
    "trapped funds", "confidential transaction", "strictest confidence"
]

# Additional high-signal spam-like phrases from recent trends
EXTRA_PHRASES = [
    "this is not a scam", "100% satisfied", "no catch", "act immediately", "offer expires",
    "free money", "instant cash", "get paid", "life changing", "miracle", "cure", "lose weight",
    "as seen on", "buy direct", "clearance", "order now", "don't delete"
]

ALL_SCAM_INDICATORS = list(set(SCAM_KEYWORDS + EXTRA_PHRASES))

class ScamFeatureExtractor(BaseEstimator, TransformerMixin):
    """Custom transformer for advanced hand-crafted features"""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        features = []
        for text in X:
            text_lower = text.lower()
            length = len(text)
            caps_ratio = sum(1 for c in text if c.isupper()) / (length + 1)
            punct_count = len(re.findall(r'[!?.,;]', text))
            excl_count = text.count('!') + text.count('?')
            keyword_hits = sum(1 for kw in ALL_SCAM_INDICATORS if kw.lower() in text_lower)
            urgency_score = sum(1 for word in ["urgent", "immediately", "now", "asap", "today"] if word in text_lower)

            features.append([
                length,
                caps_ratio,
                punct_count,
                excl_count,
                keyword_hits,
                urgency_score
            ])
        return np.array(features)

# ====================== TRAINING DATA (Expanded & Balanced) ======================
scam_messages = [
    "Congratulations! You have won a $1,000,000 prize. Claim your winnings now by clicking the link.",
    "Urgent! Send $500 via Western Union to release your trapped inheritance funds immediately.",
    "Dear friend, my mother is very sick in hospital. Please help me with $300 for the bill.",
    "Your account has been suspended due to unusual activity. Verify now or lose access.",
    "Investment opportunity! Double your money in 7 days with crypto. 100% guaranteed returns.",
    "Your package is held at Lagos customs. Pay ₦150,000 clearance fee today to release it.",
    "You are the lucky winner of an iPhone 15 Pro. Click here to claim before it expires.",
    "I am a diplomat needing your assistance to transfer $10 million. Strictest confidence required.",
    "Reset your password immediately or your bank account will be permanently locked.",
    "Work from home and earn $5000 weekly. No experience needed. Start today!"
]

legit_messages = [
    "Hello, how are you doing today? Hope everything is fine.",
    "Let's schedule a meeting for tomorrow at 2 PM. Are you available?",
    "Thank you for your help with the project last week.",
    "Good morning sir, please review the attached invoice.",
    "Happy birthday! Wishing you all the best.",
    "Can we reschedule the call to Friday afternoon?",
    "The payment was processed successfully. Receipt attached.",
    "I'll be in Lagos next month for the conference. Let's catch up.",
    "What time works best for you on Wednesday?",
    "Have a great weekend! See you on Monday."
]

# Expand dataset for better training (you can add hundreds more later)
messages = scam_messages * 3 + legit_messages * 3   # simple augmentation for balance
labels = [1] * len(scam_messages * 3) + [0] * len(legit_messages * 3)

# ====================== ADVANCED PIPELINE ======================
preprocessor = ColumnTransformer(
    transformers=[
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.9,
            stop_words='english',
            lowercase=True,
            strip_accents='ascii'
        ), 'text'),
        ('features', ScamFeatureExtractor(), 'text')
    ],
    remainder='drop'
)

model = Pipeline([
    ('preprocessor', preprocessor),
    ('scaler', StandardScaler(with_mean=False)),  # handles sparse data
    ('clf', LogisticRegression(
        class_weight='balanced',
        max_iter=2000,
        C=1.5,
        solver='liblinear',
        random_state=42
    ))
])

# Split and train
X_train, X_test, y_train, y_test = train_test_split(
    [{'text': msg} for msg in messages], labels, test_size=0.2, random_state=42, stratify=labels
)

# Convert back to lists for pipeline
X_train_text = [x['text'] for x in X_train]
X_test_text = [x['text'] for x in X_test]

model.fit(X_train_text, y_train)

# Evaluation
y_pred = model.predict(X_test_text)
print("✅ Model Training Complete!")
print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['Legitimate', 'Scam']))

# Save model
joblib.dump(model, 'advanced_scam_detector_v2.pkl')
print(f"Model saved as 'advanced_scam_detector_v2.pkl' at {datetime.now()}")

# ====================== SMART PREDICTION FUNCTION ======================
def detect_scam_advanced(text: str, threshold: float = 0.60) -> dict:
    """Highly accurate scam detection with explanation"""
    if not text or len(text.strip()) < 5:
        return {"is_scam": False, "scam_probability": 0.0, "reason": "Message too short"}

    prob = model.predict_proba([text])[0][1]
    is_scam = prob >= threshold

    # Keyword analysis for transparency
    text_lower = text.lower()
    matched_keywords = [kw for kw in ALL_SCAM_INDICATORS if kw.lower() in text_lower]

    # Feature insights
    length = len(text)
    caps_ratio = sum(1 for c in text if c.isupper()) / (length + 1)
    excl_count = text.count('!') + text.count('?')

    confidence = "High" if abs(prob - 0.5) > 0.35 else "Medium"

    return {
        "is_scam": bool(is_scam),
        "scam_probability": round(float(prob), 4),
        "confidence": confidence,
        "matched_keywords": matched_keywords[:8],  # top signals
        "message_length": length,
        "caps_ratio": round(caps_ratio, 3),
        "exclamation_count": excl_count,
        "recommendation": "🚨 HIGH RISK - BLOCK & REPORT" if is_scam else "✅ Likely Legitimate",
        "timestamp": datetime.now().isoformat()
    }

# ====================== TEST THE UPGRADED DETECTOR ======================
test_cases = [
    "Congratulations you won ₦50 million lottery. Send your bank details immediately to claim.",
    "Hi team, can we have the meeting at 3pm tomorrow?",
    "Urgent: Your account is under review. Verify now using this link or it will be suspended.",
    "Good afternoon, please find the updated contract attached. Let me know your thoughts.",
    "My love, I am stuck overseas and need $400 for hospital. Please help me quickly."
]

print("\n🚀 Testing Advanced Scam Detector:")
for msg in test_cases:
    result = detect_scam_advanced(msg)
    print(f"\nMessage: {msg[:80]}{'...' if len(msg)>80 else ''}")
    print(f"Result : {result['recommendation']}")
    print(f"Probability: {result['scam_probability']} | Confidence: {result['confidence']}")
    if result['matched_keywords']:
        print(f"Key signals: {', '.join(result['matched_keywords'][:5])}")
# ---------------- HELPERS ----------------
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

# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    score = None
    message = ""

    user = session.get("user")

    if not user:
        return redirect("/login")

    user_data = get_user(user)

    if not user_data:
        return "User not found"

    paid = user_data[0]
    checks = user_data[1]

    if request.method == "POST":

        # 🚫 LIMIT
        if not paid and checks >= 3:
            return render_template_string("""
            <h2>🚫 Free limit reached</h2>
            <p>You have used your 3 free checks.</p>

            <button onclick="payWithPaystack()">💳 Pay ₦2000 to unlock</button>

            <script src="https://js.paystack.co/v1/inline.js"></script>
            <script>
            function payWithPaystack(){
                var handler = PaystackPop.setup({
                    key: 'pk_test_53472e03ba2d63a4a5f9de9c49d88e901a2ab56a',
                    email: 'agolummaxwell@gmail.com',
                    amount: 200000,
                    currency: "NGN",

                    callback: function(response){
                        window.location.href = "/verify?reference=" + response.reference;
                    },

                    onClose: function(){
                        alert("Payment cancelled");
                    }
                });

                handler.openIframe();
            }
            </script>
            """)

        message = request.form["message"]
        score = detect_scam(message)

        if not paid:
            update_checks(user)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO history (username, message, score) VALUES (?, ?, ?)",
                  (user, message, score))
        conn.commit()
        conn.close()

    return render_template_string("""
    <html>
    <head>
        <title>DetectorMax</title>
        <style>
            body { background:#0f172a; color:white; text-align:center; padding:50px; }
            textarea { width:80%; height:120px; border-radius:8px; }
            button { padding:12px 25px; background:#22c55e; border:none; border-radius:8px; color:white; }
        </style>
    </head>
    <body>

        <h1>🛡 DetectorMax</h1>

        {% if not paid %}
            <p>Free checks left: {{3 - checks}}</p>
        {% else %}
            <p>✅ Unlimited access</p>
        {% endif %}

        <form method="post">
            <textarea name="message">{{message}}</textarea><br>
            <button>Check Message</button>
        </form>

        {% if score is not none %}
            <h3>Scam Score: {{score}}%</h3>
        {% endif %}

        <br><br>
        <a href="/history" style="color:#38bdf8;">View History</a>

    </body>
    </html>
    """, score=score, message=message, checks=checks, paid=paid)

# ---------------- VERIFY PAYMENT ----------------
@app.route("/verify")
def verify():
    reference = request.args.get("reference")
    user = session.get("user")

    if not reference or not user:
        return "Invalid request"

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    try:
        response = requests.get(url, headers=headers)
        data = response.json()

        if data["status"] and data["data"]["status"] == "success":
            set_paid(user)
            return redirect("/")

    except:
        return "Verification error"

    return "Payment verification failed"

# ---------------- HISTORY ----------------
@app.route("/history")
def history():
    user = session.get("user")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT message, score FROM history WHERE username=?", (user,))
    data = c.fetchall()
    conn.close()

    html = "<h2>Your History</h2>"
    for msg, score in data:
        html += f"<p><b>{score}%</b> - {msg}</p>"

    html += '<br><a href="/">⬅ Back</a>'
    return html

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()

        if not user:
            c.execute("INSERT INTO users (username) VALUES (?)", (username,))
            conn.commit()

        conn.close()

        session["user"] = username
        return redirect("/")

    return '''
    <h2>Login</h2>
    <form method="post">
        <input name="username" placeholder="Username"><br>
        <button>Login</button>
    </form>
    '''

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
