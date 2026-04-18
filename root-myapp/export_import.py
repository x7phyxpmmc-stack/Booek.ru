import json
import sqlite3
from datetime import datetime
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

DATABASE = 'database.db'
EXPORT_DIR = 'static/exports'  # Папка для экспорта

# Создаём папку если её нет
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)


def export_to_json():
    """Экспорт в JSON"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # ЗАГОЛОВОК JSON
        data = {'title': 'Media Tracker Backup', 'export_date': datetime.now().isoformat()}
        
        # КАТЕГОРИИ
        cursor.execute("SELECT * FROM categories")
        data['categories'] = [dict(row) for row in cursor.fetchall()]
        
        # ЭЛЕМЕНТЫ
        cursor.execute("SELECT * FROM items_base")
        data['items'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        filename = f"mediatracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return json_data, filename
    except Exception as e:
        print(f"JSON Export Error: {str(e)}")
        return None, f"Ошибка JSON: {str(e)}"


def export_to_excel():
    """Экспорт в Excel с двумя вкладками: Статистика и Все элементы"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # СОЗДАЁМ НОВУЮ РАБОЧУЮ КНИГУ
        wb = openpyxl.Workbook()
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])
        
        # СТИЛИ
        header_fill = PatternFill(start_color='00D9FF', end_color='00D9FF', fill_type='solid')
        header_font = Font(bold=True, color='000000', size=12)
        
        # ==================== ВКЛАДКА 1: СТАТИСТИКА ====================
        ws_stats = wb.create_sheet('Статистика', 0)
        
        # Получаем статистику по категориям
        cursor.execute("""
            SELECT c.name, c.emoji, COUNT(ib.id) as count
            FROM categories c
            LEFT JOIN items_base ib ON c.id = ib.category_id
            GROUP BY c.id, c.name, c.emoji
            ORDER BY c.name
        """)
        stats_rows = cursor.fetchall()
        
        # Заголовок
        ws_stats.append(['Категория', 'Элементов'])
        for cell in ws_stats[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Данные статистики
        for row in stats_rows:
            name = f"{row['emoji']} {row['name']}" if row['emoji'] else row['name']
            count = row['count'] if row['count'] else 0
            ws_stats.append([name, count])
        
        # Ширина колонок
        ws_stats.column_dimensions['A'].width = 25
        ws_stats.column_dimensions['B'].width = 15
        
        
        # ==================== ВКЛАДКА 2: ВСЕ ЭЛЕМЕНТЫ ====================
        ws_items = wb.create_sheet('Все элементы', 1)
        
        # Получаем все элементы с их типами
        cursor.execute("""
            SELECT 
                ib.id,
                c.emoji,
                c.name as category,
                ib.title,
                ib.source_url
            FROM items_base ib
            JOIN categories c ON ib.category_id = c.id
            ORDER BY c.name, ib.title
        """)
        items_rows = cursor.fetchall()
        
        # Заголовок большой таблицы
        headers = ['№', 'Категория', 'Название', 'Тип', 'Статус', 'Дополнительно', 'Ссылка']
        ws_items.append(headers)
        
        for cell in ws_items[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Добавляем все элементы с их данными
        for idx, row in enumerate(items_rows, 1):
            item_id = row['id']
            category_name = f"{row['emoji']} {row['category']}" if row['emoji'] else row['category']
            title = row['title']
            source_url = row['source_url']
            
            # Получаем специфические данные в зависимости от типа
            item_type = 'Unknown'
            status = ''
            additional = ''
            
            # Проверяем каждый тип
            cursor.execute("SELECT anime_type, episodes, rewatches, status, watched_episodes FROM items_anime WHERE item_id = ?", (item_id,))
            anime_data = cursor.fetchone()
            if anime_data:
                item_type = 'Аниме'
                anime_type, episodes, rewatches, status, watched = anime_data
                additional = f"Тип: {anime_type} | Эпизодов: {episodes} | Просмотрено: {watched}/{episodes} | Пересмотров: {rewatches}"
            
            cursor.execute("SELECT manga_type, chapters, rerereads, status, read_chapters FROM items_manga WHERE item_id = ?", (item_id,))
            manga_data = cursor.fetchone()
            if manga_data:
                item_type = 'Манга'
                manga_type, chapters, rerereads, status, read = manga_data
                additional = f"Тип: {manga_type} | Глав: {chapters} | Прочитано: {read}/{chapters} | Перечитываний: {rerereads}"
            
            cursor.execute("SELECT duration, rewatches, status FROM items_films WHERE item_id = ?", (item_id,))
            films_data = cursor.fetchone()
            if films_data:
                item_type = 'Фильм'
                duration, rewatches, status = films_data
                additional = f"Длина: {duration} мин | Пересмотров: {rewatches}"
            
            cursor.execute("SELECT episodes, episode_duration, rewatches, status, watched_episodes FROM items_series WHERE item_id = ?", (item_id,))
            series_data = cursor.fetchone()
            if series_data:
                item_type = 'Сериал'
                episodes, ep_dur, rewatches, status, watched = series_data
                additional = f"Эпизодов: {episodes}×{ep_dur}м | Просмотрено: {watched}/{episodes} | Пересмотров: {rewatches}"
            
            cursor.execute("SELECT book_type, pages_duration, hours_reading, rerereads, status, pages_read FROM items_books WHERE item_id = ?", (item_id,))
            books_data = cursor.fetchone()
            if books_data:
                item_type = 'Книга'
                book_type, pages_dur, hours_read, rerereads, status, pages_read = books_data
                if book_type == 'аудиокнига':
                    additional = f"Аудиокнига | {pages_dur}ч | Прослушано: {pages_read}ч | Перечитываний: {rerereads}"
                else:
                    additional = f"Книга | Страниц: {pages_dur} | Прочитано: {pages_read} | Перечитываний: {rerereads}"
            
            cursor.execute("SELECT hours, status FROM items_games WHERE item_id = ?", (item_id,))
            games_data = cursor.fetchone()
            if games_data:
                item_type = 'Игра'
                game_hours, status = games_data
                additional = f"Часов сыграно: {game_hours}"
            
            # Добавляем строку в таблицу
            ws_items.append([idx, category_name, title, item_type, status, additional, source_url])
        
        # Форматирование таблицы элементов
        for row in ws_items.iter_rows(min_row=2, max_row=ws_items.max_row):
            for cell in row:
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        # Ширина колонок для таблицы элементов
        ws_items.column_dimensions['A'].width = 6
        ws_items.column_dimensions['B'].width = 18
        ws_items.column_dimensions['C'].width = 25
        ws_items.column_dimensions['D'].width = 12
        ws_items.column_dimensions['E'].width = 15
        ws_items.column_dimensions['F'].width = 50
        ws_items.column_dimensions['G'].width = 40
        
        # Высота строк для лучшей видимости
        ws_items.row_dimensions[1].height = 25
        for row_num in range(2, ws_items.max_row + 1):
            ws_items.row_dimensions[row_num].height = 45
        
        conn.close()
        
        # СОХРАНЯЕМ В ПАПКУ ПРОЕКТА
        filename = f"mediatracker_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(EXPORT_DIR, filename)
        wb.save(filepath)
        
        print(f"✅ Excel file created: {filepath}")
        return filepath, filename
        
    except Exception as e:
        print(f"Excel Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Ошибка Excel: {str(e)}"


def import_from_json(json_data, mode='merge'):
    """Импорт из JSON (mode: 'merge' - объединить, 'replace' - заменить)"""
    try:
        data = json.loads(json_data)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # РЕЖИМ REPLACE - очищаем базу
        if mode == 'replace':
            cursor.execute("DELETE FROM items_base")
            cursor.execute("DELETE FROM categories")
            cursor.execute("DELETE FROM sqlite_sequence")
            conn.commit()
        
        # ИМПОРТИРУЕМ КАТЕГОРИИ
        if 'categories' in data:
            for cat in data['categories']:
                cursor.execute(
                    "INSERT OR REPLACE INTO categories (id, name, type, emoji) VALUES (?, ?, ?, ?)",
                    (cat.get('id'), cat.get('name'), cat.get('type'), cat.get('emoji'))
                )
        
        # ИМПОРТИРУЕМ ЭЛЕМЕНТЫ
        if 'items' in data:
            for item in data['items']:
                cursor.execute(
                    "INSERT OR REPLACE INTO items_base (id, category_id, title, cover_image, cover_source, source_url) VALUES (?, ?, ?, ?, ?, ?)",
                    (item.get('id'), item.get('category_id'), item.get('title'), 
                     item.get('cover_image'), item.get('cover_source'), item.get('source_url'))
                )
        
        conn.commit()
        conn.close()
        
        return True, "Данные успешно импортированы!"
    except Exception as e:
        print(f"Import Error: {str(e)}")
        return False, f"Ошибка импорта: {str(e)}"
