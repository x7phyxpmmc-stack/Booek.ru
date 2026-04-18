import sqlite3

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Таблица категорий
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT,
            type TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Базовая таблица элементов (общие поля для всех)
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            cover_image TEXT,
            cover_source TEXT,
            source_url TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # Таблица аниме
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            episodes INTEGER DEFAULT 0,
            anime_type TEXT DEFAULT 'сериал',
            rewatches INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            watched_episodes INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    # Таблица манги
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_manga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            chapters INTEGER DEFAULT 0,
            manga_type TEXT DEFAULT 'манга',
            rerereads INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            read_chapters INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    # Таблица фильмов
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            duration INTEGER DEFAULT 0,
            rewatches INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    # Таблица сериалов
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            episodes INTEGER DEFAULT 0,
            episode_duration INTEGER DEFAULT 45,
            rewatches INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            watched_episodes INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    # Таблица книг
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            book_type TEXT DEFAULT 'бумажная',
            pages_duration INTEGER DEFAULT 0,
            hours_reading REAL DEFAULT 0,
            rerereads INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            pages_read INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    # Таблица игр
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER UNIQUE NOT NULL,
            hours INTEGER DEFAULT 0,
            status TEXT DEFAULT 'планирую',
            FOREIGN KEY (item_id) REFERENCES items_base(id)
        )
    ''')
    
    conn.commit()
    
    # Проверяем есть ли категории
    cat_count = c.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
    if cat_count == 0:
        categories = [
            ('anime', '📺 Аниме'),
            ('manga', '📖 Манга'),
            ('films', '🎬 Фильмы'),
            ('series', '📺 Сериалы'),
            ('books', '📚 Книги'),
            ('games', '🎮 Игры')
        ]
        
        for cat_type, cat_name in categories:
            c.execute(
                'INSERT INTO categories (name, emoji, type) VALUES (?, ?, ?)',
                (cat_name, cat_name[0], cat_type)
            )
        
        conn.commit()
        print("✅ БД инициализирована!")
    else:
        print("✅ БД уже инициализирована")
    
    conn.close()

if __name__ == '__main__':
    init_db()
