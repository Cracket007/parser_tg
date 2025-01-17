@echo off
echo Установка бота для мониторинга...

rem Создаем .env файл
echo API_ID=ДРУГА_API_ID > .env
echo API_HASH=ДРУГА_API_HASH >> .env
echo BOT_TOKEN=ВАШ_БОТ_ТОКЕН >> .env
echo DESTINATION_CHAT_ID=ВАШ_ЧАТ_ID >> .env

rem Устанавливаем зависимости
pip install -r requirements.txt

echo Установка завершена!
echo Для запуска бота используйте: python main.py
pause 