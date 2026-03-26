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

    scores = [row[1] for row in data]
    messages = [row[0] for row in data]

    avg_score = int(sum(scores)/len(scores)) if scores else 0
    total = len(scores)

    return render_template_string(HISTORY_HTML,
        scores=scores,
        messages=messages,
        avg_score=avg_score,
        total=total
    )
# ---------------- UI ----------------

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>ScamAI Dashboard</title>

<style>
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: white;
    display: flex;
}

/* Sidebar */
.sidebar {
    width: 220px;
    height: 100vh;
    background: #020617;
    padding: 20px;
    position: fixed;
}

.sidebar h2 {
    color: #22c55e;
}

.sidebar a {
    display: block;
    margin: 20px 0;
    color: #94a3b8;
    text-decoration: none;
}

.sidebar a:hover {
    color: white;
}

/* Main content */
.main {
    margin-left: 240px;
    padding: 40px;
    width: 100%;
}

/* Card */
.card {
    background: #1e293b;
    padding: 30px;
    border-radius: 15px;
    max-width: 800px;
}

/* Input */
textarea {
    width: 100%;
    height: 150px;
    border-radius: 10px;
    padding: 15px;
    border: none;
    outline: none;
}

/* Button */
button {
    margin-top: 20px;
    padding: 10px 25px;
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
    margin-top: 20px;
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

<!-- Sidebar -->
<div class="sidebar">
    <h2>🚨 ScamAI</h2>
    <a href="/">Dashboard</a>
    <a href="/history">History</a>
    <a href="/logout">Logout</a>
</div>

<!-- Main -->
<div class="main">
    <h1>Dashboard</h1>

    <div class="card">

        <h2>Analyze Message</h2>

        <form method="post" onsubmit="showLoader()">
            <textarea name="message" placeholder="Paste suspicious message..."></textarea>
            <button type="submit">Analyze</button>
        </form>

        <div id="loader" class="loader"></div>

        {% if score is not none %}
            <div class="result">
                <p><strong>Scam Score:</strong> {{score}}%</p>

                {% if score < 30 %}
                    <p class="safe">Safe</p>
                {% elif score < 70 %}
                    <p class="warning">Suspicious</p>
                {% else %}
                    <p class="danger">High Risk Scam</p>
                {% endif %}

                <p>{{ explanation }}</p>
            </div>
        {% endif %}

    </div>
</div>

</body>
</html>
"""
HISTORY_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Analytics</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
body {
    font-family: Arial;
    background: #0f172a;
    color: white;
    padding: 40px;
}

.card {
    background: #1e293b;
    padding: 30px;
    border-radius: 15px;
    margin-bottom: 30px;
}

h1 { text-align: center; }

.stat {
    font-size: 20px;
    margin: 10px 0;
}
</style>

</head>

<body>

<h1>📊 Analytics Dashboard</h1>

<div class="card">
    <p class="stat">Total Scans: {{total}}</p>
    <p class="stat">Average Risk Score: {{avg_score}}%</p>
</div>

<div class="card">
    <canvas id="chart"></canvas>
</div>

<script>
const scores = {{scores|tojson}};

const ctx = document.getElementById('chart');

new Chart(ctx, {
    type: 'line',
    data: {
        labels: scores.map((_, i) => "Scan " + (i+1)),
        datasets: [{
            label: 'Scam Score %',
            data: scores,
            borderWidth: 2
        }]
    },
    options: {
        scales: {
            y: { beginAtZero: true, max: 100 }
        }
    }
});
</script>

</body>
</html>
"""
