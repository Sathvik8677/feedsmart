from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import mysql.connector
from dotenv import load_dotenv
import hashlib, json, os, uuid
import smtplib, random
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
load_dotenv()

app = Flask(__name__)
app.secret_key = 'feedsmart_v3_ultra_2026'

# ── MySQL CONFIG — update password if needed ─────────────────────────────────
def db():
    return mysql.connector.connect(
        host=os.environ.get("MYSQLHOST"),
        port=int(os.environ.get("MYSQLPORT", 3306)),
        user=os.environ.get("MYSQLUSER"),
        password=os.environ.get("MYSQLPASSWORD"),
        database=os.environ.get("MYSQLDATABASE")
    )
# ── DB HELPERS ───────────────────────────────────────────────────────────────
def db():
    import mysql.connector
    import os
    from urllib.parse import urlparse

    url = os.environ.get("MYSQL_URL")
    parsed = urlparse(url)

    password = parsed.password

    # 🔥 FIX: convert bytes → string
    if isinstance(password, bytes):
        password = password.decode()

    return mysql.connector.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=password,   # ✅ fixed
        database=parsed.path[1:]
    )

def qr(conn, sql, params=()):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    return cur.fetchall()

def q1(conn, sql, params=()):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    return cur.fetchone()

def qx(conn, sql, params=()):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    return cur.lastrowid

def hp(p):
    return hashlib.sha256(p.encode()).hexdigest()

def cu():
    if 'uid' not in session:
        return None
    conn = db()
    u = q1(conn, "SELECT * FROM users WHERE id=%s", (session['uid'],))
    conn.close()
    return u

def is_past_cutoff(cutoff_time):
    now = datetime.now()
    try:
        h, m = map(int, str(cutoff_time).split(':'))
        cutoff = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return now >= cutoff
    except:
        return False
def send_otp_email(to_email, otp):
    import os, smtplib
    from email.mime.text import MIMEText

    sender = os.environ.get('GMAIL_USER')
    password = os.environ.get('GMAIL_PASS')

    msg = MIMEText(f"Your FeedSmart OTP is: {otp}")
    msg['Subject'] = "FeedSmart OTP"
    msg['From'] = sender
    msg['To'] = to_email

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
    server.login(sender, password)
    server.send_message(msg)
    server.quit()

# ── INIT DB ──────────────────────────────────────────────────────────────────
def init_db():
    # Step 1: create database
    base = mysql.connector.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )
    cur = base.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS railway")
    base.commit()
    base.close()

    # Step 2: create tables
    conn = db()
    cur = conn.cursor()

    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(64) NOT NULL,
            role VARCHAR(20) DEFAULT 'student',
            roll_no VARCHAR(50),
            phone VARCHAR(20),
            user_type VARCHAR(20) DEFAULT 'dayscholar',
            mess_balance DECIMAL(10,2) DEFAULT 0.00,
            monthly_bill DECIMAL(10,2) DEFAULT 0.00,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS mess_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            admin_id INT NOT NULL,
            meal_type VARCHAR(30) NOT NULL,
            enabled TINYINT DEFAULT 1,
            start_time VARCHAR(10) NOT NULL,
            end_time VARCHAR(10) NOT NULL,
            cutoff_time VARCHAR(10) NOT NULL,
            cost DECIMAL(8,2) DEFAULT 0.00,
            description TEXT,
            UNIQUE KEY uq_admin_meal (admin_id, meal_type)
        )""",
        """CREATE TABLE IF NOT EXISTS menu (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE NOT NULL,
            meal_type VARCHAR(30) NOT NULL,
            items TEXT NOT NULL,
            admin_id INT,
            UNIQUE KEY uq_date_meal (date, meal_type)
        )""",
        """CREATE TABLE IF NOT EXISTS opt_ins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            date DATE NOT NULL,
            meal_type VARCHAR(30) NOT NULL,
            status VARCHAR(10) DEFAULT 'in',
            UNIQUE KEY uq_optin (user_id, date, meal_type)
        )""",
        """CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            date DATE NOT NULL,
            meal_type VARCHAR(30) NOT NULL,
            cost_charged DECIMAL(8,2) DEFAULT 0.00,
            scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scanned_by INT,
            UNIQUE KEY uq_att (user_id, date, meal_type)
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            date DATE NOT NULL,
            meal_type VARCHAR(30) NOT NULL,
            rating INT NOT NULL,
            taste INT DEFAULT 3,
            quantity INT DEFAULT 3,
            cleanliness INT DEFAULT 3,
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            body TEXT NOT NULL,
            priority VARCHAR(20) DEFAULT 'normal',
            created_by INT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            type VARCHAR(20) NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            method VARCHAR(30) DEFAULT 'upi',
            status VARCHAR(20) DEFAULT 'success',
            reference VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS monthly_bills (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            month VARCHAR(7) NOT NULL,
            total DECIMAL(10,2) DEFAULT 0.00,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    ]
  

    for s in statements:
        cur.execute(s)
    conn.commit()

    # Seed admin
    ap = hp('admin123')
    existing = q1(conn, "SELECT id FROM users WHERE email=%s", ('admin@feedsmart.com',))
    if not existing:
        qx(conn, """
        INSERT INTO users(name,email,password,role,roll_no,phone,user_type,monthly_bill)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            'Admin',
            'admin@feedsmart.com',
            ap,
            'admin',
            'ADMIN001',
            '9999999999',
            'dayscholar',
            0.00
        ))

    # Seed students
    sp = hp('student123')
    for i in range(1, 6):
        ex = q1(conn, "SELECT id FROM users WHERE email=%s", (f'student{i}@feedsmart.com',))
        if not ex:
            qx(conn, "INSERT INTO users(name,email,password,role,roll_no,phone) VALUES(%s,%s,%s,%s,%s,%s)",
               (f'Student {i}', f'student{i}@feedsmart.com', sp, 'student', f'23CSE00{i}', f'98765432{i:02d}'))
    conn.commit()

    # Seed mess config
    admin = q1(conn, "SELECT id FROM users WHERE role='admin' LIMIT 1")
    if admin:
        aid = admin['id']
        configs = [
            (aid, 'breakfast', 1, '07:00', '09:30', '06:30', 60, 'Idli, Vada, Sambar, Chutney, Tea/Coffee'),
            (aid, 'lunch',     1, '12:00', '14:30', '10:30', 80, 'Rice, Dal, Curry, Curd, Pickle, Papad'),
            (aid, 'snacks',    1, '16:00', '17:30', '15:00', 30, 'Samosa, Tea/Coffee, Biscuits'),
            (aid, 'dinner',    1, '19:30', '21:30', '18:00', 70, 'Chapati, Rice, Dal, Sabzi, Salad'),
        ]
        for cfg in configs:
            ex = q1(conn, "SELECT id FROM mess_config WHERE admin_id=%s AND meal_type=%s", (aid, cfg[1]))
            if not ex:
                qx(conn, """INSERT INTO mess_config(admin_id,meal_type,enabled,start_time,end_time,cutoff_time,cost,description)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""", cfg)
        conn.commit()

        meals = {
            'breakfast': 'Idli, Vada, Sambar, Chutney',
            'lunch':     'Rice, Dal, Paneer Curry, Curd',
            'snacks':    'Samosa, Tea, Biscuits',
            'dinner':    'Chapati, Dal, Mix Veg, Salad'
        }
        for off in range(-1, 6):
            d = (date.today() + timedelta(days=off)).strftime('%Y-%m-%d')
            for mt, items in meals.items():
                ex = q1(conn, "SELECT id FROM menu WHERE date=%s AND meal_type=%s", (d, mt))
                if not ex:
                    qx(conn, "INSERT INTO menu(date,meal_type,items,admin_id) VALUES(%s,%s,%s,%s)",
                       (d, mt, items, aid))
        conn.commit()


    conn.close()
    print("✅ Database initialized!")

# ── AUTH ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'uid' not in session:
        return redirect(url_for('login'))
    u = cu()
    return redirect(url_for('admin_dash' if u and u['role'] == 'admin' else 'student_dash'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = db()
        u = q1(conn, "SELECT * FROM users WHERE email=%s AND password=%s",
               (request.form['email'], hp(request.form['password'])))
        conn.close()
        if u:
            session['uid'] = u['id']
            session['role'] = u['role']
            return redirect(url_for('admin_dash' if u['role'] == 'admin' else 'student_dash'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        if not session.get('otp_verified'):
            flash("Please verify OTP first ❌", "error")
            return redirect(url_for('register'))

        try:
            conn = db()

            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')

            print("EMAIL:", email)

            # ✅ validation
            if not name or not email or not password:
                flash("All fields required ❌", "error")
                return redirect(url_for('register'))

            # ✅ OTP email match
            if email != session.get('otp_email'):
                flash("Use same email for OTP ❌", "error")
                return redirect(url_for('register'))

            # ✅ duplicate check
            existing = q1(conn, "SELECT id FROM users WHERE email=%s", (email,))
            if existing:
                flash("Email already registered ❌", "error")
                return redirect(url_for('register'))

            # ✅ insert
            qx(conn, """
            INSERT INTO users(name,email,password,roll_no,phone,mess_balance,user_type,monthly_bill)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                name,
                email,
                hp(password),
                request.form.get('roll_no'),
                request.form.get('phone'),
                0.00,
                'dayscholar',
                0.00
            ))

            conn.commit()
            conn.close()

            session.pop('otp', None)
            session.pop('otp_verified', None)

            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── STUDENT ──────────────────────────────────────────────────────────────────
@app.route('/student')
def student_dash():
    u = cu()
    if not u or u['role'] != 'student':
        return redirect(url_for('login'))

    today    = date.today().strftime('%Y-%m-%d')
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    now      = datetime.now()

    conn = db()

    configs     = qr(conn, "SELECT * FROM mess_config WHERE enabled=1 ORDER BY start_time")
    meal_order  = [c['meal_type'] for c in configs]
    config_dict = {c['meal_type']: c for c in configs}

    menu_rows  = qr(conn, "SELECT * FROM menu WHERE date=%s", (today,))
    today_menu = {r['meal_type']: r for r in menu_rows}

    weekly = {}
    for off in range(7):
        d = (date.today() + timedelta(days=off)).strftime('%Y-%m-%d')
        rows = qr(conn, "SELECT * FROM menu WHERE date=%s", (d,))
        if rows:
            weekly[d] = {r['meal_type']: r for r in rows}

    optin_rows = qr(conn, "SELECT * FROM opt_ins WHERE user_id=%s AND date>=%s", (u['id'], today))
    optins = {(str(o['date']), o['meal_type']): o['status'] for o in optin_rows}

    tmr_rows   = qr(conn, "SELECT meal_type, COUNT(*) as cnt FROM opt_ins WHERE date=%s AND status='in' GROUP BY meal_type", (tomorrow,))
    tmr_counts = {r['meal_type']: r['cnt'] for r in tmr_rows}

    att_rows  = qr(conn, "SELECT meal_type FROM attendance WHERE user_id=%s AND date=%s", (u['id'], today))
    att_today = {a['meal_type'].lower() for a in att_rows}
    att_count = len(att_today)

    missed = []
    for mt in meal_order:
        if mt not in att_today and mt in config_dict:
            cfg = config_dict[mt]
            try:
                end_h, end_m = map(int, str(cfg['end_time']).split(':'))
                meal_end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                if now > meal_end:
                    missed.append(mt)
            except:
                pass

    my_fb = qr(conn, "SELECT * FROM feedback WHERE user_id=%s ORDER BY created_at DESC LIMIT 6", (u['id'],))
    anns  = qr(conn, "SELECT * FROM announcements ORDER BY created_at DESC LIMIT 5")
    txns  = qr(conn, "SELECT * FROM transactions WHERE user_id=%s ORDER BY created_at DESC LIMIT 8", (u['id'],))
    pays  = qr(conn, "SELECT * FROM payments WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (u['id'],))

    attendance_raw = qr(conn, """
    SELECT DATE_FORMAT(date, '%Y-%m-%d') as date,
           LOWER(meal_type) as meal_type,
           cost_charged
    FROM attendance 
    WHERE user_id=%s
    ORDER BY date ASC,
    FIELD(LOWER(meal_type), 'breakfast','lunch','snacks','dinner')
    """, (u['id'],))


    attendance = {}
    grand_total = 0

    for a in attendance_raw:
        d = a['date']

        if d not in attendance:
            attendance[d] = {
                'items': [],
                'total': 0
            }

    # ✅ NOW INSIDE LOOP (CORRECT)
        attendance[d]['items'].append({
            'meal_type': a['meal_type'],
            'cost_charged': float(a['cost_charged'])
        })

        attendance[d]['total'] += float(a['cost_charged'])
        grand_total += float(a['cost_charged'])

    return render_template('student.html',
        att_count=att_count,
        u=u, today=today, tomorrow=tomorrow, now=now,
        today_str=now.strftime('%A, %d %B %Y'),
        configs=configs, config_dict=config_dict, meal_order=meal_order,
        today_menu=today_menu, weekly=weekly,
        optins=optins, tmr_counts=tmr_counts,
        att_today=att_today, missed=missed,
        my_fb=my_fb, anns=anns, txns=txns, pays=pays,
        attendance=attendance,
        grand_total=grand_total,
        is_past_cutoff=is_past_cutoff   # ← THIS FIXES THE JINJA ERROR
    )
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import send_file

@app.route('/download_bill')
def download_bill():
    u = cu()
    if not u or u['role'] != 'student':
        return redirect(url_for('login'))

    conn = db()

    rows = qr(conn, """
        SELECT DATE_FORMAT(date, '%Y-%m-%d') as date,
               LOWER(meal_type) as meal_type,
               cost_charged
        FROM attendance
        WHERE user_id=%s
        ORDER BY date ASC
    """, (u['id'],))

    conn.close()

    # 📄 PDF create
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    elements = []

    # 🔥 HEADER
    elements.append(Paragraph("FeedSmart Monthly Bill", styles['Title']))
    elements.append(Paragraph(f"Name: {u['name']}", styles['Normal']))
    elements.append(Paragraph(f"Roll No: {u['roll_no']}", styles['Normal']))
    elements.append(Paragraph(" ", styles['Normal']))

    # 📊 TABLE
    data = [["Date", "Meal", "Cost"]]
    total = 0

    for r in rows:
        data.append([r['date'], r['meal_type'], f"₹{r['cost_charged']}"])
        total += float(r['cost_charged'])

    data.append(["", "Total", f"₹{total}"])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.green),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (-1,-1), (-1,-1), colors.lightgrey)
    ]))

    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer,
                     as_attachment=True,
                     download_name="monthly_bill.pdf",
                     mimetype='application/pdf')


@app.route('/optin', methods=['POST'])
def optin():
    u = cu()
    if not u:
        return jsonify({'error': 'Not logged in'}), 401
    data      = request.get_json()
    meal_date = data['date']
    meal_type = data['meal_type']
    status    = data['status']

    conn = db()
    cfg = q1(conn, "SELECT * FROM mess_config WHERE meal_type=%s", (meal_type,))
    if cfg and meal_date == date.today().strftime('%Y-%m-%d') and is_past_cutoff(cfg['cutoff_time']):
        conn.close()
        return jsonify({'error': 'Cutoff passed', 'cutoff': True}), 400

    existing = q1(conn, "SELECT id FROM opt_ins WHERE user_id=%s AND date=%s AND meal_type=%s",
                  (u['id'], meal_date, meal_type))
    if existing:
        qx(conn, "UPDATE opt_ins SET status=%s WHERE user_id=%s AND date=%s AND meal_type=%s",
           (status, u['id'], meal_date, meal_type))
    else:
        qx(conn, "INSERT INTO opt_ins(user_id,date,meal_type,status) VALUES(%s,%s,%s,%s)",
           (u['id'], meal_date, meal_type, status))
    conn.commit()

    cnt = q1(conn, "SELECT COUNT(*) as n FROM opt_ins WHERE date=%s AND meal_type=%s AND status='in'",
             (meal_date, meal_type))['n']
    conn.close()
    return jsonify({'success': True, 'count': cnt})

@app.route('/feedback', methods=['POST'])
def feedback():
    u = cu()
    if not u:
        return redirect(url_for('login'))
    conn = db()
    qx(conn, """INSERT INTO feedback(user_id,date,meal_type,rating,taste,quantity,cleanliness,comment)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
       (u['id'], request.form['date'], request.form['meal_type'],
        int(request.form.get('rating', 3)), int(request.form.get('taste', 3)),
        int(request.form.get('quantity', 3)), int(request.form.get('cleanliness', 3)),
        request.form.get('comment', '')))
    conn.commit()
    conn.close()
    flash('Feedback submitted! Thank you 🙏', 'success')
    return redirect(url_for('student_dash'))

@app.route('/pay', methods=['POST'])
def pay():
    u = cu()
    if not u:
        return jsonify({'error': 'Not logged in'}), 401
    data   = request.get_json()
    amount = float(data.get('amount', 0))
    method = data.get('method', 'upi')
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    ref  = 'FS' + uuid.uuid4().hex[:10].upper()
    conn = db()
    qx(conn, "UPDATE users SET mess_balance = mess_balance + %s WHERE id=%s", (amount, u['id']))
    qx(conn, "INSERT INTO transactions(user_id,amount,type,description) VALUES(%s,%s,%s,%s)",
       (u['id'], amount, 'credit', f'Wallet top-up via {method}'))
    qx(conn, "INSERT INTO payments(user_id,amount,method,status,reference) VALUES(%s,%s,%s,%s,%s)",
       (u['id'], amount, method, 'success', ref))
    conn.commit()
    new_bal = float(q1(conn, "SELECT mess_balance FROM users WHERE id=%s", (u['id'],))['mess_balance'])
    conn.close()
    return jsonify({'success': True, 'reference': ref, 'new_balance': new_bal})

# ── ADMIN ─────────────────────────────────────────────────────────────────────
@app.route('/admin')
def admin_dash():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))

    today    = date.today().strftime('%Y-%m-%d')
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    now      = datetime.now()

    conn = db()

    total_students = q1(conn, "SELECT COUNT(*) as n FROM users WHERE role='student'")['n']
    configs     = qr(conn, "SELECT * FROM mess_config WHERE admin_id=%s ORDER BY start_time", (u['id'],))
    config_dict = {c['meal_type']: c for c in configs}

    today_att = {r['meal_type']: r['cnt'] for r in
        qr(conn, "SELECT meal_type, COUNT(*) as cnt FROM attendance WHERE date=%s GROUP BY meal_type", (today,))}
    today_opt = {r['meal_type']: r['cnt'] for r in
        qr(conn, "SELECT meal_type, COUNT(*) as cnt FROM opt_ins WHERE date=%s AND status='in' GROUP BY meal_type", (today,))}
    tmr_opt   = {r['meal_type']: r['cnt'] for r in
        qr(conn, "SELECT meal_type, COUNT(*) as cnt FROM opt_ins WHERE date=%s AND status='in' GROUP BY meal_type", (tomorrow,))}

    rev_row = q1(conn, "SELECT COALESCE(SUM(cost_charged),0) as r FROM attendance WHERE date=%s", (today,))
    revenue = float(rev_row['r']) if rev_row else 0

    weekly = []
    for i in range(6, -1, -1):
        d   = (date.today() - timedelta(days=i)).strftime('%Y-%m-%d')
        cnt = q1(conn, "SELECT COUNT(*) as n FROM attendance WHERE date=%s", (d,))['n']
        weekly.append({'date': d[-5:], 'count': cnt})

    fb_stats  = qr(conn, "SELECT meal_type, ROUND(AVG(rating),1) as ar, ROUND(AVG(taste),1) as at_val, ROUND(AVG(quantity),1) as aq, ROUND(AVG(cleanliness),1) as ac, COUNT(*) as cnt FROM feedback GROUP BY meal_type")
    feedbacks = qr(conn, "SELECT f.*, u.name as sname, u.roll_no FROM feedback f JOIN users u ON f.user_id=u.id ORDER BY f.created_at DESC LIMIT 10")
    att_log   = qr(conn, "SELECT a.*, u.name as sname, u.roll_no FROM attendance a JOIN users u ON a.user_id=u.id WHERE a.date=%s ORDER BY a.scanned_at DESC LIMIT 20", (today,))
    anns      = qr(conn, "SELECT * FROM announcements ORDER BY created_at DESC")
    menus     = qr(conn, "SELECT * FROM menu WHERE date>=%s ORDER BY date, FIELD(meal_type,'breakfast','lunch','snacks','dinner')", (today,))
    students  = qr(conn, "SELECT * FROM users WHERE role='student' ORDER BY name")

    conn.close()

    return render_template('admin.html',
        u=u, today=today, tomorrow=tomorrow, now=now,
        total_students=total_students, configs=configs, config_dict=config_dict,
        today_att=today_att, today_opt=today_opt, tmr_opt=tmr_opt, revenue=revenue,
        weekly=weekly, fb_stats=fb_stats, feedbacks=feedbacks,
        att_log=att_log, anns=anns, menus=menus, students=students)

@app.route('/admin/scan', methods=['POST'])
def scan():
    u = cu()
    if not u or u['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()

    try:
        # Parse QR
        try:
            qd  = json.loads(data['qr_data'])
            uid = int(qd['uid'])
        except:
            return jsonify({'error': 'Invalid QR code'}), 400

        meal_type = data.get('meal_type')
        if not meal_type:
            return jsonify({'error': 'Meal type missing'}), 400

        meal_type = meal_type.lower()
        today = date.today().strftime('%Y-%m-%d')
        conn  = db()

        # Get student
        student = q1(conn, "SELECT * FROM users WHERE id=%s", (uid,))
        if not student:
            conn.close()
            return jsonify({'error': 'Student not found'})

        # Get cost
        cfg  = q1(conn, "SELECT * FROM mess_config WHERE meal_type=%s", (meal_type,))
        cost = float(cfg['cost']) if cfg else 50.0

        user_type = student.get('user_type', 'dayscholar')
        balance = float(student['mess_balance'])

        # Prevent duplicate
        existing = q1(conn, "SELECT id FROM attendance WHERE user_id=%s AND date=%s AND meal_type=%s",
                      (uid, today, meal_type))
        if existing:
            conn.close()
            return jsonify({
                'success': False,
                'duplicate': True,
                'message': f'⚠️ Already scanned — {student["name"]} ({student["roll_no"]})'
            })

        # Balance check ONLY for day scholar
        if user_type == 'dayscholar' and balance < cost:
            conn.close()
            return jsonify({'error': 'Insufficient balance ❌'})

        # Check opt-in
        optin = q1(conn, "SELECT * FROM opt_ins WHERE user_id=%s AND date=%s AND meal_type=%s",
                   (uid, today, meal_type))

        # Insert attendance
        qx(conn, "INSERT INTO attendance(user_id,date,meal_type,cost_charged,scanned_by) VALUES(%s,%s,%s,%s,%s)",
           (uid, today, meal_type, cost, u['id']))

        # Deduct / add bill
        if user_type == 'dayscholar':
            qx(conn, "UPDATE users SET mess_balance = mess_balance - %s WHERE id=%s",
               (cost, uid))
        else:
            qx(conn, "UPDATE users SET monthly_bill = monthly_bill + %s WHERE id=%s",
               (cost, uid))

        # Add transaction
        qx(conn, "INSERT INTO transactions(user_id,amount,type,description) VALUES(%s,%s,%s,%s)",
           (uid, cost, 'debit', f'{meal_type.capitalize()} on {today}'))

        conn.commit()

        new_bal = float(q1(conn, "SELECT mess_balance FROM users WHERE id=%s", (uid,))['mess_balance'])
        conn.close()

        opted = 'opted-in ✓' if optin and optin['status'] == 'in' else 'walk-in'

        return jsonify({
            'success': True,
            'message': f'✅ {student["name"]} ({student["roll_no"]}) — {opted}',
            'cost': cost,
            'new_balance': new_bal,
            'user_type': user_type
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400
@app.route('/admin/config', methods=['POST'])
def admin_config():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))
    conn = db()
    try:
        for mt in ['breakfast', 'lunch', 'snacks', 'dinner']:
            enabled = 1 if request.form.get(f'{mt}_enabled') else 0
            start   = request.form.get(f'{mt}_start', '08:00')
            end     = request.form.get(f'{mt}_end',   '09:00')
            cutoff  = request.form.get(f'{mt}_cutoff','07:00')
            cost    = float(request.form.get(f'{mt}_cost', 0))
            desc    = request.form.get(f'{mt}_desc', '')
            existing = q1(conn, "SELECT id FROM mess_config WHERE admin_id=%s AND meal_type=%s", (u['id'], mt))
            if existing:
                qx(conn, """UPDATE mess_config SET enabled=%s,start_time=%s,end_time=%s,
                            cutoff_time=%s,cost=%s,description=%s WHERE admin_id=%s AND meal_type=%s""",
                   (enabled, start, end, cutoff, cost, desc, u['id'], mt))
            else:
                qx(conn, """INSERT INTO mess_config(admin_id,meal_type,enabled,start_time,end_time,cutoff_time,cost,description)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (u['id'], mt, enabled, start, end, cutoff, cost, desc))
        conn.commit()
        flash('Meal configuration saved! ✅', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    conn.close()
    return redirect(url_for('admin_dash'))

@app.route('/admin/menu', methods=['POST'])
def admin_menu():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))
    action = request.form.get('action')
    conn = db()
    try:
        if action == 'add':
            existing = q1(conn, "SELECT id FROM menu WHERE date=%s AND meal_type=%s",
                          (request.form['date'], request.form['meal_type']))
            if existing:
                qx(conn, "UPDATE menu SET items=%s WHERE date=%s AND meal_type=%s",
                   (request.form['items'], request.form['date'], request.form['meal_type']))
            else:
                qx(conn, "INSERT INTO menu(date,meal_type,items,admin_id) VALUES(%s,%s,%s,%s)",
                   (request.form['date'], request.form['meal_type'], request.form['items'], u['id']))
            flash('Menu updated! ✅', 'success')
        elif action == 'delete':
            qx(conn, "DELETE FROM menu WHERE id=%s", (request.form['menu_id'],))
            flash('Menu deleted! ✅', 'success')
        conn.commit()
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    conn.close()
    return redirect(url_for('admin_dash'))

@app.route('/admin/announce', methods=['POST'])
def admin_announce():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))
    conn = db()
    qx(conn, "INSERT INTO announcements(title,body,priority,created_by) VALUES(%s,%s,%s,%s)",
       (request.form['title'], request.form['body'], request.form.get('priority', 'normal'), u['id']))
    conn.commit()
    conn.close()
    flash('Announcement posted! ✅', 'success')
    return redirect(url_for('admin_dash'))

@app.route('/admin/announce/delete', methods=['POST'])
def del_announce():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))
    conn = db()
    qx(conn, "DELETE FROM announcements WHERE id=%s", (request.form['ann_id'],))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dash'))

@app.route('/admin/topup', methods=['POST'])
def topup():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))
    uid    = int(request.form['user_id'])
    amount = float(request.form['amount'])
    conn = db()
    qx(conn, "UPDATE users SET mess_balance = mess_balance + %s WHERE id=%s", (amount, uid))
    qx(conn, "INSERT INTO transactions(user_id,amount,type,description) VALUES(%s,%s,%s,%s)",
       (uid, amount, 'credit', 'Admin top-up'))
    conn.commit()
    conn.close()
    flash(f'₹{amount:.0f} added successfully! ✅', 'success')
    return redirect(url_for('admin_dash'))

@app.route('/admin/make-hosteller', methods=['POST'])
def make_hosteller():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))

    uid = int(request.form['user_id'])

    conn = db()
    qx(conn, "UPDATE users SET user_type='hosteller' WHERE id=%s", (uid,))
    conn.commit()
    conn.close()

    flash('User converted to hosteller ✅', 'success')
    return redirect(url_for('admin_dash'))

from datetime import datetime

def reset_monthly_bills():
    conn = db()

    users = qr(conn, "SELECT id, monthly_bill FROM users WHERE user_type='hosteller'")

    current_month = datetime.now().strftime('%Y-%m')

    for u in users:
        if u['monthly_bill'] > 0:
            qx(conn, """
                INSERT INTO monthly_bills(user_id, month, total)
                VALUES (%s, %s, %s)
            """, (u['id'], current_month, u['monthly_bill']))

    # reset all
    qx(conn, "UPDATE users SET monthly_bill = 0 WHERE user_type='hosteller'")

    conn.commit()
    conn.close()
@app.route('/admin/delete_student', methods=['POST'])
def delete_student():
    u = cu()
    if not u or u['role'] != 'admin':
        return redirect(url_for('login'))

    user_id = request.form.get('user_id')

    conn = db()

    try:
        # 🔥 delete related data FIRST
        qx(conn, "DELETE FROM attendance WHERE user_id=%s", (user_id,))
        qx(conn, "DELETE FROM opt_ins WHERE user_id=%s", (user_id,))
        qx(conn, "DELETE FROM transactions WHERE user_id=%s", (user_id,))
        qx(conn, "DELETE FROM feedback WHERE user_id=%s", (user_id,))
        qx(conn, "DELETE FROM payments WHERE user_id=%s", (user_id,))

        # 🔥 finally delete user
        qx(conn, "DELETE FROM users WHERE id=%s", (user_id,))

        conn.commit()
        flash("Student deleted successfully", "success")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    finally:
        conn.close()

    return redirect(url_for('admin_dash'))

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    otp = str(random.randint(100000, 999999))

    session['otp'] = otp
    session['otp_email'] = email

    print("OTP:", otp)  # 🔥 use this

    return jsonify({'msg': 'OTP generated'})

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')

    if user_otp == session.get('otp'):
        session['otp_verified'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})


app = Flask(__name__)
app.secret_key = 'feedsmart_v3_ultra_2026'

init_db()