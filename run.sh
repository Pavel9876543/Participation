#!/bin/bash
#
# Скрипт запуска Flask-проекта:
# - освобождает порт 5000
# - очищает Python-кэш
# - запускает сервер
# - открывает сайт в браузере
#

PORT=5000
URL="http://127.0.0.1:$PORT"

echo "▶ Проверка порта $PORT..."

# Освобождение порта, если занят
PID=$(lsof -ti tcp:$PORT)
if [ -n "$PID" ]; then
  echo "⚠ Порт $PORT занят процессом $PID. Завершаю..."
  kill -9 $PID
  sleep 1
else
  echo "✓ Порт свободен"
fi

echo "▶ Очистка Python-кэша..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

echo "✓ Кэш очищен"

echo "▶ Запуск Flask-приложения..."

# Запуск сервера в фоне
python app.py &

# Небольшая пауза, чтобы сервер успел подняться
sleep 2

echo "▶ Открытие браузера: $URL"

# Linux
if command -v xdg-open > /dev/null; then
  xdg-open $URL
# macOS
elif command -v open > /dev/null; then
  open $URL
else
  echo "⚠ Не удалось автоматически открыть браузер"
fi

echo "✓ Проект запущен"
