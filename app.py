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

    # Strong scam words (high risk)
    high_risk = [
        "bank account", "send money", "urgent", "transfer",
        "click here", "verify your account", "bitcoin",
        "investment opportunity"
    ]

    # Medium risk words
    medium_risk = [
        "win", "won", "prize", "winner", "free",
        "money", "offer", "loan", "credit", "gift"
    ]

    # Suspicious patterns
    if "http://" in text or "https://" in text:
        score += 20

    if any(char.isdigit() for char in text):
        score += 5

    if text.count("!") >= 2:
        score += 10

    # Check high risk keywords
    for word in high_risk:
        if word in text:
            score += 25

    # Check medium risk keywords
    for word in medium_risk:
        if word in text:
            score += 10

    # Cap score
    if score > 100:
        score = 100

    return score
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Scam Detector</title>
</head>
<body style="font-family: Arial; text-align:center; padding:40px;">
    <h1>🚨 Scam Message Detector</h1>
    <form method="post">
        <textarea name="message" rows="10" cols="50" placeholder="Paste message here..."></textarea><br><br>
        <button type="submit">Check</button>
    </form>

    {% if score is not none %}
        <h2>Scam Score: {{score}}%</h2>
        {% if score > 60 %}
            <p style="color:red;">⚠️ High Risk Scam</p>
        {% elif score > 30 %}
            <p style="color:orange;">⚠️ Suspicious</p>
        {% else %}
            <p style="color:green;">✅ Likely Safe</p>
        {% endif %}
    {% endif %}
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
