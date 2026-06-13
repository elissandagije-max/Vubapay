from flask import Flask, request, jsonify, render_template, session
import hashlib
import secrets
import random
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Simple in-memory storage (replace with MySQL later)
users = {
    'clients': {},
    'providers': {}
}

# Temporary storage for transactions
transactions = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        user_type = data.get('user_type')  # 'client' or 'provider'
        
        # Hash password for comparison
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check in memory storage
        if user_type == 'client':
            users_data = users['clients']
        else:
            users_data = users['providers']
        
        for user_id, user in users_data.items():
            if user.get('email') == email and user.get('password') == hashed_password:
                # Generate session token
                token = secrets.token_hex(32)
                session['user_id'] = user_id
                session['user_type'] = user_type
                session['token'] = token
                
                return jsonify({
                    'success': True,
                    'token': token,
                    'user': {
                        'id': user_id,
                        'name': user.get('names'),
                        'email': user.get('email'),
                        'phone': user.get('phone')
                    }
                })
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_type = data.get('user_type')
        names = data.get('names')
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password')
        
        # Hash password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check if email already exists
        existing_users = users['clients'] if user_type == 'client' else users['providers']
        for user in existing_users.values():
            if user.get('email') == email:
                return jsonify({'success': False, 'message': 'Email already exists'}), 400
        
        # Generate unique ID
        user_id = str(uuid.uuid4())[:8]
        
        if user_type == 'client':
            users['clients'][user_id] = {
                'id': user_id,
                'names': names,
                'email': email,
                'phone': phone,
                'password': hashed_password,
                'wallet_balance': 25000.00,
                'created_at': datetime.now().isoformat()
            }
            return jsonify({
                'success': True,
                'message': 'Client account created successfully',
                'user_id': user_id
            })
        
        else:  # provider
            # Generate payment code for QR
            payment_code = random.randint(100000, 999999)
            plate_number = data.get('plate_number')
            
            users['providers'][user_id] = {
                'id': user_id,
                'names': names,
                'email': email,
                'phone': phone,
                'password': hashed_password,
                'plate_number': plate_number,
                'payment_code': payment_code,
                'wallet_balance': 0.00,
                'qr_data': f"tel:*182*8*1*{payment_code}%23",
                'created_at': datetime.now().isoformat()
            }
            
            return jsonify({
                'success': True,
                'message': 'Rider account created successfully',
                'payment_code': payment_code,
                'qr_data': f"tel:*182*8*1*{payment_code}%23",
                'user_id': user_id
            })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/verify-qr', methods=['POST'])
def verify_qr():
    try:
        data = request.json
        payment_code = int(data.get('payment_code'))
        
        # Find provider with this payment code
        for provider_id, provider in users['providers'].items():
            if provider.get('payment_code') == payment_code:
                return jsonify({
                    'success': True,
                    'provider': {
                        'id': provider_id,
                        'names': provider.get('names'),
                        'plate_number': provider.get('plate_number'),
                        'phone': provider.get('phone')
                    }
                })
        
        return jsonify({'success': False, 'message': 'Invalid QR code'}), 404
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/make-payment', methods=['POST'])
def make_payment():
    try:
        data = request.json
        client_id = data.get('client_id')
        provider_id = data.get('provider_id')
        amount = float(data.get('amount'))
        payment_method = data.get('payment_method', 'QR_SCAN')
        
        # Check if client exists and has balance
        client = users['clients'].get(client_id)
        if not client:
            return jsonify({'success': False, 'message': 'Client not found'}), 404
        
        if client.get('wallet_balance', 0) < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
        
        # Check if provider exists
        provider = users['providers'].get(provider_id)
        if not provider:
            return jsonify({'success': False, 'message': 'Provider not found'}), 404
        
        # Process payment
        client['wallet_balance'] -= amount
        provider['wallet_balance'] += amount
        
        # Generate transaction ID
        transaction_id = str(uuid.uuid4())[:8].upper()
        
        # Record transaction
        transaction = {
            'id': transaction_id,
            'client_id': client_id,
            'provider_id': provider_id,
            'amount': amount,
            'payment_method': payment_method,
            'status': 'COMPLETED',
            'created_at': datetime.now().isoformat()
        }
        transactions.append(transaction)
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'amount': amount,
            'new_balance': client['wallet_balance']
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get-balance/<user_id>', methods=['GET'])
def get_balance(user_id):
    try:
        # Check if client or provider
        if user_id in users['clients']:
            user = users['clients'][user_id]
            user_type = 'client'
        elif user_id in users['providers']:
            user = users['providers'][user_id]
            user_type = 'provider'
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'user_type': user_type,
            'balance': user.get('wallet_balance', 0)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get-transactions/<user_id>', methods=['GET'])
def get_transactions(user_id):
    try:
        user_transactions = []
        for t in transactions:
            if t['client_id'] == user_id or t['provider_id'] == user_id:
                user_transactions.append(t)
        
        return jsonify({
            'success': True,
            'transactions': user_transactions
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 VubaPay Server Starting...")
    print("="*50)
    print("📱 Server URL: http://localhost:5000")
    print("📋 API Endpoints:")
    print("   POST /api/login - Login user")
    print("   POST /api/register - Register user")
    print("   POST /api/verify-qr - Verify QR code")
    print("   POST /api/make-payment - Make payment")
    print("   GET /api/get-balance/<user_id> - Get balance")
    print("   GET /api/get-transactions/<user_id> - Get transactions")
    print("="*50)
    print("\n💡 Tip: Make sure you have a 'templates' folder with index.html")
    print("="*50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)