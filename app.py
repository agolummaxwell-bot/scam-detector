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
