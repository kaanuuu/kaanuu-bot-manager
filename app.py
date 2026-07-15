from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database
from bot_core import BotEngine
import json
import os
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Create necessary directories
os.makedirs('sessions', exist_ok=True)
os.makedirs('instance', exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

db = Database()
bot_engine = BotEngine()
bot_engine.set_db(db)

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
        user_data = db.get_user_by_id(int(user_id))
        if user_data:
            return User(user_data)
    except:
        pass
    return None

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    stats = db.get_dashboard_stats(current_user.id)
    return render_template('dashboard.html', stats=stats, user=current_user)

@app.route('/bots')
@login_required
def bots():
    bots = db.get_user_bots(current_user.id)
    return render_template('bots.html', bots=bots, user=current_user)

@app.route('/commands')
@login_required
def commands():
    return render_template('commands.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    stats = db.get_dashboard_stats(current_user.id)
    return render_template('profile.html', user=current_user, stats=stats)

# API Routes
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
        
        if db.get_user_by_username(username):
            return jsonify({'success': False, 'message': 'Username already exists'})
        
        if db.get_user_by_email(email):
            return jsonify({'success': False, 'message': 'Email already registered'})
        
        hashed_password = generate_password_hash(password)
        user_id = db.create_user(username, email, hashed_password)
        
        if user_id:
            return jsonify({'success': True, 'message': 'Registration successful'})
        return jsonify({'success': False, 'message': 'Registration failed'})
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Server error'})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        user_data = db.get_user_by_username(username)
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return jsonify({'success': True, 'message': 'Login successful'})
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Server error'})

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
        
        if ':' not in bot_token or not bot_token.split(':')[0].isdigit():
            return jsonify({'success': False, 'message': 'Invalid bot token format'})
        
        try:
            bot_engine.test_bot_token(bot_token)
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
        
        bot_id = db.create_bot(
            user_id=current_user.id,
            login_type='bot_token',
            bot_token=bot_token,
            bot_name=bot_name
        )
        
        if bot_id:
            success = bot_engine.start_bot(bot_id)
            if success:
                return jsonify({'success': True, 'message': 'Bot connected successfully'})
            else:
                db.delete_bot(bot_id)
                return jsonify({'success': False, 'message': 'Failed to start bot'})
        
        return jsonify({'success': False, 'message': 'Failed to create bot'})
    except Exception as e:
        logger.error(f"Bot token login error: {e}")
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
        
        try:
            api_id = int(api_id)
        except:
            return jsonify({'success': False, 'message': 'Invalid API ID'})
        
        session['temp_bot_data'] = {
            'bot_name': bot_name,
            'api_id': api_id,
            'api_hash': api_hash,
            'phone_number': phone_number,
            'user_id': current_user.id
        }
        
        try:
            bot_engine.send_otp(api_id, api_hash, phone_number)
            return jsonify({'success': True, 'message': 'OTP sent successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Failed to send OTP: {str(e)}'})
    except Exception as e:
        logger.error(f"User API login error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/verify_code', methods=['POST'])
@login_required
def verify_code():
    try:
        data = request.json
        code = data.get('code', '').strip()
        temp_data = session.get('temp_bot_data', {})
        
        if not temp_data:
            return jsonify({'success': False, 'message': 'Session expired. Please try again.'})
        
        if not code:
            return jsonify({'success': False, 'message': 'Verification code required'})
        
        try:
            client = bot_engine.verify_otp(
                temp_data['api_id'],
                temp_data['api_hash'],
                temp_data['phone_number'],
                code
            )
            
            if client:
                bot_id = db.create_bot(
                    user_id=current_user.id,
                    login_type='user_api',
                    api_id=temp_data['api_id'],
                    api_hash=temp_data['api_hash'],
                    phone_number=temp_data['phone_number'],
                    bot_name=temp_data['bot_name']
                )
                
                if bot_id:
                    bot_engine.start_bot(bot_id)
                    session.pop('temp_bot_data', None)
                    return jsonify({'success': True, 'message': 'User API connected successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Verification failed: {str(e)}'})
        
        return jsonify({'success': False, 'message': 'Verification failed'})
    except Exception as e:
        logger.error(f"Verify code error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/create_bot', methods=['POST'])
@login_required
def create_bot():
    try:
        data = request.json
        bot_type = data.get('type', 'bot_token')
        bot_name = data.get('name', '').strip()
        
        if not bot_name:
            return jsonify({'success': False, 'message': 'Bot name required'})
        
        if bot_type == 'bot_token':
            token = data.get('token', '').strip()
            if not token:
                return jsonify({'success': False, 'message': 'Bot token required'})
            bot_id = db.create_bot(
                user_id=current_user.id,
                login_type='bot_token',
                bot_token=token,
                bot_name=bot_name
            )
        else:
            api_id = data.get('api_id', '')
            api_hash = data.get('api_hash', '').strip()
            phone = data.get('phone', '').strip()
            
            if not all([api_id, api_hash, phone]):
                return jsonify({'success': False, 'message': 'All API fields required'})
            
            try:
                api_id = int(api_id)
            except:
                return jsonify({'success': False, 'message': 'Invalid API ID'})
            
            bot_id = db.create_bot(
                user_id=current_user.id,
                login_type='user_api',
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone,
                bot_name=bot_name
            )
        
        if bot_id:
            bot_engine.start_bot(bot_id)
            return jsonify({'success': True, 'message': 'Bot created successfully', 'bot_id': bot_id})
        return jsonify({'success': False, 'message': 'Failed to create bot'})
    except Exception as e:
        logger.error(f"Create bot error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/start_bot/<int:bot_id>', methods=['GET'])
@login_required
def start_bot(bot_id):
    try:
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        success = bot_engine.start_bot(bot_id)
        if success:
            db.update_bot_status(bot_id, 'running')
            return jsonify({'success': True, 'message': 'Bot started'})
        return jsonify({'success': False, 'message': 'Failed to start bot'})
    except Exception as e:
        logger.error(f"Start bot error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop_bot/<int:bot_id>', methods=['GET'])
@login_required
def stop_bot(bot_id):
    try:
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        success = bot_engine.stop_bot(bot_id)
        if success:
            db.update_bot_status(bot_id, 'stopped')
            return jsonify({'success': True, 'message': 'Bot stopped'})
        return jsonify({'success': False, 'message': 'Failed to stop bot'})
    except Exception as e:
        logger.error(f"Stop bot error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/restart_bot/<int:bot_id>', methods=['GET'])
@login_required
def restart_bot(bot_id):
    try:
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        success = bot_engine.restart_bot(bot_id)
        if success:
            db.update_bot_status(bot_id, 'running')
            return jsonify({'success': True, 'message': 'Bot restarted'})
        return jsonify({'success': False, 'message': 'Failed to restart bot'})
    except Exception as e:
        logger.error(f"Restart bot error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_bot/<int:bot_id>', methods=['DELETE'])
@login_required
def delete_bot(bot_id):
    try:
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        bot_engine.stop_bot(bot_id)
        if db.delete_bot(bot_id):
            return jsonify({'success': True, 'message': 'Bot deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete bot'})
    except Exception as e:
        logger.error(f"Delete bot error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add_message/<int:bot_id>', methods=['POST'])
@login_required
def add_message(bot_id):
    try:
        data = request.json
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'success': False, 'message': 'Message text required'})
        
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        if db.add_message(bot_id, message_text):
            return jsonify({'success': True, 'message': 'Message added'})
        return jsonify({'success': False, 'message': 'Failed to add message'})
    except Exception as e:
        logger.error(f"Add message error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_messages/<int:bot_id>', methods=['GET'])
@login_required
def get_messages(bot_id):
    try:
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        messages = db.get_messages(bot_id)
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_message/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    try:
        if db.delete_message(msg_id):
            return jsonify({'success': True, 'message': 'Message deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete message'})
    except Exception as e:
        logger.error(f"Delete message error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add_target/<int:bot_id>', methods=['POST'])
@login_required
def add_target(bot_id):
    try:
        data = request.json
        target_id = data.get('target_id', '').strip()
        target_username = data.get('target_username', '').strip()
        chat_id = data.get('chat_id', 'private')
        
        if not target_id:
            return jsonify({'success': False, 'message': 'Target ID required'})
        
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        if db.add_active_user(bot_id, target_id, target_username, chat_id):
            return jsonify({'success': True, 'message': 'Target added'})
        return jsonify({'success': False, 'message': 'Failed to add target'})
    except Exception as e:
        logger.error(f"Add target error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/update_settings/<int:bot_id>', methods=['POST'])
@login_required
def update_settings(bot_id):
    try:
        data = request.json
        bot_data = db.get_bot(bot_id)
        if not bot_data or bot_data['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        if db.update_settings(bot_id, data):
            return jsonify({'success': True, 'message': 'Settings updated'})
        return jsonify({'success': False, 'message': 'Failed to update settings'})
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    try:
        stats = db.get_dashboard_stats(current_user.id)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/creator_info', methods=['GET'])
def creator_info():
    return jsonify({
        'name': 'KAANUU',
        'website': 'https://github.com/KAANUU',
        'version': '1.0.0'
    })

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
        
        user_data = db.get_user_by_id(current_user.id)
        if not check_password_hash(user_data['password'], current):
            return jsonify({'success': False, 'message': 'Current password is incorrect'})
        
        hashed = generate_password_hash(new_password)
        if db.update_password(current_user.id, hashed):
            return jsonify({'success': True, 'message': 'Password changed successfully'})
        return jsonify({'success': False, 'message': 'Failed to change password'})
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
