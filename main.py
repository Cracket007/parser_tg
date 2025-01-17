from telethon import TelegramClient, events
import asyncio
import os
from dotenv import load_dotenv
import logging
from database import init_db
from handlers import *
import signal
import sqlite3

# Настройка логирования
logging.basicConfig(
    level=logging.WARNING,  # Меняем с INFO на WARNING чтобы убрать сообщения о подключении
    format='%(message)s'    # Упрощаем формат вывода
)
logger = logging.getLogger(__name__)

# Загружаем токен бота
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

async def get_bot_credentials():
    """Получаем учетные данные бота из базы данных"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT api_id, api_hash FROM bot_credentials LIMIT 1")
    creds = c.fetchone()
    conn.close()
    
    if not creds:
        raise ValueError("Bot credentials not found in database!")
    return int(creds[0]), creds[1]

# Создаем клиент бота
bot = None  # Инициализируем позже

# Флаг для отслеживания состояния работы
running = True

def signal_handler(sig, frame):
    global running
    logger.info("\n⌛️ Получен сигнал завершения, останавливаем бота...")
    running = False

async def stop_all_clients():
    """Останавливаем все активные клиенты"""
    for user_id in list(active_clients.keys()):
        await stop_client(user_id)
    logger.info("✅ Все клиенты остановлены")

def register_handlers(bot):
    # Добавляем обработчик обычных сообщений
    bot.add_event_handler(lambda e: message_handler(e, bot), events.NewMessage)
    
    # Остальные обработчики
    bot.add_event_handler(lambda e: start_handler(e, bot), events.NewMessage(pattern='/start'))
    bot.add_event_handler(lambda e: help_handler(e, bot), events.NewMessage(pattern='/help'))
    bot.add_event_handler(lambda e: id_handler(e, bot), events.NewMessage(pattern='/id'))
    bot.add_event_handler(lambda e: stop_handler(e, bot), events.NewMessage(pattern='/stop'))
    bot.add_event_handler(lambda e: stats_handler(e, bot), events.NewMessage(pattern='/stats'))
    bot.add_event_handler(lambda e: setchat_handler(e, bot), events.NewMessage(pattern='/setchat'))
    bot.add_event_handler(lambda e: callback_handler(e, bot), events.CallbackQuery())
    bot.add_event_handler(lambda e: settings_handler(e, bot), events.NewMessage(pattern='/settings'))

async def main():
    # Регистрируем обработчик сигнала
    signal.signal(signal.SIGINT, signal_handler)
    
    init_db()
    
    # Получаем учетные данные и создаем бота
    global bot
    api_id, api_hash = await get_bot_credentials()
    bot = TelegramClient('bot', api_id, api_hash)
    
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    
    # Запускаем бота с токеном
    await bot.start(bot_token=BOT_TOKEN)
    register_handlers(bot)
    
    logger.info("✅ Бот успешно запущен")
    
    try:
        while running:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        # Корректное завершение
        await stop_all_clients()
        await bot.disconnect()
        logger.info("👋 Бот успешно остановлен")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
