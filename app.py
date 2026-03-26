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

# ---------------- ROUTES ----------------

@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    score = None
    explanation = ""

    if request.method == "POST":
        message = request.form["message"]
        score = detect_scam(message)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO history VALUES (NULL, ?, ?, ?)",
                  (session["user"], message, score))
        conn.commit()
        conn.close()

        explanation = "AI + pattern detection used"

    return render_template_string(HTML, score=score, explanation=explanation)


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


@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT message, score FROM history WHERE username=?", (session["user"],))
    data = c.fetchall()
    conn.close()

    html = "<h2>Your History</h2>"
    for msg, score in data:
        html += f"<p>{msg} → {score}%</p>"

    return html


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ---------------- UI ----------------

HTML = """
<h1>🚨 Scam Detector AI</h1>
<form method="post">
<textarea name="message"></textarea><br>
<button>Check</button>
</form>

{% if score is not none %}
<p>Score: {{score}}%</p>
<p>{{explanation}}</p>
{% endif %}
"""

if __name__ == "__main__":
    app.run(debug=True)
