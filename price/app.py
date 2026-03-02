
#データベースを作成する
from flask import Flask, request, jsonify
from database import db
from models import User, Plate
from flask import render_template

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

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True, port=5001)