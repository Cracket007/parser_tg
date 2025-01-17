from telethon import events, Button, TelegramClient, types
from telethon.tl.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardHide
)
import sqlite3
from datetime import datetime
import logging
from database import init_db
from messages import INSTRUCTIONS, HELP_MESSAGE
from client_manager import start_client, stop_client, check_bot_permissions, send_message_to_target, phone_code_hashes

logger = logging.getLogger(__name__)

# Словарь для хранения активных клиентов
active_clients = {}

# Добавим словарь для отслеживания состояния пользователя
user_states = {}

# Состояния пользователя
class UserState:
    WAITING_API_ID = 'waiting_api_id'
    WAITING_API_HASH = 'waiting_api_hash'
    WAITING_PHONE = 'waiting_phone'
    WAITING_KEYWORDS = 'waiting_keywords'
    EDIT_API_ID = 'edit_api_id'
    EDIT_API_HASH = 'edit_api_hash'
    EDIT_PHONE = 'edit_phone'
    EDIT_KEYWORDS = 'edit_keywords'
    WAITING_CODE = 'waiting_code'

async def start_handler(event, bot):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (event.sender_id,))
    user = c.fetchone()
    conn.close()

    if user and user[4]:  # Если есть ключевые слова, значит настройка завершена
        keyboard = [
            [Button.inline('▶️ Запустить парсер', 'start_parser')],
            [Button.inline('🔄 Начать настройку заново', 'reset_settings')]
        ]
        await event.respond("Парсер уже настроен. Выберите действие:", buttons=keyboard)
    else:
        # Начинаем процесс настройки
        user_states[event.sender_id] = UserState.WAITING_API_ID
        await event.respond("👋 Привет! Я помогу настроить парсер для Telegram.\n\n" + INSTRUCTIONS)

async def callback_handler(event, bot):
    if event.data == b'start_parser':
        await start_existing_parser(event, bot)
    elif event.data == b'reset_settings':
        await reset_user_settings(event)
    elif event.data == b'edit_api_id':
        user_states[event.sender_id] = UserState.EDIT_API_ID
        await event.respond("Отправьте новый API ID:")
    elif event.data == b'edit_api_hash':
        user_states[event.sender_id] = UserState.EDIT_API_HASH
        await event.respond("Отправьте новый API HASH:")
    elif event.data == b'edit_phone':
        user_states[event.sender_id] = UserState.EDIT_PHONE
        await event.respond("Отправьте новый номер телефона:")
    elif event.data == b'edit_keywords':
        user_states[event.sender_id] = UserState.EDIT_KEYWORDS
        await event.respond("Отправьте новые ключевые слова через запятую:")

async def help_handler(event, bot):
    await event.respond(HELP_MESSAGE)

async def id_handler(event, bot):
    chat = await event.get_chat()
    
    response = f"📝 Информация о чате:\n\n"
    response += f"ID: {chat.id}\n"
    
    # Определяем тип чата
    if hasattr(chat, 'megagroup') and chat.megagroup:
        chat_type = "Супергруппа"
    elif hasattr(chat, 'channel') and chat.channel:
        chat_type = "Канал"
    elif hasattr(chat, 'gigagroup') and chat.gigagroup:
        chat_type = "Гигагруппа"
    elif hasattr(chat, 'group') and chat.group:
        chat_type = "Группа"
    else:
        chat_type = "Личный чат"
    
    response += f"Тип: {chat_type}\n"
    
    if hasattr(chat, 'title') and chat.title:
        response += f"Название: {chat.title}\n"
    
    if hasattr(chat, 'username') and chat.username:
        response += f"Username: @{chat.username}\n"
        
    if chat_type == "Личный чат":
        sender = await event.get_sender()
        response += f"\n👤 Информация о пользователе:\n"
        response += f"Имя: {sender.first_name}\n"
        if sender.username:
            response += f"Username: @{sender.username}\n"
            
    await event.respond(response)

async def stop_handler(event, bot):
    user_id = event.sender_id
    if await stop_client(user_id):
        await event.respond("🛑 Парсер остановлен")
    else:
        await event.respond("❌ Парсер не был запущен")

async def stats_handler(event, bot):
    user_id = event.sender_id
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT messages_found, last_active, is_active FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    conn.close()

    if data:
        messages_found, last_active, is_active = data
        stats_text = f"📊 Статистика парсера:\n\n"
        stats_text += f"📝 Найдено сообщений: {messages_found}\n"
        stats_text += f"🕒 Последняя активность: {last_active}\n"
        stats_text += f"⚡️ Статус: {'Активен' if is_active else 'Остановлен'}"
        await event.respond(stats_text)
    else:
        await event.respond("❌ Статистика недоступна. Парсер не настроен.")

async def setchat_handler(event, bot):
    await event.respond("""
Чтобы установить чат для отправки результатов:

1️⃣ Добавьте бота в нужную группу
2️⃣ Сделайте бота администратором
3️⃣ Перешлите любое сообщение из этой группы мне

Или отправьте ID чата напрямую.
""")

async def start_existing_parser(event, bot):
    user_id = event.sender_id
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT api_id, api_hash, phone, keywords FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        api_id, api_hash, phone, keywords = user_data
        result = await start_client(user_id, api_id, api_hash, phone, keywords, bot)
        if result is True:  # Явно проверяем на True
            await event.respond("✅ Парсер запущен с сохраненными настройками")
        elif result is False:  # Явно проверяем на False
            await event.respond("❌ Ошибка при запуске парсера")
        # Если None - значит отправлен код, ничего не отвечаем
    else:
        await event.respond("❌ Настройки не найдены. Используйте /start для настройки")

async def reset_user_settings(event):
    user_id = event.sender_id
    
    # Удаляем файл сессии
    session_file = f'sessions/{user_id}.session'
    try:
        import os
        if os.path.exists(session_file):
            os.remove(session_file)
            print(f"🗑 Удален файл сессии: {session_file}")
    except Exception as e:
        print(f"❌ Ошибка при удалении сессии: {e}")

    # Очищаем БД
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # Останавливаем парсер если он запущен
    await stop_client(user_id)
    await event.respond(
        "🔄 Настройки сброшены и сессия удалена.\n"
        "Подождите 2-3 минуты и используйте /start для новой настройки."
    )

# В обработчиках будем получать target_chat_id из базы данных
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
            logger.error(f"Ошибка отправки сообщения: {e}")
            await bot.send_message(user_id, message)
            
    except Exception as e:
        logger.error(f"Ошибка при работе с БД: {e}")
        await bot.send_message(user_id, message)

async def message_handler(event, bot):
    user_id = event.sender_id
    message = event.message

    if user_id in user_states:
        state = user_states[user_id]
        
        if state == UserState.WAITING_API_ID:
            try:
                api_id = int(message.text)
                # Проверяем длину API_ID (обычно 7-8 цифр)
                if len(str(api_id)) > 10:
                    await event.respond("❌ API ID слишком длинный. API ID обычно состоит из 7-8 цифр. Проверьте и попробуйте снова:")
                    return
                if len(str(api_id)) < 5:
                    await event.respond("❌ API ID слишком короткий. API ID обычно состоит из 7-8 цифр. Проверьте и попробуйте снова:")
                    return
                    
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO users (user_id, api_id) VALUES (?, ?)", 
                         (user_id, int(api_id)))
                conn.commit()
                conn.close()
                
                user_states[user_id] = UserState.WAITING_API_HASH
                await event.respond("Отлично! Теперь отправьте API HASH:")
            except ValueError:
                await event.respond("❌ API ID должен быть числом. Попробуйте снова:")
                
        elif state == UserState.WAITING_API_HASH:
            if len(message.text) != 32:
                await event.respond("❌ API HASH должен быть 32 символа. Проверьте и попробуйте снова:")
                return
                
            # Проверяем формат API HASH (должен содержать только hex символы)
            if not all(c in '0123456789abcdef' for c in message.text.lower()):
                await event.respond("❌ API HASH должен содержать только шестнадцатеричные символы (0-9, a-f). Проверьте и попробуйте снова:")
                return
                
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE users SET api_hash = ? WHERE user_id = ?", 
                     (message.text, user_id))
            conn.commit()
            conn.close()
            
            user_states[user_id] = UserState.WAITING_PHONE
            await event.respond(
                "❗️ Убедитесь, что вы ввели правильные API ID и API HASH от своего приложения.\n\n"
                "Теперь отправьте номер телефона в международном формате:\n"
                "Например: +380995364081"
            )
            
        elif state == UserState.WAITING_PHONE:
            phone = message.text
            if not phone.startswith('+'):
                phone = '+' + phone
                
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE users SET phone = ? WHERE user_id = ?", 
                     (phone, user_id))
            conn.commit()
            conn.close()
            
            user_states[user_id] = UserState.WAITING_KEYWORDS
            # Убираем клавиатуру
            await event.respond(
                "Отлично! Теперь отправьте ключевые слова для поиска через запятую:", 
                buttons=ReplyKeyboardHide()
            )
            
        elif state == UserState.WAITING_KEYWORDS:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE users SET keywords = ? WHERE user_id = ?", 
                     (message.text, user_id))
            conn.commit()
            conn.close()
            
            del user_states[user_id]  # Удаляем состояние
            await event.respond("✅ Настройка завершена! Используйте /start для запуска парсера")
            
        elif state == UserState.EDIT_API_ID:
            try:
                api_id = int(message)
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute("UPDATE users SET api_id = ? WHERE user_id = ?", (api_id, user_id))
                conn.commit()
                conn.close()
                del user_states[user_id]
                await event.respond("✅ API ID успешно обновлен!")
            except ValueError:
                await event.respond("❌ API ID должен быть числом. Попробуйте снова:")
                
        elif state in [UserState.EDIT_API_HASH, UserState.EDIT_PHONE, UserState.EDIT_KEYWORDS]:
            field = {
                UserState.EDIT_API_HASH: 'api_hash',
                UserState.EDIT_PHONE: 'phone',
                UserState.EDIT_KEYWORDS: 'keywords'
            }[state]
            
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (message, user_id))
            conn.commit()
            conn.close()
            
            del user_states[user_id]
            await event.respond(f"✅ {field.replace('_', ' ').title()} успешно обновлен!")
            
        elif state == UserState.WAITING_CODE:
            try:
                print(f"\n📱 Получен код от пользователя {user_id}")
                
                # Получаем данные пользователя из БД
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute("SELECT api_id, api_hash, phone FROM users WHERE user_id = ?", (user_id,))
                user_data = c.fetchone()
                conn.close()
                
                if not user_data:
                    print("❌ Данные пользователя не найдены в БД")
                    await event.respond("❌ Ошибка: данные пользователя не найдены")
                    return
                    
                api_id, api_hash, phone = user_data
                print(f"📝 Загружены данные: API_ID={api_id}, HASH={api_hash[:8]}..., PHONE={phone}")
                
                code = message.text.strip()
                print(f"🔑 Проверяем код: {code}")

                phone_code_hash = phone_code_hashes.get(user_id)
                print(f"📨 Получен hash: {phone_code_hash[:8] if phone_code_hash else 'None'}")
                
                if not phone_code_hash:
                    print("⚠️ Hash не найден, отправляем новый код")
                    await event.respond("⌛️ Сессия истекла. Отправляю новый код...")
                    await start_client(user_id, api_id, api_hash, phone, "", bot)
                    return

                try:
                    print("🔐 Пытаемся войти...")
                    # Используем существующую сессию
                    client = TelegramClient(f'sessions/{user_id}', api_id, api_hash)
                    await client.connect()
                    
                    # Пытаемся войти с сохраненным хэшем
                    await client.sign_in(
                        phone=phone,
                        code=code,
                        phone_code_hash=phone_code_hash
                    )
                    
                    print("✅ Вход успешен!")
                    del phone_code_hashes[user_id]
                    del user_states[user_id]
                    
                    await event.respond(
                        "✅ Авторизация успешна!\n\n"
                        "Теперь введите /start чтобы запустить парсер или /settings чтобы проверить настройки."
                    )
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if "phone code invalid" in error_msg:
                        await event.respond(
                            "❌ Неверный код подтверждения.\n\n"
                            "Убедитесь, что вы вводите последний полученный код.\n"
                            "Попробуйте еще раз или используйте /start для новой попытки."
                        )
                    elif "flood" in error_msg or "banned" in error_msg:
                        await event.respond(
                            "⚠️ Telegram временно заблокировал попытки входа.\n\n"
                            "Это происходит для защиты аккаунта. Пожалуйста:\n"
                            "1. Подождите 15-30 минут\n"
                            "2. Используйте /start для новой попытки\n"
                            "3. Убедитесь, что вводите правильный код"
                        )
                    elif "was blocked" in error_msg:
                        await event.respond(
                            "⚠️ Telegram заблокировал вход для безопасности.\n\n"
                            "Пожалуйста:\n"
                            "1. Используйте /settings и нажмите 'Сбросить все настройки'\n"
                            "2. Подождите 2-3 минуты\n"
                            "3. Используйте /start для новой попытки"
                        )
                    else:
                        await event.respond(f"❌ Ошибка при авторизации: {str(e)}\nИспользуйте /start для новой попытки.")
                
                finally:
                    await client.disconnect()
                    
            except Exception as e:
                logger.error(f"Ошибка авторизации: {e}")
                await event.respond(f"❌ Произошла ошибка: {str(e)}")

# Добавим новый обработчик
async def settings_handler(event, bot):
    user_id = event.sender_id
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT api_id, api_hash, phone, keywords FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        api_id, api_hash, phone, keywords = user_data
        masked_hash = f"{api_hash[:8]}...{api_hash[-4:]}" if len(api_hash) > 12 else "не установлен"
        
        settings_text = "⚙️ Текущие настройки:\n\n"
        settings_text += f"📌 API ID: {api_id}\n"
        settings_text += f"🔑 API HASH: {masked_hash}\n"
        settings_text += f"📱 Телефон: {phone}\n"
        settings_text += f"🔍 Ключевые слова: {keywords}"
        
        # Добавляем кнопки для редактирования
        keyboard = [
            [Button.inline('📝 Изменить API ID', 'edit_api_id'),
             Button.inline('🔑 Изменить API HASH', 'edit_api_hash')],
            [Button.inline('📱 Изменить телефон', 'edit_phone'),
             Button.inline('🔍 Изменить ключевые слова', 'edit_keywords')],
            [Button.inline('🔄 Сбросить все настройки', 'reset_settings')]
        ]
        
        await event.respond(settings_text, buttons=keyboard)
    else:
        await event.respond("❌ Настройки не найдены. Используйте /start для настройки парсера")

# ... (остальные обработчики) 