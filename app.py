from flask import Flask, request, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
app = Flask(__name__)
# AI Training Data
messages = [
    # 🚨 SCAM (1)
    "You have won a prize claim now",
    "Send money urgently to receive funds",
    "Click here to win cash prize",
    "Free investment opportunity",
    "Verify your bank account now",
    "Urgent transfer required now",
    "Claim your reward immediately",
    "You are selected as a winner",
    "Send your details to receive money",
    "Congratulations you won lottery",
    "Click link to claim your money now",
    "Account suspended verify now",
    "You won $5000 click here now",
    "Limited time offer act fast",
    "Bitcoin investment double your money",

    # ✅ NORMAL (0)
    "Hello how are you doing today",
    "Let's meet tomorrow",
    "This is a normal message",
    "Are you available for a call",
    "See you later",
    "Can we talk later",
    "I will send the document tomorrow",
    "Thank you for your help",
    "Let's have lunch together",
    "How is your family",
    "Please review this file",
    "Meeting starts at 3pm",
    "Call me when you are free",
    "I will arrive soon",
    "Good morning have a great day"
]
    "You have won a prize claim now",
    "Send money urgently",
    "Click here to win cash",
    "Free investment opportunity",
    "Verify your bank account now",
    "Hello how are you doing today",
    "Let's meet tomorrow",
    "This is a normal message",
    "Are you available for a call",
    "See you later"
]

labels = [1]*15 + [0]*15

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(messages)

model = MultinomialNB()
model.fit(X, labels)

def detect_scam(text):
    text = text.lower()

    # AI prediction
    X_input = vectorizer.transform([text])
    prediction = model.predict(X_input)[0]
    probability = model.predict_proba(X_input)[0][1]

    score = int(probability * 100)

    # 🚨 Boost score for dangerous patterns
    if "http" in text or "www" in text:
        score += 20

    if any(char.isdigit() for char in text):
        score += 10

    if "urgent" in text:
        score += 15

    return min(score, 100)
    ret# AI prediction
X_test = vectorizer.transform([text])
ai_score = model.predict_proba(X_test)[0][1] * 100

# Combine both systems
final_score = int((score + ai_score) / 2)

return min(final_score, 100)urn score
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Scam Detector AI</title>
    <style>
        body {
            font-family: Arial;
            background: #0f172a;
            color: white;
            text-align: center;
            padding: 50px;
        }

        h1 { font-size: 40px; }

        textarea {
            width: 60%;
            height: 150px;
            border-radius: 10px;
            padding: 15px;
            font-size: 16px;
            border: none;
            outline: none;
        }

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

        button:hover { background: #16a34a; }

        .card {
            background: #1e293b;
            padding: 30px;
            border-radius: 15px;
            width: 70%;
            margin: auto;
        }

        .result { margin-top: 30px; font-size: 22px; }

        .safe { color: #22c55e; }
        .warning { color: #facc15; }
        .danger { color: #ef4444; }

        /* 🔥 LOADING ANIMATION */
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

        .explanation {
            margin-top: 20px;
            font-size: 16px;
            color: #cbd5f5;
        }
    </style>

    <script>
        function showLoader() {
            document.getElementById("loader").style.display = "block";
        }
    </script>
</head>

<body>

<div class="card">
    <h1>🚨 Scam Detector AI</h1>

    <form method="post" onsubmit="showLoader()">
        <textarea name="message" placeholder="Paste suspicious message here..."></textarea><br>
        <button type="submit">Analyze Message</button>
    </form>

    <div id="loader" class="loader"></div>

    {% if score is not none %}
        <div class="result">
            <p>Scam Score: {{score}}%</p>

            {% if score < 30 %}
                <p class="safe">✅ Safe Message</p>
            {% elif score < 70 %}
                <p class="warning">⚠️ Suspicious Message</p>
            {% else %}
                <p class="danger">🚨 High Risk Scam</p>
            {% endif %}

            <div class="explanation">
                <p><strong>Why?</strong></p>
                <p>{{ explanation }}</p>
            </div>
        </div>
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
