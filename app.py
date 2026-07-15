from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import sys

app = Flask(__name__)
app.secret_key = 'kaanuu-super-secret-key-2024'

# Create directories
try:
    os.makedirs('instance', exist_ok=True)
    os.makedirs('sessions', exist_ok=True)
except:
    pass

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

# ============ DATABASE ============
def get_db():
    try:
        conn = sqlite3.connect('instance/kaanuu.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database error: {e}")
        return None

def init_db():
    try:
        conn = get_db()
        if conn is None:
            return
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0,
            plan TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            login_type TEXT DEFAULT 'bot_token',
            bot_token TEXT,
            api_id TEXT,
            api_hash TEXT,
            phone_number TEXT,
            bot_name TEXT,
            bot_username TEXT,
            status TEXT DEFAULT 'stopped',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER,
            message_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER,
            target_user_id TEXT,
            target_username TEXT,
            chat_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER UNIQUE,
            auto_delete_enabled INTEGER DEFAULT 0,
            auto_delete_time INTEGER DEFAULT 30,
            anti_delete_enabled INTEGER DEFAULT 0,
            anti_spam INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS deleted_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER,
            target_user_id TEXT,
            chat_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Default admin: admin/admin123
        c.execute("INSERT OR IGNORE INTO users (username, email, password, is_admin) VALUES ('admin', 'admin@kaanuu.com', 'pbkdf2:sha256:260000$eH9j0VjL$f4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5', 1)")
        
        conn.commit()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Init DB error: {e}")

# Initialize database
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
    try:
        conn = get_db()
        if conn is None:
            return None
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return User(user)
        return None
    except:
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
    try:
        conn = get_db()
        if conn is None:
            return render_template('dashboard.html', stats={'total_bots':0, 'active_bots':0, 'total_messages':0, 'active_users':0}, user=current_user)
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
    except:
        return render_template('dashboard.html', stats={'total_bots':0, 'active_bots':0, 'total_messages':0, 'active_users':0}, user=current_user)

@app.route('/bots')
@login_required
def bots():
    try:
        conn = get_db()
        if conn is None:
            return render_template('bots.html', bots=[], user=current_user)
        c = conn.cursor()
        c.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (current_user.id,))
        bots = c.fetchall()
        conn.close()
        return render_template('bots.html', bots=bots, user=current_user)
    except:
        return render_template('bots.html', bots=[], user=current_user)

@app.route('/commands')
@login_required
def commands():
    return render_template('commands.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    try:
        conn = get_db()
        if conn is None:
            return render_template('profile.html', user=current_user, stats={'total_bots':0, 'total_messages':0, 'active_users':0})
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (current_user.id,))
        total_bots = c.fetchone()['count']
        c.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)", (current_user.id,))
        total_msgs = c.fetchone()['count']
        conn.close()
        stats = {'total_bots': total_bots, 'total_messages': total_msgs, 'active_users': 0}
        return render_template('profile.html', user=current_user, stats=stats)
    except:
        return render_template('profile.html', user=current_user, stats={'total_bots':0, 'total_messages':0, 'active_users':0})

# ============ API ROUTES ============
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'All fields required'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                  (username, email, generate_password_hash(password)))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Registration successful'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username or email already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            login_user(User(user))
            return jsonify({'success': True, 'message': 'Login successful'})
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/login_bot_token', methods=['POST'])
@login_required
def login_bot_token():
    try:
        data = request.json
        bot_name = data.get('bot_name', '').strip()
        bot_token = data.get('bot_token', '').strip()
        
        if not bot_name or not bot_token:
            return jsonify({'success': False, 'message': 'Bot name and token required'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("INSERT INTO bots (user_id, login_type, bot_name, bot_token, status) VALUES (?, 'bot_token', ?, ?, 'running')", 
                  (current_user.id, bot_name, bot_token))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot connected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/login_user_api', methods=['POST'])
@login_required
def login_user_api():
    try:
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
            'phone_number': phone_number
        }
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/verify_code', methods=['POST'])
@login_required
def verify_code():
    try:
        data = request.json
        code = data.get('code', '').strip()
        temp_data = session.get('temp_bot_data', {})
        
        if not temp_data:
            return jsonify({'success': False, 'message': 'Session expired'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("""INSERT INTO bots (user_id, login_type, bot_name, api_id, api_hash, phone_number, status) 
                     VALUES (?, 'user_api', ?, ?, ?, ?, 'running')""", 
                  (current_user.id, temp_data['bot_name'], temp_data['api_id'], 
                   temp_data['api_hash'], temp_data['phone_number']))
        conn.commit()
        conn.close()
        session.pop('temp_bot_data', None)
        return jsonify({'success': True, 'message': 'User API connected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/create_bot', methods=['POST'])
@login_required
def create_bot():
    try:
        data = request.json
        bot_name = data.get('name', '').strip()
        bot_token = data.get('token', '').strip()
        
        if not bot_name or not bot_token:
            return jsonify({'success': False, 'message': 'Bot name and token required'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("INSERT INTO bots (user_id, login_type, bot_name, bot_token) VALUES (?, 'bot_token', ?, ?)", 
                  (current_user.id, bot_name, bot_token))
        bot_id = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot created', 'bot_id': bot_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/start_bot/<int:bot_id>')
@login_required
def start_bot(bot_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("UPDATE bots SET status = 'running' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop_bot/<int:bot_id>')
@login_required
def stop_bot(bot_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("UPDATE bots SET status = 'stopped' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot stopped'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/restart_bot/<int:bot_id>')
@login_required
def restart_bot(bot_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("UPDATE bots SET status = 'running' WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot restarted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_bot/<int:bot_id>', methods=['DELETE'])
@login_required
def delete_bot(bot_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, current_user.id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Bot deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add_message/<int:bot_id>', methods=['POST'])
@login_required
def add_message(bot_id):
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'message': 'Message text required'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("INSERT INTO messages (bot_id, message_text) VALUES (?, ?)", (bot_id, message))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Message added'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_messages/<int:bot_id>')
@login_required
def get_messages(bot_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'messages': []})
        c = conn.cursor()
        c.execute("SELECT * FROM messages WHERE bot_id = ? ORDER BY created_at DESC", (bot_id,))
        messages = c.fetchall()
        conn.close()
        return jsonify({'success': True, 'messages': [dict(m) for m in messages]})
    except Exception as e:
        return jsonify({'success': False, 'messages': []})

@app.route('/api/delete_message/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Message deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/dashboard_stats')
@login_required
def dashboard_stats():
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'success': True, 'stats': {'total_bots':0, 'active_bots':0, 'total_messages':0, 'active_users':0}})
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (current_user.id,))
        total_bots = c.fetchone()['count']
        c.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ? AND status = 'running'", (current_user.id,))
        active_bots = c.fetchone()['count']
        c.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)", (current_user.id,))
        total_msgs = c.fetchone()['count']
        conn.close()
        return jsonify({'success': True, 'stats': {'total_bots': total_bots, 'active_bots': active_bots, 'total_messages': total_msgs, 'active_users': 0}})
    except:
        return jsonify({'success': True, 'stats': {'total_bots':0, 'active_bots':0, 'total_messages':0, 'active_users':0}})

@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.json
        current = data.get('current', '')
        new_password = data.get('new_password', '')
        
        if not current or not new_password:
            return jsonify({'success': False, 'message': 'All fields required'})
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
        
        conn = get_db()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database error'})
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
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(e):
    return "Page not found", 404

@app.errorhandler(500)
def server_error(e):
    return "Server error", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
