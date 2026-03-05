import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
# セッション（ユーザーを記憶する仕組み）を使うための秘密の鍵
app.secret_key = 'sushi_secret_key' 

# データベースとテーブルを作成する関数
def init_db():
    # sushi_app.dbというファイルに接続（無ければ自動で作られます）
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # ユーザー情報を保存する users テーブルを作成
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gender TEXT,
            age INTEGER
        )
    ''')
    
    # 注文履歴を保存する orders テーブルを作成
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sushi_name TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# アプリを起動する前に、一度だけデータベースを初期化する
init_db()

# ------ ここから下はルーティング（URLごとの処理） ------

@app.route('/')
def index():
    return render_template('index.html')

# さきほどのHTMLからデータが送られてくるURL
@app.route('/register', methods=['POST'])
def register():
    # 1. フォームに入力されたデータを受け取る
    gender = request.form.get('gender')
    age = request.form.get('age')

    # 2. データベースに接続して、データを保存（INSERT）する
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    c.execute('INSERT INTO users (gender, age) VALUES (?, ?)', (gender, age))
    conn.commit()
    
    # 3. 今保存したユーザーのIDを取得して、「セッション」に記憶させる
    # （これをしておくと、後で「誰が注文したか」が分かります）
    user_id = c.lastrowid
    session['user_id'] = user_id
    
    conn.close()

    # 4. 処理が終わったら、マイページに移動させる
    return redirect(url_for('mypage'))

@app.route('/order_menu')
def order_menu():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('order_menu.html')

# 🌟 変更：注文処理（終わったら注文画面に戻るようにする）
@app.route('/order', methods=['POST'])
def order():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    sushi_name = request.form.get('sushi_name')
    
    if sushi_name:
        conn = sqlite3.connect('sushi_app.db')
        c = conn.cursor()
        c.execute('INSERT INTO orders (user_id, sushi_name) VALUES (?, ?)', (user_id, sushi_name))
        conn.commit()
        conn.close()
        
    # 注文後は「注文画面」に戻る（連続で頼めるように）
    return redirect(url_for('order_menu'))

# 🌟 変更：マイページ（個人の詳細データを取得する）
@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    user_id = session['user_id']
    
    conn = sqlite3.connect('sushi_app.db')
    c = conn.cursor()
    
    # 1. 自分の注文履歴（最近のものから10件だけ取得する）
    c.execute('SELECT sushi_name FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,))
    recent_orders = c.fetchall()

    # 2. 自分の好みの推移（どのネタを何回頼んだか集計）
    c.execute('SELECT sushi_name, COUNT(*) FROM orders WHERE user_id = ? GROUP BY sushi_name', (user_id,))
    preferences = c.fetchall()
    conn.close()

    # グラフ用にデータを分ける
    pref_labels = [row[0] for row in preferences]
    pref_counts = [row[1] for row in preferences]

    # フレンド追加用のQRコードにするためのデータ（今回は自分のユーザーID）
    # 実際のアプリなら https://あなたのドメイン/add_friend/1 などのURLにします
    qr_data = f"sushi_app_friend_id_{user_id}"

    return render_template('mypage.html', 
                           recent_orders=recent_orders, 
                           pref_labels=pref_labels, 
                           pref_counts=pref_counts,
                           qr_data=qr_data)

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
#if __name__ == '__main__':
#    app.run(debug=True)
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')