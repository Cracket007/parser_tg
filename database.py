import sqlite3

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Таблица для пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  api_id TEXT,
                  api_hash TEXT,
                  phone TEXT,
                  keywords TEXT,
                  is_active BOOLEAN DEFAULT 0,
                  messages_found INTEGER DEFAULT 0,
                  last_active TEXT,
                  target_chat_id TEXT)''')
                  
    # Таблица для учетных данных бота
    c.execute('''CREATE TABLE IF NOT EXISTS bot_credentials
                 (id INTEGER PRIMARY KEY,
                  api_id TEXT NOT NULL,
                  api_hash TEXT NOT NULL)''')
                  
    # Проверяем, есть ли учетные данные бота
    c.execute("SELECT COUNT(*) FROM bot_credentials")
    if c.fetchone()[0] == 0:
        # Добавляем учетные данные бота
        c.execute("INSERT INTO bot_credentials (api_id, api_hash) VALUES (?, ?)",
                 ('26493983', '3373346fb1d3f1ba06e77f00b28138ca'))
    
    conn.commit()
    conn.close() 