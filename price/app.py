
#データベースを作成する
from flask import Flask, request, jsonify
from database import db
from models import User, Plate
from flask import render_template
from google import genai
import os
import requests

# client = genai.Client(api_key="AIzaSyB2zBx6XHTPPf148w2Va-ZbR8Egj775pEM")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sushi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()


#ユーザーを作成するAPI
@app.route('/users', methods=['POST'])
def create_user():
    name = request.json["name"]
    user = User(name=name)
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "name": user.name})

#皿登録API
@app.route('/plates', methods=['POST'])
def add_plate():
    user_id = request.json["user_id"]
    price = request.json["price"]
    plate = Plate(user_id=user_id, price=price)
    db.session.add(plate)
    db.session.commit()
    return jsonify({"message": "Plate added successfully"})

#集計API
from sqlalchemy import func

@app.route("/summary/<int:user_id>")
def summary(user_id):
    #合計金額
    total = db.session.query(func.sum(Plate.price))\
        .filter(Plate.user_id == user_id).scalar() or 0
    
    #価格別枚数
    counts = db.session.query(
        Plate.price,
        func.count(Plate.id)
    ).filter(
        Plate.user_id == user_id
    ).group_by(
        Plate.price
    ).all()

    breakdown = {price: count for price, count in counts}

    return jsonify({
        "user_id": user_id,
        "total": total,
        "breakdown": breakdown
    })

#豆知識のAPI
@app.route("/trivial", methods=["GET"])
def trivia():
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt":"あなたは寿司職人です。必ず日本語で、寿司に関する豆知識を1つ、100文字以内で教えてください。フランクで親しみやすい話し方をしてください",
            "stream": False
        }
    )
    data = response.json()
    return {"text": data["response"]}
@app.route("/")
def index():
    return render_template("index.html")



if __name__ == '__main__':
    app.run(debug=True, port=5001)