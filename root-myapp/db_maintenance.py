# ========================================================================
# DATABASE MAINTENANCE SCRIPT
# Регулярное обслуживание базы данных Media Tracker
# ========================================================================
#
# ИСПОЛЬЗОВАНИЕ:
# 1. Сохраните этот файл как `db_maintenance.py` в корне проекта
# 2. Запускайте периодически:
#    python db_maintenance.py
#
# РЕКОМЕНДАЦИЯ: Запускайте раз в месяц или после удаления большого количества элементов
# 🧹 Полная очистка БД (удалит осиротевшие записи)
#python db_maintenance.py
#
# 🏥 Только проверка без удаления
#python db_maintenance.py check
# ========================================================================

import sqlite3
from datetime import datetime

DATABASE = 'database.db'

def cleanup_all_orphans():
    """Удаляет осиротевшие записи из ВСЕХ таблиц типов"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 80)
    print(f"🧹 DATABASE MAINTENANCE [{timestamp}]")
    print("=" * 80)

    # Все таблицы типов контента
    type_tables = [
        'items_anime',
        'items_manga',
        'items_films',
        'items_series',
        'items_books',
        'items_games'
    ]

    total_deleted = 0

    for table in type_tables:
        print(f"\n📋 Checking {table}...")

        # Находим осиротевшие записи
        cursor.execute(f"""
            SELECT ib.id, ib.item_id
            FROM {table} ib
            LEFT JOIN items_base base ON ib.item_id = base.id
            WHERE base.id IS NULL
        """)

        orphans = cursor.fetchall()

        if orphans:
            print(f"  ❌ Found {len(orphans)} orphan record(s):")

            for orphan in orphans:
                record_id, item_id = orphan
                print(f"     - {table}.id={record_id}, item_id={item_id}")

            # Удаляем
            for orphan in orphans:
                record_id = orphan[0]
                cursor.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))

            conn.commit()
            print(f"  ✅ Deleted {len(orphans)} record(s)")
            total_deleted += len(orphans)
        else:
            print(f"  ✅ No orphans found")

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("📊 DATABASE STATISTICS:")
    print("=" * 80)

    stats = {}
    for table in type_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(DISTINCT item_id) FROM {table}")
        unique = cursor.fetchone()[0]

        status = "✅" if total == unique else "⚠️"
        print(f"{status} {table:20} | Total: {total:3} | Unique: {unique:3}")

        stats[table] = {'total': total, 'unique': unique}

    # Общая статистика
    print("\n" + "-" * 80)
    cursor.execute("SELECT COUNT(*) FROM items_base")
    base_count = cursor.fetchone()[0]
    print(f"📚 items_base total items: {base_count}")

    cursor.execute("SELECT COUNT(*) FROM categories")
    cat_count = cursor.fetchone()[0]
    print(f"📁 Total categories: {cat_count}")

    conn.close()

    # Итоги
    print("\n" + "=" * 80)
    if total_deleted > 0:
        print(f"🎉 MAINTENANCE COMPLETE!")
        print(f"   {total_deleted} orphan record(s) deleted")
    else:
        print(f"✅ DATABASE IS CLEAN!")
        print(f"   No orphan records found")
    print(f"📅 Completed at: {timestamp}")
    print("=" * 80 + "\n")


def check_database_health():
    """Быстрая проверка здоровья БД без очистки"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("🏥 DATABASE HEALTH CHECK")
    print("=" * 80)

    type_tables = [
        'items_anime',
        'items_manga',
        'items_films',
        'items_series',
        'items_books',
        'items_games'
    ]

    issues = 0

    for table in type_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(DISTINCT item_id) FROM {table}")
        unique = cursor.fetchone()[0]

        if total > unique:
            status = "⚠️ ISSUES"
            issues += 1
        else:
            status = "✅ OK"

        print(f"{status} {table:20} | Total: {total:3} | Unique: {unique:3}")

    conn.close()

    print("\n" + "=" * 80)
    if issues > 0:
        print(f"⚠️  Found {issues} table(s) with issues!")
        print(f"   Run: python db_maintenance.py")
    else:
        print(f"✅ Database is healthy!")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        check_database_health()
    else:
        cleanup_all_orphans()
