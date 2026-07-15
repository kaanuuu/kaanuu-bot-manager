from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'kaanuu-super-secret-key-2024'

# Create directories
os.makedirs('instance', exist_ok=True)
os.makedirs('sessions', exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

# ============ DATABASE ============
def get_db():
    conn = sqlite3.connect('instance/kaanuu.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        plan TEXT DEFAULT 'free',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Bots table
    c.execute('''CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        login_type TEXT DEFAULT 'bot_token',
        bot_token TEXT,
        api_id TEXT,
        api_hash TEXT,
        phone_number TEXT,
        bot_name TEXT NOT NULL,
        bot_username TEXT,
        status TEXT DEFAULT 'stopped',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )''')
    
    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        message_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
    )''')
    
    # Active users table
    c.execute('''CREATE TABLE IF NOT EXISTS active_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        target_user_id TEXT NOT NULL,
        target_username TEXT,
        chat_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
    )''')
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL UNIQUE,
        auto_delete_enabled INTEGER DEFAULT 0,
        auto_delete_time INTEGER DEFAULT 30,
        anti_delete_enabled INTEGER DEFAULT 0,
        anti_spam INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
    )''')
    
    # Deleted users table
    c.execute('''CREATE TABLE IF NOT EXISTS deleted_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        target_user_id TEXT NOT NULL,
        chat_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
    )''')
    
    # Default admin: admin/admin123
    c.execute("""INSERT OR IGNORE INTO users (username, email, password, is_admin) 
                 VALUES ('admin', 'admin@kaanuu.com', 'pbkdf2:sha256:260000$eH9j0VjL$f4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5', 1)""")
    
    conn.commit()
    conn.close()

init_db()

# ============ USER CLASS ============
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.is_admin = user_data.get('is_admin', False)
        self.plan = user_data.get('plan', 'free')
        self.created_at = user_data.get('created_at')

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user)
    return None

# ============ ROUTES ============
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (current_user.id,))
    total_bots = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ? AND status = 'running'", (current_user.id,))
    active_bots = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)", (current_user.id,))
    total_msgs = c.fetchone()['count']
    conn.close()
    stats = {'total_bots': total_bots, 'active_bots': active_bots, 'total_messages': total_msgs, 'active_users': 0}
    return render_template('dashboard.html', stats=stats, user=current_user)

@app.route('/bots')
@login_required
def bots():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (current_user.id,))
    bots = c.fetchall()
    conn.close()
    return render_template('bots.html', bots=bots, user=current_user)

@app.route('/commands')
@login_required
def commands():
    return render_template('commands.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (current_user.id,))
    total_bots = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)", (current_user.id,))
    total_msgs = c.fetchone()['count']
    conn.close()
    stats = {'total_bots': total_bots, 'total_messages': total_msgs, 'active_users': 0}
    return render_template('profile.html', user=current_user, stats=stats)

# ============ API ROUTES ============
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields required'})
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                  (username, email, generate_password_hash(password)))
        conn.commit()
        return jsonify({'success': True, 'message': 'Registration successful'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username or email already exists'})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        login_user(User(user))
        return jsonify({'success': True, 'message': 'Login successful'})
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/login_bot_token', methods=['POST'])
@login_required
def login_bot_token():
    data = request.json
    bot_name = data.get('bot_name', '').strip()
    bot_token = data.get('bot_token', '').strip()
    
    if not bot_name or not bot_token:
        return jsonify({'success': False, 'message': 'Bot name and token required'})
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO bots (user_id, login_type, bot_name, bot_token, status) VALUES (?, 'bot_token', ?, ?, 'running')", 
                  (current_user.id, bot_name, bot_token))
        conn.commit()
        return jsonify({'success': True, 'message': 'Bot connected successfully'})
    except:
        return jsonify({'success': False, 'message': 'Failed to create bot'})
    finally:
        conn.close()

@app.route('/api/login_user_api', methods=['POST'])
@login_required
def login_user_api():
    data = request.json
    bot_name = data.get('bot_name', '').strip()
    api_id = data.get('api_id', '')
    api_hash = data.get('api_hash', '').strip()
    phone_number = data.get('phone_number', '').strip()
    
    if not all([bot_name, api_id, api_hash, phone_number]):
        return jsonify({'success': False, 'message': 'All fields required'})
    
    session['temp_bot_data'] = {
        'bot_name': bot_name,
        'api_id': api_id,
        'api_hash': api_hash,
        'phone_number': phone_number,
        'user_id': current_user.id
    }
    
    return jsonify({'success': True, 'message': 'OTP sent successfully'})

@app.route('/api/verify_code', methods=['POST'])
@login_required
def verify_code():
    data = request.json
    code = data.get('code', '').strip()
    temp_data = session.get('temp_bot_data', {})
    
    if not temp_data:
        return jsonify({'success': False, 'message': 'Session expired'})
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO bots (user_id, login_type, bot_name, api_id, api_hash, phone_number, status) 
                     VALUES (?, 'user_api', ?, ?, ?, ?, 'running')""", 
                  (current_user.id, temp_data['bot_name'], temp_data['api_id'], 
                   temp_data['api_hash'], temp_data['phone_number']))
        conn.commit()
        session.pop('temp_bot_data', None)
        return jsonify({'success': True, 'message': 'User API connected successfully'})
    except:
        return jsonify({'success': False, 'message': 'Failed to create bot'})
    finally:
        conn.close()

@app.route('/api/create_bot', methods=['POST'])
@login_required
def create_bot():
    data = request.json
    bot_name = data.get('name', '').strip()
    bot_token = data.get('token', '').strip()
    
    if not bot_name or not bot_token:
        return jsonify({'success': False, 'message': 'Bot name and token required'})
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO bots (user_id, login_type, bot_name, bot_token) VALUES (?, 'bot_token', ?, ?)", 
                  (current_user.id, bot_name, bot_token))
        bot_id = c.lastrowid
        conn.commit()
        return jsonify({'success': True, 'message': 'Bot created', 'bot_id': bot_id})
    except:
        return jsonify({'success': False, 'message': 'Failed to create bot'})
    finally:
        conn.close()

@app.route('/api/start_bot/<int:bot_id>')
@login_required
def start_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE bots SET status = 'running' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Bot started'})

@app.route('/api/stop_bot/<int:bot_id>')
@login_required
def stop_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE bots SET status = 'stopped' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Bot stopped'})

@app.route('/api/restart_bot/<int:bot_id>')
@login_required
def restart_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE bots SET status = 'running' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Bot restarted'})

@app.route('/api/delete_bot/<int:bot_id>', methods=['DELETE'])
@login_required
def delete_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Bot deleted'})

@app.route('/api/add_message/<int:bot_id>', methods=['POST'])
@login_required
def add_message(bot_id):
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'message': 'Message text required'})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO messages (bot_id, message_text) VALUES (?, ?)", (bot_id, message))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Message added'})

@app.route('/api/get_messages/<int:bot_id>')
@login_required
def get_messages(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE bot_id = ? ORDER BY created_at DESC", (bot_id,))
    messages = c.fetchall()
    conn.close()
    return jsonify({'success': True, 'messages': [dict(m) for m in messages]})

@app.route('/api/delete_message/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Message deleted'})

@app.route('/api/dashboard_stats')
@login_required
def dashboard_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (current_user.id,))
    total_bots = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ? AND status = 'running'", (current_user.id,))
    active_bots = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)", (current_user.id,))
    total_msgs = c.fetchone()['count']
    conn.close()
    return jsonify({'success': True, 'stats': {'total_bots': total_bots, 'active_bots': active_bots, 'total_messages': total_msgs, 'active_users': 0}})

@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    current = data.get('current', '')
    new_password = data.get('new_password', '')
    
    if not current or not new_password:
        return jsonify({'success': False, 'message': 'All fields required'})
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (current_user.id,))
    user = c.fetchone()
    
    if not check_password_hash(user['password'], current):
        conn.close()
        return jsonify({'success': False, 'message': 'Current password is incorrect'})
    
    c.execute("UPDATE users SET password = ? WHERE id = ?", (generate_password_hash(new_password), current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Password changed successfully'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
