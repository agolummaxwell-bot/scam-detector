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
<!DOCTYPE html>
<html>
<head>
<title>Scam Detector AI</title>

<style>
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: white;
}

/* Navbar */
.navbar {
    background: #020617;
    padding: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.navbar a {
    color: #22c55e;
    text-decoration: none;
    margin-left: 20px;
}

/* Container */
.container {
    max-width: 800px;
    margin: 60px auto;
    text-align: center;
}

/* Card */
.card {
    background: #1e293b;
    padding: 40px;
    border-radius: 15px;
    box-shadow: 0px 0px 20px rgba(0,0,0,0.5);
}

/* Input */
textarea {
    width: 100%;
    height: 150px;
    border-radius: 10px;
    padding: 15px;
    font-size: 16px;
    border: none;
    outline: none;
}

/* Button */
button {
    margin-top: 20px;
    padding: 12px 30px;
    font-size: 18px;
    border: none;
    border-radius: 8px;
    background: #22c55e;
    color: white;
    cursor: pointer;
}

button:hover {
    background: #16a34a;
}

/* Result */
.result {
    margin-top: 30px;
    font-size: 22px;
}

.safe { color: #22c55e; }
.warning { color: #facc15; }
.danger { color: #ef4444; }

/* Loader */
.loader {
    margin-top: 20px;
    border: 6px solid #1e293b;
    border-top: 6px solid #22c55e;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    display: none;
    margin-left: auto;
    margin-right: auto;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>

<script>
function showLoader() {
    document.getElementById("loader").style.display = "block";
}
</script>

</head>

<body>

<div class="navbar">
    <h2>🚨 ScamAI</h2>
    <div>
        <a href="/">Home</a>
        <a href="/history">History</a>
        <a href="/logout">Logout</a>
    </div>
</div>

<div class="container">
    <div class="card">

        <h1>Analyze Suspicious Message</h1>

        <form method="post" onsubmit="showLoader()">
            <textarea name="message" placeholder="Paste suspicious message here..."></textarea>
            <br>
            <button type="submit">Analyze</button>
        </form>

        <div id="loader" class="loader"></div>

        {% if score is not none %}
            <div class="result">
                <p>Scam Score: {{score}}%</p>

                {% if score < 30 %}
                    <p class="safe">✅ Safe</p>
                {% elif score < 70 %}
                    <p class="warning">⚠️ Suspicious</p>
                {% else %}
                    <p class="danger">🚨 High Risk Scam</p>
                {% endif %}

                <p>{{ explanation }}</p>
            </div>
        {% endif %}

    </div>
</div>

</body>
</html>
"""
