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

    total = len(scores)
    avg = int(sum(scores)/total) if total else 0

    high = len([s for s in scores if s > 70])
    medium = len([s for s in scores if 30 <= s <= 70])
    low = len([s for s in scores if s < 30])

    return render_template_string(HISTORY_HTML,
        scores=scores,
        total=total,
        avg=avg,
        high=high,
        medium=medium,
        low=low
    )
    @app.route("/download")
def download():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT message, score FROM history WHERE username=?", (session["user"],))
    data = c.fetchall()
    conn.close()

    csv_data = "Message,Score\n"
    for msg, score in data:
        csv_data += f"{msg},{score}\n"

    return csv_data, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=history.csv'
    }
# ---------------- UI ----------------

HISTORY_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Dashboard</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
body {
    background: #0f172a;
    color: white;
    font-family: Arial;
    padding: 30px;
}

h1 { text-align: center; }

.grid {
    display: flex;
    gap: 20px;
    margin-bottom: 30px;
}

.card {
    flex: 1;
    background: #1e293b;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
}

.big { font-size: 28px; }

button {
    padding: 10px 20px;
    background: #22c55e;
    border: none;
    border-radius: 8px;
    color: white;
    cursor: pointer;
}
</style>

</head>

<body>

<h1>📊 Your Analytics</h1>

<div class="grid">
    <div class="card"><p>Total</p><div class="big">{{total}}</div></div>
    <div class="card"><p>Avg Score</p><div class="big">{{avg}}%</div></div>
    <div class="card"><p>High Risk</p><div class="big">{{high}}</div></div>
    <div class="card"><p>Medium</p><div class="big">{{medium}}</div></div>
    <div class="card"><p>Safe</p><div class="big">{{low}}</div></div>
</div>

<div class="card">
    <canvas id="chart"></canvas>
</div>

<br>
<a href="/download"><button>⬇ Download CSV</button></a>

<script>
const scores = {{scores|tojson}};

new Chart(document.getElementById('chart'), {
    type: 'line',
    data: {
        labels: scores.map((_, i) => "Scan " + (i+1)),
        datasets: [{
            label: 'Scam Score',
            data: scores,
            borderWidth: 2
        }]
    }
});
</script>

</body>
</html>
"""
