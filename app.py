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

# ---------------- AI ----------------
messages = [
    "You have won a prize claim now",
    "Send money urgently to receive funds",
    "Click here to win cash prize",
    "Free investment opportunity",
    "Verify your bank account now",
    "Urgent transfer required now",
    "Hello how are you doing today",
    "Let's meet tomorrow",
    "This is a normal message",
    "Are you available for a call"
]

labels = [1,1,1,1,1,1,0,0,0,0]

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(messages)

model = MultinomialNB()
model.fit(X, labels)

def detect_scam(text):
    text = text.lower()
    X_input = vectorizer.transform([text])
    probability = model.predict_proba(X_input)[0][1]

    score = int(probability * 100)

    if "http" in text:
        score += 20
    if any(char.isdigit() for char in text):
        score += 10
    if "urgent" in text:
        score += 15

    return min(score, 100)

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
    paid = user_data[0]
    checks = user_data[1]

    if request.method == "POST":

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
    <!DOCTYPE html>
    <html>
    <head>
        <title>DetectorMax</title>
        <style>
            body {
                background: #0f172a;
                color: white;
                font-family: Arial;
                text-align: center;
                padding: 50px;
            }
            textarea {
                width: 80%;
                height: 120px;
                padding: 10px;
                border-radius: 8px;
                border: none;
            }
            button {
                margin-top: 10px;
                padding: 12px 25px;
                background: #22c55e;
                border: none;
                border-radius: 8px;
                color: white;
                cursor: pointer;
            }
            .result {
                margin-top: 20px;
                font-size: 20px;
            }
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
            <textarea name="message" placeholder="Paste message here...">{{message}}</textarea><br>
            <button>Check Message</button>
        </form>

        {% if score is not none %}
            <div class="result">
                Scam Score: <b>{{score}}%</b>
            </div>
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

    if not reference:
        return "No reference"

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    if data["status"] and data["data"]["status"] == "success":
        set_paid(user)
        return redirect("/")

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
