from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import hashlib
import secrets
import random
import pymysql
from pymysql import Error
import os
import datetime
from datetime import timedelta
from functools import wraps

# ============================================
# 🚀 FLASK APP INITIALIZATION
# ============================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=7)

# ============================================
# 📊 DATABASE CONFIGURATION
# ============================================

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # XAMPP default is empty
    'database': 'vubapay',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    """Create database connection"""
    try:
        conn = pymysql.connect(**db_config)
        return conn
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None

# ============================================
# 🔒 HEADERS & SECURITY
# ============================================

@app.after_request
def add_header(response):
    """Add headers to prevent caching issues"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ============================================
# 🏠 MAIN ROUTES
# ============================================

@app.route('/')
def index():
    if session.get('user_type') == 'provider' and session.get('user_id'):
        return redirect(url_for('provider_dashboard'))
    if session.get('user_type') == 'client' and session.get('user_id'):
        return redirect(url_for('client_dashboard'))
    return render_template('index.html')

@app.route('/provider-dashboard')
def provider_dashboard():
    if session.get('user_type') == 'provider' and session.get('user_id'):
        return render_template('provider_dashboard.html')
    return redirect(url_for('index'))

@app.route('/client-dashboard')
def client_dashboard():
    if session.get('user_type') == 'client' and session.get('user_id'):
        return render_template('client_dashboard.html')
    return redirect(url_for('index'))

# ============================================
# 👑 ADMIN ROUTES
# ============================================

@app.route('/admin-login')
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/admin-dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login_page'))
    return render_template('admin_dashboard.html')

# ============================================
# 📝 API ROUTES - AUTHENTICATION
# ============================================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_type = data.get('user_type')
        names = data.get('names')
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password')
        
        if not names or not email or not phone or not password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        if user_type == 'client':
            cursor.execute("SELECT ID FROM clients WHERE EMAIL = %s OR PHONE_NUMBER = %s", (email, phone))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Email or phone already exists'}), 400
            
            cursor.execute("""
                INSERT INTO clients (NAMES, EMAIL, PHONE_NUMBER, PASSWORD, WALLET_BALANCE)
                VALUES (%s, %s, %s, %s, 25000)
            """, (names, email, phone, hashed_password))
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': '✨ Client account created successfully!'})
        
        else:
            cursor.execute("SELECT ID FROM service_providers WHERE EMAIL = %s OR PHONE_NUMBER = %s", (email, phone))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Email or phone already exists'}), 400
            
            payment_code = random.randint(100000, 999999)
            plate_number = data.get('plate_number', '')
            
            if not plate_number:
                return jsonify({'success': False, 'message': 'Plate number is required'}), 400
            
            qr_data = f"tel:*182*8*1*{payment_code}%23"
            
            cursor.execute("""
                INSERT INTO service_providers 
                (NAMES, EMAIL, PHONE_NUMBER, PASSWORD, PLATE_NUMBER, PAYMENT_CODE, HELMET_QR_CODE, WALLET_BALANCE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            """, (names, email, phone, hashed_password, plate_number, payment_code, qr_data))
            
            provider_id = cursor.lastrowid
            conn.commit()
            
            sticker_serial = f"VUB-{str(provider_id).zfill(4)}"
            cursor.execute("""
                INSERT INTO qr_codes (PROVIDER_ID, QR_DATA, STICKER_SERIAL)
                VALUES (%s, %s, %s)
            """, (provider_id, qr_data, sticker_serial))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'🏍️ Rider account created! Payment code: {payment_code}',
                'payment_code': payment_code
            })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        user_type = data.get('user_type')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        if user_type == 'client':
            cursor.execute("""
                SELECT ID, NAMES, EMAIL, PHONE_NUMBER, WALLET_BALANCE 
                FROM clients 
                WHERE (EMAIL = %s OR PHONE_NUMBER = %s) AND PASSWORD = %s AND IS_ACTIVE = 1
            """, (email, email, hashed_password))
        else:
            cursor.execute("""
                SELECT ID, NAMES, EMAIL, PHONE_NUMBER, PLATE_NUMBER, PAYMENT_CODE, WALLET_BALANCE 
                FROM service_providers 
                WHERE (EMAIL = %s OR PHONE_NUMBER = %s) AND PASSWORD = %s AND IS_ACTIVE = 1
            """, (email, email, hashed_password))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            session.clear()
            session.permanent = True
            session['user_id'] = user['ID']
            session['user_type'] = user_type
            session['user_name'] = user['NAMES']
            
            return jsonify({
                'success': True,
                'redirect': '/provider-dashboard' if user_type == 'provider' else '/client-dashboard'
            })
        
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# 📊 API ROUTES - DASHBOARD DATA
# ============================================

@app.route('/api/get-provider-data', methods=['GET'])
def get_provider_data():
    if not session.get('user_id') or session.get('user_type') != 'provider':
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT ID, NAMES, EMAIL, PHONE_NUMBER, PLATE_NUMBER, PAYMENT_CODE, 
                   HELMET_QR_CODE, WALLET_BALANCE, PAYMENT_TYPE, MOMO_NUMBER
            FROM service_providers 
            WHERE ID = %s AND IS_ACTIVE = 1
        """, (session['user_id'],))
        provider = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if provider:
            return jsonify({'success': True, 'provider': provider})
        return jsonify({'success': False, 'message': 'Provider not found'}), 404
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get-client-data', methods=['GET'])
def get_client_data():
    if not session.get('user_id') or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT ID, NAMES, EMAIL, PHONE_NUMBER, WALLET_BALANCE 
            FROM clients 
            WHERE ID = %s AND IS_ACTIVE = 1
        """, (session['user_id'],))
        client = cursor.fetchone()
        
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE CLIENT_ID = %s 
            ORDER BY CREATED_AT DESC 
            LIMIT 20
        """, (session['user_id'],))
        transactions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        formatted_transactions = []
        for t in transactions:
            rider_name = "Rider"
            if t.get('PROVIDER_ID'):
                conn2 = get_db_connection()
                cursor2 = conn2.cursor(pymysql.cursors.DictCursor)
                cursor2.execute("SELECT NAMES FROM service_providers WHERE ID = %s", (t['PROVIDER_ID'],))
                rider = cursor2.fetchone()
                if rider:
                    rider_name = rider['NAMES']
                cursor2.close()
                conn2.close()
            
            formatted_transactions.append({
                'riderName': rider_name,
                'amount': float(t['AMOUNT']),
                'method': t['PAYMENT_METHOD'],
                'date': t['CREATED_AT'].strftime('%Y-%m-%d %H:%M') if t['CREATED_AT'] else '',
                'type': 'payment'
            })
        
        return jsonify({
            'success': True,
            'client': client,
            'transactions': formatted_transactions
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/rider/<payment_code>', methods=['GET'])
def get_rider_by_payment_code(payment_code):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT ID, NAMES, PLATE_NUMBER, PHONE_NUMBER, PAYMENT_CODE, PAYMENT_TYPE, MOMO_NUMBER
            FROM service_providers 
            WHERE (PAYMENT_CODE = %s OR MOMO_NUMBER = %s) AND IS_ACTIVE = 1
        """, (payment_code, payment_code))
        rider = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if rider:
            return jsonify({'success': True, 'rider': rider})
        return jsonify({'success': False, 'message': 'Rider not found'}), 404
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# 💰 API ROUTES - PAYMENTS
# ============================================

@app.route('/api/make-payment', methods=['POST'])
def make_payment():
    if not session.get('user_id') or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.json
        payment_code = data.get('payment_code')
        amount = float(data.get('amount'))
        network = data.get('network')
        
        if not payment_code or not amount:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        if amount < 100:
            return jsonify({'success': False, 'message': 'Minimum payment is 100 RWF'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT ID, NAMES, WALLET_BALANCE FROM clients WHERE ID = %s", (session['user_id'],))
        client = cursor.fetchone()
        
        if not client:
            return jsonify({'success': False, 'message': 'Client not found'}), 404
        
        if client['WALLET_BALANCE'] < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
        
        cursor.execute("""
            SELECT ID, NAMES, PAYMENT_CODE, MOMO_NUMBER, PAYMENT_TYPE, WALLET_BALANCE 
            FROM service_providers 
            WHERE (PAYMENT_CODE = %s OR MOMO_NUMBER = %s) AND IS_ACTIVE = 1
        """, (payment_code, payment_code))
        rider = cursor.fetchone()
        
        if not rider:
            return jsonify({'success': False, 'message': 'Invalid QR code'}), 404
        
        cursor.execute("SELECT ID FROM service_providers WHERE PAYMENT_CODE = 556688")
        master = cursor.fetchone()
        
        fee = amount * 0.005
        net_amount = amount - fee
        
        transaction_id = f"VUB{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        conn.begin()
        
        cursor.execute("UPDATE clients SET WALLET_BALANCE = WALLET_BALANCE - %s WHERE ID = %s", (amount, client['ID']))
        cursor.execute("UPDATE service_providers SET WALLET_BALANCE = WALLET_BALANCE + %s WHERE ID = %s", (net_amount, rider['ID']))
        
        if master:
            cursor.execute("UPDATE service_providers SET WALLET_BALANCE = WALLET_BALANCE + %s WHERE ID = %s", (fee, master['ID']))
        
        cursor.execute("""
            INSERT INTO transactions (TRANSACTION_ID, CLIENT_ID, PROVIDER_ID, AMOUNT, FEE_AMOUNT, NET_AMOUNT, PAYMENT_METHOD, STATUS)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED')
        """, (transaction_id, client['ID'], rider['ID'], amount, fee, net_amount, network))
        
        conn.commit()
        
        cursor.execute("SELECT WALLET_BALANCE FROM clients WHERE ID = %s", (client['ID'],))
        updated_client = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ Payment of {amount:,.0f} RWF sent to {rider["NAMES"]}',
            'transaction_id': transaction_id,
            'amount': amount,
            'fee': fee,
            'net_amount': net_amount,
            'new_balance': updated_client['WALLET_BALANCE']
        })
    
    except Exception as e:
        print(f"❌ Payment error: {e}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update-payment-code', methods=['POST'])
def update_payment_code():
    if not session.get('user_id') or session.get('user_type') != 'provider':
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.json
        new_payment_code = data.get('payment_code')
        
        if not new_payment_code or len(str(new_payment_code)) != 6:
            return jsonify({'success': False, 'message': 'Payment code must be exactly 6 digits'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT ID FROM service_providers WHERE PAYMENT_CODE = %s AND ID != %s", 
                      (new_payment_code, session['user_id']))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'This payment code is already taken'}), 400
        
        new_qr_data = f"tel:*182*8*1*{new_payment_code}%23"
        
        cursor.execute("""
            UPDATE service_providers 
            SET PAYMENT_CODE = %s, HELMET_QR_CODE = %s, PAYMENT_TYPE = 'momocode', MOMO_NUMBER = NULL
            WHERE ID = %s
        """, (new_payment_code, new_qr_data, session['user_id']))
        
        cursor.execute("""
            UPDATE qr_codes 
            SET QR_DATA = %s 
            WHERE PROVIDER_ID = %s
        """, (new_qr_data, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '✅ Payment code updated successfully!',
            'new_payment_code': new_payment_code,
            'new_qr_data': new_qr_data
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# 🎟️ QR FEE PROCESSING (UPDATED)
# ============================================

@app.route('/api/process-qr-fee', methods=['POST'])
def process_qr_fee():
    try:
        data = request.json
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        payment_type = data.get('payment_type')
        payment_code = data.get('payment_code')
        mobile_number = data.get('mobile_number')
        master_phone = data.get('master_phone', '0783473932')
        
        if amount != 200:
            return jsonify({'success': False, 'message': 'Amount must be 200 RWF'}), 400
        
        # Process payment to master account (0783473932)
        # In production, integrate with MTN/Airtel API here
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # ✅ Record QR payment in qr_payments table (UPDATED SECTION)
        cursor.execute("""
            INSERT INTO qr_payments (provider_id, amount, payment_method, payment_type, payment_code, momo_number, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'COMPLETED')
        """, (session.get('user_id'), amount, payment_method, payment_type, payment_code, mobile_number))
        
        # Also record in transactions table for tracking
        transaction_id = f"QRFEE{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        cursor.execute("""
            INSERT INTO transactions (TRANSACTION_ID, AMOUNT, PAYMENT_METHOD, STATUS, CREATED_AT)
            VALUES (%s, %s, %s, 'COMPLETED', NOW())
        """, (transaction_id, amount, payment_method))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '✅ Payment successful! QR code generated.',
            'payment_code': payment_code,
            'payment_type': payment_type
        })
    
    except Exception as e:
        print(f"❌ QR fee processing error: {e}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ⚙️ API ROUTES - SETTINGS & AUTH
# ============================================

@app.route('/api/save-payment-settings', methods=['POST'])
def save_payment_settings():
    if not session.get('user_id') or session.get('user_type') != 'provider':
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.json
        payment_type = data.get('payment_type')
        payment_code = data.get('payment_code')
        mobile_number = data.get('mobile_number')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        if payment_type == 'momocode':
            cursor.execute("""
                UPDATE service_providers 
                SET PAYMENT_TYPE = 'momocode', PAYMENT_CODE = %s, MOMO_NUMBER = NULL,
                    HELMET_QR_CODE = %s
                WHERE ID = %s
            """, (payment_code, f"tel:*182*8*1*{payment_code}%23", session['user_id']))
        else:
            cursor.execute("""
                UPDATE service_providers 
                SET PAYMENT_TYPE = 'momo_number', MOMO_NUMBER = %s, PAYMENT_CODE = NULL,
                    HELMET_QR_CODE = %s
                WHERE ID = %s
            """, (mobile_number, f"tel:*182*1*1*{mobile_number}%23", session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '✅ Payment settings saved!'})
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if session.get('user_id'):
        return jsonify({
            'logged_in': True, 
            'user_type': session.get('user_type'),
            'user_name': session.get('user_name')
        })
    return jsonify({'logged_in': False})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# ============================================
# 👑 ADMIN API ROUTES
# ============================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT ID, NAMES, EMAIL, PHONE_NUMBER, ROLE, IS_ACTIVE 
            FROM admins 
            WHERE EMAIL = %s AND PASSWORD = %s AND IS_ACTIVE = 1
        """, (email, hashed_password))
        
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin:
            session.clear()
            session.permanent = True
            session['admin_id'] = admin['ID']
            session['admin_name'] = admin['NAMES']
            session['admin_role'] = admin['ROLE']
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE admins SET LAST_LOGIN = NOW() WHERE ID = %s", (admin['ID'],))
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'redirect': '/admin-dashboard'})
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    except Exception as e:
        print(f"❌ Admin login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT COUNT(*) as total FROM service_providers WHERE IS_ACTIVE = 1")
        total_riders = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM clients WHERE IS_ACTIVE = 1")
        total_clients = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM transactions")
        total_transactions = cursor.fetchone()['total']
        
        cursor.execute("SELECT SUM(AMOUNT) as total FROM transactions WHERE STATUS = 'COMPLETED'")
        total_volume = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT SUM(FEE_AMOUNT) as total_fees FROM transactions")
        total_fees = cursor.fetchone()['total_fees'] or 0
        
        cursor.execute("SELECT COUNT(*) as total, SUM(amount) as total_amount FROM qr_payments WHERE status = 'COMPLETED'")
        qr_stats = cursor.fetchone()
        total_qr_payments = qr_stats['total'] or 0
        
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as qr_count
            FROM qr_payments
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """)
        daily_stats = cursor.fetchall()
        
        cursor.execute("""
            SELECT t.TRANSACTION_ID, t.AMOUNT, t.FEE_AMOUNT, t.PAYMENT_METHOD, 
                   t.STATUS, t.CREATED_AT,
                   c.NAMES as client_name, p.NAMES as provider_name
            FROM transactions t
            LEFT JOIN clients c ON t.CLIENT_ID = c.ID
            LEFT JOIN service_providers p ON t.PROVIDER_ID = p.ID
            ORDER BY t.CREATED_AT DESC
            LIMIT 20
        """)
        recent_transactions = cursor.fetchall()
        
        cursor.execute("""
            SELECT NAMES, PLATE_NUMBER, PAYMENT_CODE, WALLET_BALANCE
            FROM service_providers 
            WHERE IS_ACTIVE = 1
            ORDER BY WALLET_BALANCE DESC
            LIMIT 10
        """)
        top_riders = cursor.fetchall()
        
        cursor.execute("""
            SELECT NAMES, PHONE_NUMBER, WALLET_BALANCE
            FROM clients 
            WHERE IS_ACTIVE = 1
            ORDER BY WALLET_BALANCE DESC
            LIMIT 10
        """)
        top_clients = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_riders': total_riders,
                'total_clients': total_clients,
                'total_transactions': total_transactions,
                'total_volume': float(total_volume),
                'total_fees': float(total_fees),
                'total_qr_payments': total_qr_payments,
                'qr_revenue': float(qr_stats['total_amount'] or 0)
            },
            'recent_transactions': recent_transactions,
            'top_riders': top_riders,
            'top_clients': top_clients,
            'daily_stats': daily_stats
        })
    
    except Exception as e:
        print(f"❌ Admin stats error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/riders', methods=['GET'])
def admin_riders():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT ID, NAMES, EMAIL, PHONE_NUMBER, PLATE_NUMBER, 
                   PAYMENT_CODE, MOMO_NUMBER, PAYMENT_TYPE, HELMET_QR_CODE,
                   WALLET_BALANCE, IS_ACTIVE, CREATED_AT
            FROM service_providers
            ORDER BY CREATED_AT DESC
        """)
        riders = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'riders': riders})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/clients', methods=['GET'])
def admin_clients():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT ID, NAMES, EMAIL, PHONE_NUMBER, WALLET_BALANCE, IS_ACTIVE, CREATED_AT,
                   (SELECT COUNT(*) FROM transactions WHERE CLIENT_ID = clients.ID) as total_rides,
                   (SELECT SUM(AMOUNT) FROM transactions WHERE CLIENT_ID = clients.ID) as total_spent
            FROM clients
            ORDER BY CREATED_AT DESC
        """)
        clients = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'clients': clients})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/qr-payments', methods=['GET'])
def admin_qr_payments():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT qp.*, sp.NAMES as rider_name, sp.PHONE_NUMBER
            FROM qr_payments qp
            LEFT JOIN service_providers sp ON qp.PROVIDER_ID = sp.ID
            ORDER BY qp.CREATED_AT DESC
        """)
        payments = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'payments': payments})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/toggle-rider/<int:rider_id>', methods=['POST'])
def admin_toggle_rider(rider_id):
    if 'admin_id' not in session or session.get('admin_role') not in ['super_admin', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT IS_ACTIVE FROM service_providers WHERE ID = %s", (rider_id,))
        current = cursor.fetchone()
        
        new_status = 0 if current[0] == 1 else 1
        cursor.execute("UPDATE service_providers SET IS_ACTIVE = %s WHERE ID = %s", (new_status, rider_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'is_active': new_status})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/toggle-client/<int:client_id>', methods=['POST'])
def admin_toggle_client(client_id):
    if 'admin_id' not in session or session.get('admin_role') not in ['super_admin', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT IS_ACTIVE FROM clients WHERE ID = %s", (client_id,))
        current = cursor.fetchone()
        
        new_status = 0 if current[0] == 1 else 1
        cursor.execute("UPDATE clients SET IS_ACTIVE = %s WHERE ID = %s", (new_status, client_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'is_active': new_status})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/delete-rider/<int:rider_id>', methods=['DELETE'])
def admin_delete_rider(rider_id):
    if 'admin_id' not in session or session.get('admin_role') != 'super_admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM service_providers WHERE ID = %s", (rider_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Rider deleted successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/admin/check-auth', methods=['GET'])
def admin_check_auth():
    if 'admin_id' in session:
        return jsonify({'logged_in': True, 'admin_name': session.get('admin_name'), 'admin_role': session.get('admin_role')})
    return jsonify({'logged_in': False})

@app.route('/api/admin/register', methods=['POST'])
def admin_register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password')
        role = data.get('role', 'admin')
        
        if not name or not email or not phone or not password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT ID FROM admins WHERE EMAIL = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        
        cursor.execute("""
            INSERT INTO admins (NAMES, EMAIL, PHONE_NUMBER, PASSWORD, ROLE, IS_ACTIVE)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (name, email, phone, hashed_password, role))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'✅ Admin account created! Role: {role}'})
    
    except Exception as e:
        print(f"❌ Admin register error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/send-otp', methods=['POST'])
def admin_send_otp():
    try:
        data = request.json
        email = data.get('email')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT ID, NAMES FROM admins WHERE EMAIL = %s", (email,))
        admin = cursor.fetchone()
        
        if not admin:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Email not found'}), 404
        
        otp = f"{random.randint(100000, 999999)}"
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_otp (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL,
                otp VARCHAR(6) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("DELETE FROM admin_otp WHERE email = %s", (email,))
        
        expires_at = datetime.datetime.now() + datetime.timedelta(minutes=2)
        cursor.execute("""
            INSERT INTO admin_otp (email, otp, expires_at)
            VALUES (%s, %s, %s)
        """, (email, otp, expires_at))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"📧 OTP for {email}: {otp}")
        
        return jsonify({'success': True, 'message': 'OTP sent to your email'})
    
    except Exception as e:
        print(f"❌ Send OTP error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/verify-otp', methods=['POST'])
def admin_verify_otp():
    try:
        data = request.json
        email = data.get('email')
        otp = data.get('otp')
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT * FROM admin_otp 
            WHERE email = %s AND otp = %s AND expires_at > NOW()
        """, (email, otp))
        
        otp_record = cursor.fetchone()
        
        if not otp_record:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid or expired OTP'}), 400
        
        cursor.execute("DELETE FROM admin_otp WHERE email = %s", (email,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'OTP verified successfully'})
    
    except Exception as e:
        print(f"❌ Verify OTP error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/reset-password', methods=['POST'])
def admin_reset_password():
    try:
        data = request.json
        email = data.get('email')
        new_password = data.get('new_password')
        
        if not email or not new_password:
            return jsonify({'success': False, 'message': 'Email and new password required'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE admins SET PASSWORD = %s WHERE EMAIL = %s", (hashed_password, email))
        conn.commit()
        
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        
        if affected > 0:
            return jsonify({'success': True, 'message': '✅ Password reset successfully'})
        else:
            return jsonify({'success': False, 'message': 'Email not found'}), 404
    
    except Exception as e:
        print(f"❌ Reset password error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# 🚀 SERVER STARTUP
# ============================================

if not os.path.exists('templates'):
    os.makedirs('templates')
    print("✅ Created templates folder")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 VUBA PAY SERVER")
    print("="*60)
    print("🌐 Starting server at: http://localhost:5000")
    print("📱 Press CTRL+C to stop")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)