from pyrogram import Client, filters
from pyrogram.types import Message
import asyncio
import time
import random
import re
from datetime import datetime
import threading
import os
import logging

logger = logging.getLogger(__name__)

class BotEngine:
    def __init__(self):
        self.bots = {}
        self.stop_flags = {}
        self.bot_clients = {}
        self.db = None
        self.uptime = datetime.now()
        os.makedirs('sessions', exist_ok=True)
    
    def set_db(self, db):
        self.db = db
    
    def test_bot_token(self, token):
        try:
            parts = token.split(':')
            if len(parts) != 2 or not parts[0].isdigit():
                raise Exception('Invalid token format. Expected: 1234567890:ABCdef...')
            client = Client(f"sessions/temp_token_{int(time.time())}", bot_token=token)
            client.start()
            client.stop()
            return True
        except Exception as e:
            raise Exception(f'Invalid bot token: {str(e)}')
    
    def send_otp(self, api_id, api_hash, phone_number):
        try:
            client = Client(f"sessions/temp_otp_{int(time.time())}", api_id=int(api_id), api_hash=api_hash)
            client.start()
            client.send_code(phone_number)
            client.stop()
            return True
        except Exception as e:
            raise Exception(f'Failed to send OTP: {str(e)}')
    
    def verify_otp(self, api_id, api_hash, phone_number, code):
        try:
            client = Client(f"sessions/user_{phone_number.replace('+', '')}", api_id=int(api_id), api_hash=api_hash)
            client.start()
            client.sign_in(phone_number, code)
            return client
        except Exception as e:
            raise Exception(f'Failed to verify OTP: {str(e)}')
    
    def start_bot(self, bot_id):
        try:
            if not self.db:
                from database import Database
                self.db = Database()
            
            bot_data = self.db.get_bot(bot_id)
            if not bot_data:
                return False
            
            if bot_id in self.bot_clients:
                return True
            
            session_name = f"sessions/bot_{bot_id}"
            
            try:
                if bot_data['login_type'] == 'bot_token':
                    client = Client(session_name, bot_token=bot_data['bot_token'])
                else:
                    client = Client(session_name, api_id=int(bot_data['api_id']), api_hash=bot_data['api_hash'])
            except Exception as e:
                logger.error(f"Failed to create client for bot {bot_id}: {e}")
                return False
            
            self.register_handlers(client, bot_id)
            
            try:
                client.start()
                self.bot_clients[bot_id] = client
                self.stop_flags[bot_id] = False
                self.db.update_bot_status(bot_id, 'running')
                threading.Thread(target=self.run_bot, args=(bot_id, client), daemon=True).start()
                return True
            except Exception as e:
                logger.error(f"Failed to start client for bot {bot_id}: {e}")
                return False
        except Exception as e:
            logger.error(f"Start bot error: {e}")
            return False
    
    def run_bot(self, bot_id, client):
        try:
            client.run()
        except Exception as e:
            logger.error(f"Bot {bot_id} stopped: {e}")
            if self.db:
                self.db.update_bot_status(bot_id, 'stopped')
            if bot_id in self.bot_clients:
                del self.bot_clients[bot_id]
    
    def stop_bot(self, bot_id):
        try:
            if bot_id in self.bot_clients:
                self.stop_flags[bot_id] = True
                try:
                    self.bot_clients[bot_id].stop()
                except:
                    pass
                del self.bot_clients[bot_id]
                if bot_id in self.stop_flags:
                    del self.stop_flags[bot_id]
                if self.db:
                    self.db.update_bot_status(bot_id, 'stopped')
            return True
        except Exception as e:
            logger.error(f"Stop bot error: {e}")
            return False
    
    def restart_bot(self, bot_id):
        self.stop_bot(bot_id)
        time.sleep(2)
        return self.start_bot(bot_id)
    
    def get_bot_status(self, bot_id):
        if bot_id in self.bot_clients:
            try:
                self.bot_clients[bot_id].get_me()
                return 'running'
            except:
                return 'stopped'
        return 'stopped'
    
    def register_handlers(self, client, bot_id):
        
        @client.on_message(filters.command(['add']) & filters.private)
        async def add_message(client, message):
            try:
                if len(message.text.split()) < 2:
                    await message.reply("❌ Usage: .add <message>")
                    return
                msg_text = ' '.join(message.text.split()[1:])
                if self.db:
                    self.db.add_message(bot_id, msg_text)
                await message.reply(f"✅ Message added successfully!\n\n📝 {msg_text}")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['list']) & filters.private)
        async def list_messages(client, message):
            try:
                if not self.db:
                    await message.reply("❌ Database not available")
                    return
                messages = self.db.get_messages(bot_id)
                if not messages:
                    await message.reply("📭 No messages found")
                    return
                reply = "📝 **Your Messages:**\n\n"
                for i, msg in enumerate(messages[:20], 1):
                    reply += f"{i}. {msg['message_text'][:50]}...\n"
                await message.reply(reply)
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['del']) & filters.private)
        async def delete_message(client, message):
            try:
                if len(message.text.split()) < 2:
                    await message.reply("❌ Usage: .del <number>")
                    return
                try:
                    num = int(message.text.split()[1])
                    if not self.db:
                        await message.reply("❌ Database not available")
                        return
                    messages = self.db.get_messages(bot_id)
                    if 1 <= num <= len(messages):
                        msg_id = messages[num-1]['id']
                        self.db.delete_message(msg_id)
                        await message.reply(f"✅ Message {num} deleted successfully!")
                    else:
                        await message.reply("❌ Invalid message number")
                except ValueError:
                    await message.reply("❌ Invalid number format")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['clear']) & filters.private)
        async def clear_messages(client, message):
            try:
                if self.db:
                    self.db.clear_messages(bot_id)
                await message.reply("🗑️ All messages cleared successfully!")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rr', 'rron']) & filters.private)
        async def enable_autoreply(client, message):
            try:
                if 'off' in message.text.lower():
                    await message.reply("⛔ Auto-reply disabled")
                    return
                await message.reply("✅ Auto-reply enabled successfully!\n\n💡 Use .rr off to disable")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rroff']) & filters.private)
        async def disable_autoreply(client, message):
            await message.reply("⛔ Auto-reply disabled")
        
        @client.on_message(filters.command(['active']) & filters.private)
        async def show_active_users(client, message):
            try:
                if not self.db:
                    await message.reply("❌ Database not available")
                    return
                users = self.db.get_active_users(bot_id)
                if not users:
                    await message.reply("📭 No active users")
                    return
                reply = "👤 **Active Users:**\n\n"
                for user in users[:20]:
                    reply += f"• {user['target_username'] or user['target_user_id']}\n"
                await message.reply(reply)
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['del_msg']) & filters.private)
        async def enable_auto_delete(client, message):
            try:
                if message.reply_to_message:
                    user_id = message.reply_to_message.from_user.id
                    chat_id = message.chat.id
                    if self.db:
                        self.db.add_deleted_user(bot_id, user_id, chat_id)
                    await message.reply(f"✅ Auto-delete enabled for user {user_id}")
                else:
                    await message.reply("❌ Reply to a user's message")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rdel_msg']) & filters.private)
        async def disable_auto_delete(client, message):
            await message.reply("⛔ Auto-delete disabled for this user")
        
        @client.on_message(filters.command(['raid']) & filters.private)
        async def raid_command(client, message):
            try:
                args = message.text.split()
                if len(args) < 3:
                    await message.reply("❌ Usage: .raid @user count [message]")
                    return
                
                target = args[1]
                try:
                    count = min(int(args[2]), 1000)
                except ValueError:
                    await message.reply("❌ Invalid count")
                    return
                
                msg = ' '.join(args[3:]) if len(args) > 3 else f"Hello {target}!"
                
                self.stop_flags[bot_id] = False
                await message.reply(f"⚡ Starting raid on {target} ({count} messages)...\n\n⚠️ Type .rraid to stop")
                
                for i in range(count):
                    if self.stop_flags.get(bot_id, False):
                        await message.reply(f"⛔ Raid stopped at {i}/{count}")
                        return
                    
                    try:
                        await client.send_message(message.chat.id, f"{msg} [{i+1}/{count}]")
                        if (i + 1) % 50 == 0:
                            await message.reply(f"📊 Progress: {i+1}/{count}")
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.error(f"Raid send error: {e}")
                
                await message.reply(f"✅ Raid completed! Sent {count} messages to {target}")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rraid']) & filters.private)
        async def stop_raid(client, message):
            self.stop_flags[bot_id] = True
            await message.reply("⛔ Raid stopped by user")
        
        @client.on_message(filters.command(['purge']) & filters.private)
        async def purge_messages(client, message):
            try:
                if len(message.text.split()) < 2:
                    await message.reply("❌ Usage: .purge <count>")
                    return
                
                try:
                    count = int(message.text.split()[1])
                except ValueError:
                    await message.reply("❌ Invalid count")
                    return
                
                self.stop_flags[bot_id] = False
                await message.reply(f"🧹 Purging {count} messages...")
                
                me = await client.get_me()
                deleted = 0
                
                async for msg in client.get_chat_history(message.chat.id, limit=count + 50):
                    if self.stop_flags.get(bot_id, False):
                        await message.reply(f"⛔ Purge stopped at {deleted}/{count}")
                        return
                    
                    if msg.from_user and msg.from_user.id == me.id:
                        try:
                            await msg.delete()
                            deleted += 1
                            if deleted % 100 == 0:
                                await asyncio.sleep(3)
                        except Exception as e:
                            logger.error(f"Purge delete error: {e}")
                
                await message.reply(f"✅ Purged {deleted} messages")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rpurge']) & filters.private)
        async def stop_purge(client, message):
            self.stop_flags[bot_id] = True
            await message.reply("⛔ Purge stopped")
        
        @client.on_message(filters.command(['autodel']) & filters.private)
        async def auto_delete_timer(client, message):
            try:
                args = message.text.split()
                if len(args) < 2:
                    await message.reply("❌ Usage: .autodel on [seconds] or .autodel off")
                    return
                
                if args[1].lower() == 'on':
                    seconds = int(args[2]) if len(args) > 2 else 30
                    if self.db:
                        self.db.update_settings(bot_id, {'auto_delete_enabled': 1, 'auto_delete_time': seconds})
                    await message.reply(f"✅ Auto-delete enabled: {seconds} seconds")
                elif args[1].lower() == 'off':
                    if self.db:
                        self.db.update_settings(bot_id, {'auto_delete_enabled': 0})
                    await message.reply("⛔ Auto-delete disabled")
                else:
                    await message.reply("❌ Invalid option")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rautodel']) & filters.private)
        async def disable_timer(client, message):
            if self.db:
                self.db.update_settings(bot_id, {'auto_delete_enabled': 0})
            await message.reply("⛔ Auto-delete timer disabled")
        
        @client.on_message(filters.command(['antidel']) & filters.private)
        async def anti_delete(client, message):
            try:
                args = message.text.split()
                if len(args) < 2:
                    await message.reply("❌ Usage: .antidel on/off")
                    return
                
                if args[1].lower() == 'on':
                    if self.db:
                        self.db.update_settings(bot_id, {'anti_delete_enabled': 1})
                    await message.reply("🛡️ Anti-delete protection enabled")
                elif args[1].lower() == 'off':
                    if self.db:
                        self.db.update_settings(bot_id, {'anti_delete_enabled': 0})
                    await message.reply("⛔ Anti-delete disabled")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['rantidel']) & filters.private)
        async def disable_antidel(client, message):
            if self.db:
                self.db.update_settings(bot_id, {'anti_delete_enabled': 0})
            await message.reply("⛔ Anti-delete disabled")
        
        @client.on_message(filters.command(['ping']) & filters.private)
        async def ping_command(client, message):
            start = time.time()
            await client.send_chat_action(message.chat.id, 'typing')
            end = time.time()
            ping = round((end - start) * 1000)
            await message.reply(f"🏓 Pong!\n\n⏱️ {ping}ms\n📡 Online")
        
        @client.on_message(filters.command(['status']) & filters.private)
        async def status_command(client, message):
            try:
                me = await client.get_me()
                uptime = datetime.now() - self.uptime
                status = f"""
╔══════════════════════════════════════╗
║        ⚡ KAANUU USER BOT ⚡         ║
║   Status: ONLINE ✅                  ║
║   Bot: {me.first_name}              ║
║   ID: {me.id}                       ║
║   Uptime: {str(uptime).split('.')[0]}   ║
║   Created by: KAANUU                 ║
╚══════════════════════════════════════╝
"""
                await message.reply(status)
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
        
        @client.on_message(filters.command(['creator']) & filters.private)
        async def creator_command(client, message):
            card = """
╔══════════════════════════════════════╗
║        ⚡ KAANUU CREATOR ⚡          ║
║                                      ║
║   🌟 Creator: KAANUU                 ║
║   💻 Bot Manager Platform            ║
║   🚀 Telegram Automation             ║
║   ❤️ Made with passion               ║
║                                      ║
║   📱 Telegram: @KAANUU               ║
║   🌐 Website: https://kaanuu.dev     ║
║                                      ║
║   🔰 Powered by KAANUU              ║
╚══════════════════════════════════════╝
"""
            await message.reply(card)
        
        @client.on_message(filters.command(['help']) & filters.private)
        async def help_command(client, message):
            help_text = """
╔══════════════════════════════════════╗
║        ⚡ KAANUU USER BOT ⚡         ║
║   Powerful Telegram Automation      ║
║        Created by KAANUU            ║
╚══════════════════════════════════════╝

📝 **MESSAGES:** .add .list .del .clear
🎯 **AUTO-REPLY:** .rr on/off .active .ractive
🗑️ **AUTO-DELETE:** .del_msg .rdel_msg .delall .rdelall .dlist
⚡ **RAID (MAX 1000):** .raid @u 100 .rraid .raidstatus
⏱️ **TIMER:** .autodel on 30 .autodel off .rautodel
🛡️ **PROTECTION:** .antidel on/off .rantidel
🧹 **SAFE PURGE:** .purge 10 .purgeall .rpurge .purgestatus
📊 **INFO:** .ping .status .info .creator
🔧 **UTILITY:** .copy .id .whois
📚 **HELP:** .help .helpmsg .helprr .helpdel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 'r' = DISABLE | 🧹 Purge: Only own msgs
⚡ Raid: Max 1000, 2s delay | 🔰 KAANUU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            await message.reply(help_text)
        
        @client.on_message(filters.command(['helpmsg', 'helprr', 'helpdel']) & filters.private)
        async def help_subcommands(client, message):
            await message.reply("📚 Use .help for complete command list\n\n⚡ Powered by KAANUU")
