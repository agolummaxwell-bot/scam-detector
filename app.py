from flask import Flask, request, render_template_string

app = Flask(__name__)

scam_keywords = [
    "urgent", "send money", "gift", "package", "fee",
    "crypto", "investment", "love", "secret", "manager",
    "selected", "winner", "claim", "verify", "account"
]

def detect_scam(text):
    text = text.lower()
    score = 0

    high_risk = [
        "bank account", "send money", "urgent", "transfer",
        "click here", "verify your account", "bitcoin",
        "investment opportunity", "claim now"
    ]

    medium_risk = [
        "win", "won", "prize", "winner", "free",
        "money", "offer", "loan", "credit", "gift"
    ]

    # 🚨 Strong signals
    if "http://" in text or "https://" in text:
        score += 30   # increased

    if any(char.isdigit() for char in text):
        score += 10   # increased

    if text.count("!") >= 2:
        score += 20   # increased

    # 🔴 High risk words
    for word in high_risk:
        if word in text:
            score += 30   # increased

    # 🟠 Medium risk words
    for word in medium_risk:
        if word in text:
            score += 15   # increased

    # 🚨 BONUS: combo detection (THIS IS KEY)
    if "win" in text and "money" in text:
        score += 20

    if "click" in text and "http" in text:
        score += 25

    if "urgent" in text and "money" in text:
        score += 25

    if score > 100:
        score = 100

    return score
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Scam Detector</title>
    <style>
        body {
            font-family: Arial;
            background: #0f172a;
            color: white;
            text-align: center;
            padding: 50px;
        }

        .card {
            background: #1e293b;
            padding: 30px;
            border-radius: 15px;
            width: 400px;
            margin: auto;
            box-shadow: 0px 0px 20px rgba(0,0,0,0.5);
        }

        textarea {
            width: 100%;
            height: 120px;
            border-radius: 10px;
            border: none;
            padding: 10px;
            margin-top: 10px;
        }

        button {
            margin-top: 15px;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            background: #3b82f6;
            color: white;
            font-weight: bold;
            cursor: pointer;
        }

        .score {
            margin-top: 20px;
            font-size: 22px;
        }

        .safe { color: #22c55e; }
        .warn { color: #f59e0b; }
        .danger { color: #ef4444; }

        .bar {
            height: 10px;
            background: #334155;
            border-radius: 10px;
            margin-top: 10px;
        }

        .fill {
            height: 10px;
            border-radius: 10px;
        }
    </style>
</head>

<body>

<div class="card">
    <h1>🚨 Scam Detector</h1>

    <form method="post">
        <textarea name="message" placeholder="Paste message here..."></textarea>
        <br>
        <button type="submit">Check</button>
    </form>

    {% if score is not none %}
        <div class="score">
            Scam Score: {{score}}%
        </div>

        <div class="bar">
            <div class="fill"
                 style="width: {{score}}%;
                 background:
                 {% if score < 30 %}#22c55e
                 {% elif score < 70 %}#f59e0b
                 {% else %}#ef4444
                 {% endif %};">
            </div>
        </div>

        <p class="
            {% if score < 30 %}safe
            {% elif score < 70 %}warn
            {% else %}danger
            {% endif %}
        ">
            {% if score < 30 %}
                ✅ Likely Safe
            {% elif score < 70 %}
                ⚠️ Suspicious
            {% else %}
                🚨 High Risk Scam
            {% endif %}
        </p>
    {% endif %}

</div>

</body>
</html>
"""
@app.route("/", methods=["GET", "POST"])
def home():
    score = None

    if request.method == "POST":
        message = request.form["message"]
        score = detect_scam(message)

    return render_template_string(HTML, score=score)

if __name__ == "__main__":
    app.run(debug=True)
