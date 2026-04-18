import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(__file__))

# Импортируем приложение
from app import app

# Если в app.py есть if __name__ == '__main__', нужен WSGI:
if __name__ == "__main__":
    app.run()
