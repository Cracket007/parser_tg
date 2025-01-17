from telethon import TelegramClient, events
import logging
import sqlite3
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)
active_clients = {}
phone_code_hashes = {}

async def start_client(user_id, api_id, api_hash, phone, keywords, bot):
    try:
        print(f"\n🔐 Попытка подключения для {phone}")
        print(f"📝 Данные: API_ID={api_id}, HASH={api_hash[:8]}...")
        
        client = TelegramClient(f'sessions/{user_id}', int(api_id), api_hash)
        await client.connect()
        
        is_authorized = await client.is_user_authorized()
        print(f"📱 Статус авторизации: {'✅ Авторизован' if is_authorized else '❌ Не авторизован'}")
        
        if not is_authorized:
            try:
                print("📤 Отправляем запрос на код...")
                send_code_result = await client.send_code_request(phone)
                phone_code_hash = send_code_result.phone_code_hash
                print(f"📨 Код отправлен успешно. Hash: {phone_code_hash[:8]}...")
                
                phone_code_hashes[user_id] = phone_code_hash
                print(f"💾 Сохранен hash для user_id: {user_id}")
                
                # Устанавливаем состояние ожидания кода
                from handlers import user_states, UserState
                user_states[user_id] = UserState.WAITING_CODE
                
                await bot.send_message(
                    user_id, 
                    "📱 Код подтверждения отправлен на ваш телефон.\n"
                    "⚠️ У вас есть 2 минуты чтобы ввести код.\n"
                    "Отправьте его мне:"
                )
                await client.disconnect()
                return None  # Возвращаем None вместо False
                
            except Exception as e:
                logger.error(f"Ошибка при отправке кода: {e}")
                await bot.send_message(user_id, f"❌ Ошибка при отправке кода: {str(e)}")
                await client.disconnect()
                return False

        # Если уже авторизован - продолжаем работу
        active_clients[user_id] = client
        print("✅ Клиент успешно запущен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при запуске клиента: {e}")
        if 'client' in locals():
            await client.disconnect()
        return False

async def stop_client(user_id):
    if user_id in active_clients:
        client = active_clients[user_id]
        await client.disconnect()
        del active_clients[user_id]
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

async def check_bot_permissions(chat_id, bot):
    try:
        bot_member = await bot.get_permissions(int(chat_id))
        return bot_member.send_messages
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False

async def send_message_to_target(user_id, message, bot):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT target_chat_id FROM users WHERE user_id = ?", (user_id,))
        target_chat = c.fetchone()
        conn.close()
        
        chat_id = target_chat[0] if target_chat and target_chat[0] else user_id
        
        try:
            await bot.send_message(int(chat_id), message)
        except Exception as e:
            if "Chat not found" in str(e) or "Channel not found" in str(e):
                await bot.send_message(user_id, """
❌ Ошибка отправки сообщения в целевой чат!

Возможные причины:
1️⃣ Бот не добавлен в группу
2️⃣ У бота нет прав администратора
3️⃣ Чат был удален или недоступен

Используйте /setchat для настройки нового чата.
""")
            else:
                raise e
                
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        await bot.send_message(user_id, message) 