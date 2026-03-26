from flask import Flask, request, render_template_string, session, redirect
import sqlite3

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
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

# ---------------- HOME (NEW UI) ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    score = None
    message = ""

    if request.method == "POST":
        message = request.form["message"]
        score = detect_scam(message)

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
            h1 { font-size: 40px; }

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
                font-size: 16px;
                cursor: pointer;
            }

            .result {
                margin-top: 20px;
                font-size: 20px;
            }

            .login {
                margin-top: 20px;
                display: block;
                color: #38bdf8;
            }
        </style>
    </head>
    <body>

        <h1>🛡 DetectorMax</h1>
        <p>AI-powered scam detector</p>

        <form method="post">
            <textarea name="message" placeholder="Paste message here...">{{message}}</textarea><br>
            <button>Check Message</button>
        </form>

        {% if score is not none %}
            <div class="result">
                Scam Score: <b>{{score}}%</b>
            </div>
        {% endif %}

        <a class="login" href="/login">Login</a>

    </body>
    </html>
    """, score=score, message=message)


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
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
    app.run()
