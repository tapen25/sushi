import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
import requests
import os
from google import genai
app = Flask(__name__)
# セッション（ユーザーを記憶する仕組み）を使うための秘密の鍵
app.secret_key = 'sushi_secret_key' 

# データベースとテーブルを作成する関数
def init_db():
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,    /* ← 新しく追加！ */
            gender TEXT,
            age INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sushi_name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,    /* 自分 */
            friend_id INTEGER,  /* 友達 */
            UNIQUE(user_id, friend_id) /* 同じ人を2回登録しないための設定 */
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sushi_name TEXT,
            price INTEGER    /* 🌟 お友達のアイデア：値段を追加！ */
        )
    ''')
    conn.commit()
    conn.close()
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# 🌟 変更：ユーザーネームも一緒に受け取って保存する
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    gender = request.form.get('gender')
    age = request.form.get('age')

    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # 1. まず、入力されたユーザーネームがすでにデータベースに存在するか探す
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    existing_user = c.fetchone()
    
    if existing_user:
        # 【ログイン処理】すでに存在する場合
        # existing_user[0] にはその人の昔のユーザーIDが入っているので、それをセッションに復元する
        session['user_id'] = existing_user[0]
        conn.close()
        
        # ログインした時は、過去の記録が見たいはずなので「マイページ」に飛ばす
        return redirect(url_for('mypage'))
        
    else:
        # 【新規登録処理】存在しない新しい名前の場合
        # これまで通り、新しくデータベースに保存する
        c.execute('INSERT INTO users (username, gender, age) VALUES (?, ?, ?)', (username, gender, age))
        conn.commit()
        session['user_id'] = c.lastrowid
        conn.close()

        # 新規のお客さんは、まずは注文したいはずなので「注文画面」に飛ばす
        return redirect(url_for('order_menu'))

@app.route('/order_menu')
def order_menu():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('order_menu.html')

# 🌟 変更：注文処理（終わったら注文画面に戻るようにする）
@app.route('/order', methods=['POST'])
def order():
    # 誰からの注文か確認（あなたのログイン機能）
    if 'user_id' not in session:
        return {"error": "ログインしていません"}, 401
        
    user_id = session['user_id']
    
    # お友達の fetch から送られてくるデータ(JSON)を受け取る
    data = request.get_json()
    sushi_name = data.get('sushi_name')
    price = data.get('price')
    
    if sushi_name and price is not None:
        conn = sqlite3.connect('sushi_app.db')
        c = conn.cursor()
        # ネタの名前と値段の両方を保存する
        c.execute('INSERT INTO orders (user_id, sushi_name, price) VALUES (?, ?, ?)', 
                  (user_id, sushi_name, price))
        conn.commit()
        conn.close()
        
    # 画面を切り替えずに「成功したよ」という合図だけを返す
    return {"message": "へい！まいどあり！"}


# 🌟 お友達の機能：豆知識APIを追加
@app.route("/trivial", methods=["GET"])
def trivia():
    try:
        # パソコンやRenderの設定からAPIキーを読み込みます
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            return {"text": "大将は今お休み中でい！（APIキーが設定されていません）"}
            
        # Geminiクライアントの準備
        client = genai.Client(api_key=api_key)
        
        # Geminiに指示を出す（高速で賢い gemini-2.5-flash モデルを使用）
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='あなたは寿司職人です。必ず日本語で、寿司に関する豆知識を1つ、100文字以内で教えてください。フランクで親しみやすい話し方をしてください。'
        )
        
        return {"text": response.text}
        
    except Exception as e:
        print(f"Gemini API エラー: {e}") # ターミナルでエラー原因を確認できるようにする
        return {"text": "大将は今忙しいみたいでい！（通信エラー）"}

# 🌟 変更：マイページでユーザーネームを表示するために取得する
@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # 🌟 追加：自分のユーザーネームを取得する
    c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user_row = c.fetchone()
    # もしデータがあれば1つ目を取り出す。なければ「名無し」にする
    username = user_row[0] if user_row else "名無し"
    
    c.execute('SELECT sushi_name FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,))
    recent_orders = c.fetchall()

    c.execute('SELECT sushi_name, COUNT(*) FROM orders WHERE user_id = ? GROUP BY sushi_name', (user_id,))
    preferences = c.fetchall()
    conn.close()

    pref_labels = [row[0] for row in preferences]
    pref_counts = [row[1] for row in preferences]
    qr_url = f"{request.host_url}add_friend/{user_id}"

    # username を HTML に渡す
    return render_template('mypage.html', 
                           username=username, 
                           recent_orders=recent_orders, 
                           pref_labels=pref_labels, 
                           pref_counts=pref_counts,
                           qr_url=qr_url)
@app.route('/admin')
def admin():
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # 1. 全データ一覧
    c.execute('SELECT users.id, users.gender, users.age, orders.sushi_name FROM users JOIN orders ON users.id = orders.user_id')
    all_data = c.fetchall()

    # 2. 売上ランキング
    c.execute('''
        SELECT orders.sushi_name, users.gender, 
            CASE 
                WHEN users.age < 10 THEN '10代未満'
                WHEN users.age >= 10 AND users.age < 20 THEN '10代'
                WHEN users.age >= 20 AND users.age < 25 THEN '20代前半'
                WHEN users.age >= 25 AND users.age < 30 THEN '20代後半'
                WHEN users.age >= 30 AND users.age < 35 THEN '30代前半'
                WHEN users.age >= 35 AND users.age < 40 THEN '30代後半'
                ELSE '40代以上'
            END AS age_group, COUNT(*) AS count
        FROM users JOIN orders ON users.id = orders.user_id
        GROUP BY orders.sushi_name, users.gender, age_group ORDER BY count DESC
    ''')
    ranking_data = c.fetchall()

    # 3. 世代別・ネタ別の集計データ（積み上げ棒グラフ用）
    c.execute('''
        SELECT 
            CASE 
                WHEN users.age < 10 THEN '10代未満'
                WHEN users.age >= 10 AND users.age < 20 THEN '10代'
                WHEN users.age >= 20 AND users.age < 25 THEN '20代前半'
                WHEN users.age >= 25 AND users.age < 30 THEN '20代後半'
                WHEN users.age >= 30 AND users.age < 35 THEN '30代前半'
                WHEN users.age >= 35 AND users.age < 40 THEN '30代後半'
                ELSE '40代以上'
            END AS age_group,
            orders.sushi_name,
            COUNT(*)
        FROM users JOIN orders ON users.id = orders.user_id
        GROUP BY age_group, orders.sushi_name
    ''')
    raw_chart_data = c.fetchall()
    
    # 4. 男女比のグラフ用データ
    c.execute('''
        SELECT users.gender, COUNT(*)
        FROM users JOIN orders ON users.id = orders.user_id
        GROUP BY users.gender
    ''')
    gender_data = c.fetchall()

    # 🌟 ここですべてのデータ取得が終わったので、データベースを閉じる（1回だけ）
    conn.close()

    # ----- 取得したデータの整理（Pythonの処理） -----
    
    gender_counts = {'male': 0, 'female': 0, 'other': 0}
    for row in gender_data:
        gender_counts[row[0]] = row[1]

    age_groups_order = ['10代未満', '10代', '20代前半', '20代後半', '30代前半', '30代後半', '40代以上']
    sushi_datasets = {}
    
    sushi_names = set([row[1] for row in raw_chart_data])
    for name in sushi_names:
        sushi_datasets[name] = [0] * len(age_groups_order)

    for row in raw_chart_data:
        age_group = row[0]
        sushi_name = row[1]
        count = row[2]
        if age_group in age_groups_order:
            idx = age_groups_order.index(age_group)
            sushi_datasets[sushi_name][idx] = count

    # HTMLにデータを渡す
    return render_template('admin.html', 
                           all_data=all_data, 
                           ranking_data=ranking_data,
                           age_groups=age_groups_order, 
                           sushi_datasets=sushi_datasets,
                           gender_counts=gender_counts)
@app.route('/add_friend/<int:friend_id>')
def add_friend(friend_id):
    # まだログインしていない人がQRを読み取った場合は、まず登録(ログイン)画面へ飛ばす
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    my_id = session['user_id']
    
    # 自分自身をQRコードで読み取ってしまった場合はエラーを防ぐ
    if my_id == friend_id:
        return redirect(url_for('mypage'))

    # データベースに友達として記録する
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    try:
        # INSERT OR IGNORE で、すでに友達だった場合はエラーにならず無視する
        c.execute('INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)', (my_id, friend_id))
        
        # 相互フォローにしたい場合は、相手側からも自分をフォローしたことにする
        c.execute('INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)', (friend_id, my_id))
        
        conn.commit()
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        conn.close()

    # 友達登録が終わったら、自分のマイページに戻る
    return redirect(url_for('mypage'))
#if __name__ == '__main__':
 #   app.run(debug=True)
if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0')