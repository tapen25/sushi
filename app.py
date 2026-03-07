import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import os
from google import genai
from google.genai.types import GenerateImageConfig # 🌟 Imagen用の設定を追加
import base64

app = Flask(__name__)
# セッション（ユーザーを記憶する仕組み）を使うための秘密の鍵
app.secret_key = 'sushi_secret_key' 

# ---------------------------------------------------------
# 1. データベース構築（起動時に1回だけ呼ばれる）
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # ユーザー用テーブル
    #c.execute('''
    #    CREATE TABLE IF NOT EXISTS users (
    #        id INTEGER PRIMARY KEY AUTOINCREMENT,
    #        username TEXT,
    #        gender TEXT,
    #        age INTEGER,
   #         group_id INTEGER    /* 🌟 新規：今いるテーブルのID */
     #   )
    #''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            gender TEXT,
            age INTEGER,
            group_id INTEGER,
            fairy_image_base64 TEXT    /* 🌟 新規：生成された画像のBase64データ */
        )
    ''')
    
    # 友達用テーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,    /* 自分 */
            friend_id INTEGER,  /* 友達 */
            UNIQUE(user_id, friend_id) /* 同じ人を2回登録しないための設定 */
        )
    ''')
    
    # 注文用テーブル（price入り）
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,    /* 誰が頼んだか */
            group_id INTEGER,   /* どのテーブル(代表者)の注文か */
            sushi_name TEXT,
            price INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

# アプリ起動時にデータベースをセットアップ
init_db()

# ---------------------------------------------------------
# 2. 認証・ログイン関連
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    gender = request.form.get('gender')
    age = request.form.get('age')

    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    existing_user = c.fetchone()
    
    if existing_user:
        user_id = existing_user[0]
        session['user_id'] = user_id
        session['group_id'] = user_id # 自分が代表
        # 🌟 昔のデータでログインした時も、最初は「一人のテーブル」としてリセットする
        c.execute('UPDATE users SET group_id = ? WHERE id = ?', (user_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('mypage'))
    else:
        c.execute('INSERT INTO users (username, gender, age) VALUES (?, ?, ?)', (username, gender, age))
        user_id = c.lastrowid
        session['user_id'] = user_id
        session['group_id'] = user_id # 自分が代表
        # 🌟 データベースにもテーブル情報を保存
        c.execute('UPDATE users SET group_id = ? WHERE id = ?', (user_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('order_menu'))
# ---------------------------------------------------------
# 3. 注文関連
# ---------------------------------------------------------
@app.route('/order_menu')
def order_menu():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    group_id = session.get('group_id', user_id)
    
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    c.execute('SELECT SUM(price) FROM orders WHERE user_id = ?', (user_id,))
    my_total = c.fetchone()[0]
    my_total = my_total if my_total else 0 
    
    c.execute('SELECT SUM(price) FROM orders WHERE group_id = ?', (group_id,))
    group_total = c.fetchone()[0]
    group_total = group_total if group_total else 0
    
    # 🌟 新規追加：同じテーブルにいる他の人（自分以外）の名前を取得
    c.execute('SELECT username FROM users WHERE group_id = ? AND id != ?', (group_id, user_id))
    companion_rows = c.fetchall()
    # ['Aさん', 'Bさん'] のようなリストにする
    companions = [row[0] for row in companion_rows] 
    
    conn.close()
    
    # companions リストも一緒に HTML に渡す
    return render_template('order_menu.html', my_total=my_total, group_total=group_total, companions=companions)

@app.route('/order', methods=['POST'])
def order():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    # 🌟 メモしてあるテーブルIDを取り出す（無ければ自分のIDにする）
    group_id = session.get('group_id', user_id) 
    
    sushi_name = request.form.get('sushi_name')
    price = request.form.get('price')
    
    if sushi_name and price is not None:
        try:
            conn = sqlite3.connect('sushi_app.db')
            c = conn.cursor()
            # 🌟 group_id も一緒にデータベースに保存する！
            c.execute('INSERT INTO orders (user_id, group_id, sushi_name, price) VALUES (?, ?, ?, ?)', 
                      (user_id, group_id, sushi_name, price))
            conn.commit()
        except Exception as e:
            print(f"データベース保存エラー: {e}")
        finally:
            conn.close()
            
    return redirect(url_for('order_menu'))

# ---------------------------------------------------------
# 4. 豆知識API (Gemini)
# ---------------------------------------------------------
@app.route("/trivial", methods=["GET"])
def trivia():
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"text": "大将は今お休み中でい！（APIキーが設定されていません）"}
            
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='あなたは寿司職人です。必ず日本語で、寿司に関する豆知識を1つ、100文字以内で教えてください。フランクで親しみやすい話し方をしてください。'
        )
        return {"text": response.text}
    except Exception as e:
        print(f"Gemini API エラー: {e}") 
        return {"text": "大将は今忙しいみたいでい！（通信エラー）"}

    

# ---------------------------------------------------------
# 5. マイページ・フレンド関連
# ---------------------------------------------------------
@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user_row = c.fetchone()
    username = user_row[0] if user_row else "名無し"
    
    c.execute('SELECT sushi_name FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,))
    recent_orders = c.fetchall()

    c.execute('SELECT sushi_name, COUNT(*) FROM orders WHERE user_id = ? GROUP BY sushi_name', (user_id,))
    preferences = c.fetchall()

    c.execute('SELECT fairy_image_base64 FROM users WHERE id = ?', (user_id,))
    user_row = c.fetchone()
    # もし画像があれば取り出す。なければ None
    fairy_image_base64 = user_row[0] if user_row else None

    # 🌟 ここにフレンド一覧取得処理を移動しました
    c.execute('''
        SELECT users.id, users.username 
        FROM friends 
        JOIN users ON friends.friend_id = users.id 
        WHERE friends.user_id = ?
    ''', (user_id,))
    friends_list = c.fetchall()
    
    conn.close()

    pref_labels = [row[0] for row in preferences]
    pref_counts = [row[1] for row in preferences]
    qr_url = f"{request.host_url}join_table/{user_id}"
    return render_template('mypage.html', 
                           username=username, 
                           recent_orders=recent_orders, 
                           pref_labels=pref_labels, 
                           pref_counts=pref_counts,
                           qr_url=qr_url,
                           friends_list=friends_list,
                           fairy_image_base64=fairy_image_base64)

@app.route('/join_table/<int:host_id>')
def join_table(host_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    my_id = session['user_id']
    session['group_id'] = host_id
    
    # 🌟 データベースの自分のデータも「相手のテーブルに移動したよ」と更新する
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    c.execute('UPDATE users SET group_id = ? WHERE id = ?', (host_id, my_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('order_menu'))

# 🌟 下にあったものを正しい位置に移動しました
@app.route('/friend_detail/<int:friend_id>')
def friend_detail(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()

    c.execute('SELECT username FROM users WHERE id = ?', (friend_id,))
    friend_row = c.fetchone()
    if not friend_row:
        conn.close()
        return "ユーザーが見つかりません"
    friend_name = friend_row[0]

    c.execute('SELECT sushi_name, COUNT(*) FROM orders WHERE user_id = ? GROUP BY sushi_name', (friend_id,))
    preferences = c.fetchall()
    conn.close()

    pref_labels = [row[0] for row in preferences]
    pref_counts = [row[1] for row in preferences]

    return render_template('mypage.html',
                           username=f"【フレンド】{friend_name}", 
                           recent_orders=[], 
                           pref_labels=pref_labels, 
                           pref_counts=pref_counts,
                           qr_url=None, 
                           friends_list=[])

# ---------------------------------------------------------
# 6. 管理者画面
# ---------------------------------------------------------
@app.route('/admin')
def admin():
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    c.execute('SELECT users.id, users.gender, users.age, orders.sushi_name FROM users JOIN orders ON users.id = orders.user_id')
    all_data = c.fetchall()

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
    
    c.execute('''
        SELECT users.gender, COUNT(*)
        FROM users JOIN orders ON users.id = orders.user_id
        GROUP BY users.gender
    ''')
    gender_data = c.fetchall()
    conn.close()

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

    return render_template('admin.html', 
                           all_data=all_data, 
                           ranking_data=ranking_data,
                           age_groups=age_groups_order, 
                           sushi_datasets=sushi_datasets,
                           gender_counts=gender_counts)
@app.route('/generate_fairy')
def generate_fairy():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return "APIキーが設定されていません。"

    # 1. データベースから自分の「お寿司の好み（ランキング）」を取得
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    # 🌟 ここ重要！好みを取得する（マイページと同じ処理）
    c.execute('SELECT sushi_name FROM orders WHERE user_id = ? GROUP BY sushi_name ORDER BY COUNT(*) DESC LIMIT 3', (user_id,))
    preferences = c.fetchall()
    
    # 2. Gemini API（Imagen）に渡すプロンプトを作成
    if preferences:
        # 好みランキングからプロンプトを作る
        top1 = preferences[0][0]
        top2 = preferences[1][0] if len(preferences) > 1 else ""
        
        # 🌟 ここでAIへの「注文書」を作成！
        # 日本語でも Imagen 3 は理解します。
        prompt = f"かわいいデジタルアートスタイルの小さな寿司の妖精キャラクター。一番の特徴は「{top1}」に基づいています。"
        if top2:
            prompt += f"二番目の特徴は「{top2}」の影響を受けています。"
        prompt += "白背景。Vibrant colors."
    else:
        # 注文がない場合のデフォルト
        prompt = "かわいいデジタルアートスタイルの小さな寿司の妖精キャラクター。様々な種類のお寿司の影響を受けています。白背景。Vibrant colors."

    # 3. Imagen API（画像生成）を呼び出す！
    client = genai.Client(api_key=api_key)
    try:
        # Imagen 3 モデルを使用して画像を生成
        # 🌟 呼び出しに数秒かかります！
        response = client.models.generate_image(
            model='imagen-3',
            prompt=prompt,
            config=GenerateImageConfig(
                number_of_images=1,
                aspect_ratio="1:1", # 正方形
                output_mime_type="image/png" # 出力形式
            )
        )
        
        # 生成された画像（バイトデータ）
        image_bytes = response.generated_images[0].image_bytes
        
        # 4. バイトデータを文字の暗号（Base64）に変換！
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')
        
        # 5. データベースの自分のデータに保存！
        c.execute('UPDATE users SET fairy_image_base64 = ? WHERE id = ?', (encoded_string, user_id))
        conn.commit()
        
    except Exception as e:
        print(f"Imagen API エラー: {e}")
        conn.close()
        return f"妖精の召喚に失敗しましたでい... （エラー: {e}）"
        
    conn.close()
    
    # 妖精ができたら、マイページにリダイレクト！
    return redirect(url_for('mypage'))
# ---------------------------------------------------------
# アプリ起動のスイッチ（必ず一番下！）
# ---------------------------------------------------------
if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0')