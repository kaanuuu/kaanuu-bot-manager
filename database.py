import sqlite3
import json
from datetime import datetime
import os

class Database:
    def __init__(self, db_path='instance/kaanuu.db'):
        self.db_path = db_path
        os.makedirs('instance', exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                plan TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_type TEXT NOT NULL,
                bot_token TEXT,
                api_id TEXT,
                api_hash TEXT,
                phone_number TEXT,
                bot_name TEXT NOT NULL,
                bot_username TEXT,
                status TEXT DEFAULT 'stopped',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                target_user_id TEXT NOT NULL,
                target_username TEXT,
                chat_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL UNIQUE,
                auto_delete_enabled INTEGER DEFAULT 0,
                auto_delete_time INTEGER DEFAULT 30,
                anti_delete_enabled INTEGER DEFAULT 0,
                anti_spam INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                target_user_id TEXT NOT NULL,
                chat_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        
        # Create default admin (password: admin123)
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password, is_admin)
            VALUES ('admin', 'admin@kaanuu.com', 'scrypt:32768:8:1$YVqXqFqV$e8f6d55a4f5f8a4f5d8a4f5d8a4f5d8a4f5d8a4f5d8a4f5d8a4f5d8a4f5d8a4f5d8a', 1)
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, username, email, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, password)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Create user error: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_user_by_username(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_user_by_email(self, email):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def update_password(self, user_id, hashed_password):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def create_bot(self, user_id, login_type, bot_name, bot_token=None, api_id=None, api_hash=None, phone_number=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO bots (user_id, login_type, bot_token, api_id, api_hash, phone_number, bot_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'stopped')
            ''', (user_id, login_type, bot_token, api_id, api_hash, phone_number, bot_name))
            bot_id = cursor.lastrowid
            cursor.execute('INSERT INTO settings (bot_id) VALUES (?)', (bot_id,))
            conn.commit()
            return bot_id
        except Exception as e:
            print(f"Create bot error: {e}")
            return None
        finally:
            conn.close()
    
    def get_bot(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
        bot = cursor.fetchone()
        conn.close()
        return dict(bot) if bot else None
    
    def get_user_bots(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        bots = cursor.fetchall()
        conn.close()
        return [dict(bot) for bot in bots]
    
    def update_bot_status(self, bot_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE bots SET status = ? WHERE id = ?', (status, bot_id))
        conn.commit()
        conn.close()
    
    def delete_bot(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM bots WHERE id = ?', (bot_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Delete bot error: {e}")
            return False
        finally:
            conn.close()
    
    def add_message(self, bot_id, message_text):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO messages (bot_id, message_text) VALUES (?, ?)',
                (bot_id, message_text)
            )
            conn.commit()
            return cursor.lastrowid
        except:
            return None
        finally:
            conn.close()
    
    def get_messages(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages WHERE bot_id = ? ORDER BY created_at DESC', (bot_id,))
        messages = cursor.fetchall()
        conn.close()
        return [dict(msg) for msg in messages]
    
    def delete_message(self, msg_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
        conn.commit()
        conn.close()
        return True
    
    def clear_messages(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE bot_id = ?', (bot_id,))
        conn.commit()
        conn.close()
        return True
    
    def add_active_user(self, bot_id, target_user_id, target_username, chat_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO active_users (bot_id, target_user_id, target_username, chat_id)
                VALUES (?, ?, ?, ?)
            ''', (bot_id, target_user_id, target_username, chat_id))
            conn.commit()
            return cursor.lastrowid
        except:
            return None
        finally:
            conn.close()
    
    def get_active_users(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_users WHERE bot_id = ? AND is_active = 1', (bot_id,))
        users = cursor.fetchall()
        conn.close()
        return [dict(user) for user in users]
    
    def toggle_active_user(self, target_id, is_active):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE active_users SET is_active = ? WHERE id = ?', (is_active, target_id))
        conn.commit()
        conn.close()
        return True
    
    def remove_active_user(self, target_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM active_users WHERE id = ?', (target_id,))
        conn.commit()
        conn.close()
        return True
    
    def get_settings(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM settings WHERE bot_id = ?', (bot_id,))
        settings = cursor.fetchone()
        conn.close()
        return dict(settings) if settings else None
    
    def update_settings(self, bot_id, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for key, value in data.items():
                if key in ['auto_delete_enabled', 'auto_delete_time', 'anti_delete_enabled', 'anti_spam']:
                    cursor.execute(
                        f'UPDATE settings SET {key} = ? WHERE bot_id = ?',
                        (value, bot_id)
                    )
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    
    def add_deleted_user(self, bot_id, target_user_id, chat_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO deleted_users (bot_id, target_user_id, chat_id) VALUES (?, ?, ?)',
                (bot_id, target_user_id, chat_id)
            )
            conn.commit()
            return cursor.lastrowid
        except:
            return None
        finally:
            conn.close()
    
    def get_deleted_users(self, bot_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM deleted_users WHERE bot_id = ?', (bot_id,))
        users = cursor.fetchall()
        conn.close()
        return [dict(user) for user in users]
    
    def remove_deleted_user(self, target_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM deleted_users WHERE id = ?', (target_id,))
        conn.commit()
        conn.close()
        return True
    
    def get_dashboard_stats(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {'total_bots': 0, 'active_bots': 0, 'total_messages': 0, 'active_users': 0}
        
        cursor.execute('SELECT COUNT(*) as count FROM bots WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        stats['total_bots'] = result['count'] if result else 0
        
        cursor.execute('SELECT COUNT(*) as count FROM bots WHERE user_id = ? AND status = "running"', (user_id,))
        result = cursor.fetchone()
        stats['active_bots'] = result['count'] if result else 0
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM messages 
            WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?)
        ''', (user_id,))
        result = cursor.fetchone()
        stats['total_messages'] = result['count'] if result else 0
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM active_users 
            WHERE bot_id IN (SELECT id FROM bots WHERE user_id = ?) AND is_active = 1
        ''', (user_id,))
        result = cursor.fetchone()
        stats['active_users'] = result['count'] if result else 0
        
        conn.close()
        return stats
