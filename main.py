import telebot
from telethon import TelegramClient, events
import asyncio
import os
from dotenv import load_dotenv
import logging
import threading
import signal

# Настройка базового логирования
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(message)s',
                   datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# API данные для Telethon
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID чата, куда будут пересылаться сообщения
DESTINATION_CHAT_ID = "-1002322331895"

# Инициализация ботов
bot = telebot.TeleBot(BOT_TOKEN)
client = TelegramClient('user_session', API_ID, API_HASH)

# Проверяем чат при инициализации
try:
    chat_info = bot.get_chat(DESTINATION_CHAT_ID)
    logger.info(f"Целевой чат найден: {chat_info.title} (ID: {chat_info.id})")
except Exception as e:
    logger.error(f"Ошибка при проверке чата: {e}")
    logger.error("Бот не сможет отправлять сообщения. Проверьте ID чата")
    exit(1)

# Расширенный список ключевых слов
KEYWORDS = [
    # Массаж
    'массаж', 'massage', 'масаж', 'массажист', 'массажистка',
]

# Флаг для отслеживания завершения
running = True

def signal_handler(sig, frame):
    """Обработчик сигнала завершения"""
    global running
    logger.info("\n🛑 Получен сигнал завершения. Закрываем соединения...")
    running = False

@client.on(events.NewMessage(chats=None))
async def handler(event):
    try:
        # Логируем все сообщения
        chat = await event.get_chat()
        sender = await event.get_sender()
        message = event.message.text if event.message.text else ''
        
        logger.info(f"👀 Новое сообщение в чате '{chat.title}':")
        logger.info(f"📝 Текст: {message}")
        
        # Проверяем наличие ключевых слов
        if any(keyword in message.lower() for keyword in KEYWORDS):
            # Формируем текст для пересылки
            forward_text = f"🔍 Найдено новое сообщение!\n\n"
            forward_text += f"💬 Чат: {chat.title}\n"
            
            # Добавляем информацию об отправителе
            sender_info = []
            if hasattr(sender, 'first_name') and sender.first_name:
                sender_info.append(sender.first_name)
            if hasattr(sender, 'last_name') and sender.last_name:
                sender_info.append(sender.last_name)
            if hasattr(sender, 'username') and sender.username:
                sender_info.append(f"@{sender.username}")
            
            forward_text += f"👤 Отправитель: {' '.join(sender_info)}\n"
            forward_text += f"📝 Сообщение:\n{message}\n"
            
            # Добавляем ссылки
            if hasattr(chat, 'username') and chat.username:
                forward_text += f"\n🔗 Ссылка на чат: https://t.me/{chat.username}"
            if hasattr(sender, 'username') and sender.username:
                forward_text += f"\n👤 Профиль: https://t.me/{sender.username}"
            
            # Добавляем найденные ключевые слова
            found_keywords = [kw for kw in KEYWORDS if kw in message.lower()]
            forward_text += f"\n\n🔑 Ключевые слова: {', '.join(found_keywords)}"
            
            # Отправляем через telebot
            bot.send_message(DESTINATION_CHAT_ID, forward_text)
            logger.info(f"✅ Сообщение с ключевыми словами переслано")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сообщения: {e}")

async def main():
    # Регистрируем обработчик Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    await client.start()
    
    if await client.is_user_authorized():
        logger.info("Клиент успешно авторизован")
        bot.send_message(DESTINATION_CHAT_ID, "🤖 Бот запущен и готов к работе!")
        logger.info("Тестовое сообщение отправлено успешно")
    else:
        logger.error("Ошибка авторизации клиента")
        return

    try:
        logger.info("✅ Бот успешно запущен. Для завершения нажмите Ctrl+C")
        while running:
            await asyncio.sleep(1)
    finally:
        # Корректно закрываем соединения
        await client.disconnect()
        bot.stop_polling()
        logger.info("👋 Бот успешно остановлен")

if __name__ == '__main__':
    logger.info("Запуск мониторинга...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
