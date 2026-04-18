import sqlite3

DB_PATH = 'database.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Команды - некоторые могут выдать ошибку "column already exists" - это OK
commands = [
    "ALTER TABLE items_anime ADD COLUMN rewatches INTEGER DEFAULT 0;",
    "ALTER TABLE items_anime ADD COLUMN watched_episodes INTEGER DEFAULT 0;",
    "ALTER TABLE items_manga ADD COLUMN rerereads INTEGER DEFAULT 0;",
    "ALTER TABLE items_manga ADD COLUMN read_chapters INTEGER DEFAULT 0;",
    "ALTER TABLE items_films ADD COLUMN rewatches INTEGER DEFAULT 0;",
    "ALTER TABLE items_series ADD COLUMN rewatches INTEGER DEFAULT 0;",
    "ALTER TABLE items_series ADD COLUMN watched_episodes INTEGER DEFAULT 0;",
    "ALTER TABLE items_books ADD COLUMN rerereads INTEGER DEFAULT 0;",
    "ALTER TABLE items_books ADD COLUMN pages_read INTEGER DEFAULT 0;",
]

for cmd in commands:
    try:
        c.execute(cmd)
        print(f"✅ {cmd[:50]}...")
    except Exception as e:
        print(f"⚠️ {cmd[:50]}... - {str(e)}")

conn.commit()
conn.close()
print("✅ Миграция завершена!")
