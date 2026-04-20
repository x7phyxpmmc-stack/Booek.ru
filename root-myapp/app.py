from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
import sqlite3
from functools import wraps
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import hmac
import hashlib
from io import BytesIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
app = Flask(__name__)
import re

@app.template_filter('remove_emoji')
def remove_emoji(text):
    """Убирает эмодзи из начала названия"""
    if not text:
        return text
    # Удаляем эмодзи только в начале (1-2 символа)
    return re.sub(r'^[\U0001F300-\U0001F9FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251🎬📖🎥📺📚🎮📦]{1,2}\s*', '', text)

app.secret_key = 'media-tracker-secret-key-2025'

# Rate Limiter для защиты от брутфорса
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[]
)

# Конфигурация безопасной сессии
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,  # XSS защита: недоступно для JS
    SESSION_COOKIE_SAMESITE='Strict',  # CSRF защита
    PERMANENT_SESSION_LIFETIME=2592000  # 30 дней в секундах
)

@app.after_request
def set_security_headers(response):
    """Добавляет безопасность заголовки"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' https: data:;"
    )
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    """Обработчик Rate Limit ошибки"""
    return render_template(
        'login.html',
        error='⏱️ Слишком много попыток входа. Попробуйте позже (через 15 минут).',
        csrf_token=secrets.token_hex(32)
    ), 429

DB_PATH = 'database.db'
UPLOAD_FOLDER = '/var/www/myapp_static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024

# PIN-код вход
SITE_PIN = "132666"  # 🔴 ИЗМЕНИ НА СВОЙ 6-ЗНАЧНЫЙ PIN!


# Пароль сайта (защищён от XSS и SQL инъекций через сессии и хеширование)
SITE_PASSWORD_HASH = generate_password_hash('X2iI7brp1DW0GCo_6KSa')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ========================================================================
# ЧАСОВЫЕ ФУНКЦИИ (АВТОВЫЧИСЛЕНИЯ) - ИСПРАВЛЕННЫЕ ДЛЯ ПОВТОРНЫХ ПРОХОЖДЕНИЙ
# ========================================================================

def calc_hours_anime(episodes, anime_type, rewatches, status, watched_episodes):
    """
    Аниме: учитываем rewatches (повторные просмотры)
    - rewatches = 0 → просмотрено один раз
    - rewatches = 1 → просмотрено два раза (оригинальный + 1 повтор)
    - watched_episodes для статуса 'не досмотрел'
    """
    if status == 'просмотрено':
        ep_dur = 20 if anime_type == 'сериал' else 6
        # Всего: оригинальный просмотр + повторные просмотры
        total_episodes = episodes * (1 + rewatches)
        return round((total_episodes * ep_dur) / 60, 1)
    elif status == 'не досмотрел' and watched_episodes > 0:
        ep_dur = 20 if anime_type == 'сериал' else 6
        return round((watched_episodes * ep_dur) / 60, 1)
    return 0

def calc_hours_manga(chapters, rerereads, status, read_chapters):
    """
    Манга: учитываем rerereads (повторные прочтения)
    - rerereads = 0 → прочитано один раз
    - rerereads = 1 → прочитано два раза (оригинальное + 1 повтор)
    - read_chapters для статуса 'не дочитал'
    """
    if status == 'прочитано':
        # Всего: оригинальное прочтение + повторные прочтения
        total_chapters = chapters * (1 + rerereads)
        return round((total_chapters * 5) / 60, 1)
    elif status == 'не дочитал' and read_chapters > 0:
        return round((read_chapters * 5) / 60, 1)
    return 0

def calc_hours_films(duration, rewatches, status):
    """
    Фильмы: учитываем rewatches (повторные просмотры)
    - rewatches = 0 → просмотрено один раз
    - rewatches = 1 → просмотрено два раза (оригинальный + 1 повтор)
    """
    if status == 'просмотрено':
        # Всего: оригинальный просмотр + повторные просмотры
        total_duration = duration * (1 + rewatches)
        return round(total_duration / 60, 1)
    return 0

def calc_hours_series(episodes, ep_dur, rewatches, status, watched_episodes):
    """
    Сериалы: учитываем rewatches (повторные просмотры)
    - rewatches = 0 → просмотрено один раз
    - rewatches = 1 → просмотрено два раза (оригинальный + 1 повтор)
    - watched_episodes для статуса 'не досмотрел'
    """
    if status == 'просмотрено':
        # Всего: оригинальный просмотр + повторные просмотры
        total_episodes = episodes * (1 + rewatches)
        total_minutes = total_episodes * ep_dur
        return round(total_minutes / 60, 1)
    elif status == 'не досмотрел' and watched_episodes > 0:
        return round((watched_episodes * ep_dur) / 60, 1)
    return 0

def calc_hours_books(book_type, pages_dur, hours_reading, rerereads, status, pages_read):
    """
    Книги: учитываем rerereads (повторные прочтения)
    - rerereads = 0 → прочитано один раз
    - rerereads = 1 → прочитано два раза (оригинальное + 1 повтор)
    - Для статуса 'прочитано': часы = hours_reading * (1 + rerereads)
    - Для статуса 'не дочитал': пропорция по прочитанным страницам
    - Для аудиокниг: используется ТОЛЬКО hours_reading, pages_dur игнорируется
    """
    if status == 'прочитано':
        # Всего: оригинальное прочтение + повторные прочтения
        total_hours = hours_reading * (1 + rerereads)
        return round(total_hours, 1)
    elif status == 'не дочитал' and pages_read > 0:
        # Для недочитанных - пропорция: (прочитано/всего) * часы
        if pages_dur > 0 and hours_reading > 0:
            return round((pages_read / pages_dur) * hours_reading, 1)
        elif hours_reading > 0:
            # Если pages_dur неизвестен, но есть часы - используем часы как есть
            return round(hours_reading, 1)
    return 0

def calc_hours_games(hours, status):
    """Игры: часы считаются всегда, независимо от статуса (БЕЗ повторных прохождений)"""
    return hours

# ========================================================================
# СТАТИСТИКА ПО ТИПАМ (ИСПРАВЛЕННАЯ)
# ========================================================================

def get_type_statistics():
    """Возвращает статистику по типам для каждой категории"""
    conn = get_db()
    type_stats = {}

    # ANIME TYPES: сериал, фильм
    anime_data = conn.execute(
        'SELECT items_anime.anime_type FROM items_anime GROUP BY items_anime.anime_type'
    ).fetchall()
    type_stats['anime'] = []
    for row in anime_data:
        anime_type = row[0]
        items = conn.execute(
            'SELECT DISTINCT items_anime.item_id FROM items_anime WHERE items_anime.anime_type = ?',
            (anime_type,)
        ).fetchall()
        total_hours = 0
        for item in items:
            full_item = get_item_full(item['item_id'])
            if full_item:
                total_hours += calc_item_hours(full_item)
        type_stats['anime'].append({
            'type': anime_type,
            'count': len(items),
            'hours': round(total_hours, 1)
        })

    # MANGA TYPES: манга, манхва, маньхуа
    manga_data = conn.execute(
        'SELECT items_manga.manga_type FROM items_manga GROUP BY items_manga.manga_type'
    ).fetchall()
    type_stats['manga'] = []
    for row in manga_data:
        manga_type = row[0]
        items = conn.execute(
            'SELECT DISTINCT items_manga.item_id FROM items_manga WHERE items_manga.manga_type = ?',
            (manga_type,)
        ).fetchall()
        total_hours = 0
        for item in items:
            full_item = get_item_full(item['item_id'])
            if full_item:
                total_hours += calc_item_hours(full_item)
        type_stats['manga'].append({
            'type': manga_type,
            'count': len(items),
            'hours': round(total_hours, 1)
        })

    # BOOK TYPES: бумажная, аудиокнига, электронная
    book_data = conn.execute(
        'SELECT items_books.book_type FROM items_books GROUP BY items_books.book_type'
    ).fetchall()
    type_stats['books'] = []
    for row in book_data:
        book_type = row[0]
        items = conn.execute(
            'SELECT DISTINCT items_books.item_id FROM items_books WHERE items_books.book_type = ?',
            (book_type,)
        ).fetchall()
        total_hours = 0
        for item in items:
            full_item = get_item_full(item['item_id'])
            if full_item:
                total_hours += calc_item_hours(full_item)
        type_stats['books'].append({
            'type': book_type,
            'count': len(items),
            'hours': round(total_hours, 1)
        })

    # FILMS TYPES (если есть несколько типов фильмов)
    films_data = conn.execute(
        'SELECT COUNT(DISTINCT item_id) as count FROM items_films'
    ).fetchall()
    if films_data[0][0] > 0:
        type_stats['films'] = [{
            'type': 'фильм',
            'count': films_data[0][0],
            'hours': 0  # Можно добавить расчёт часов если нужно
        }]

    # SERIES TYPES (если есть несколько типов сериалов)
    series_data = conn.execute(
        'SELECT COUNT(DISTINCT item_id) as count FROM items_series'
    ).fetchall()
    if series_data[0][0] > 0:
        type_stats['series'] = [{
            'type': 'сериал',
            'count': series_data[0][0],
            'hours': 0  # Можно добавить расчёт часов если нужно
        }]

    # GAMES TYPES
    games_data = conn.execute(
        'SELECT COUNT(DISTINCT item_id) as count FROM items_games'
    ).fetchall()
    if games_data[0][0] > 0:
        type_stats['games'] = [{
            'type': 'игра',
            'count': games_data[0][0],
            'hours': 0
        }]

    conn.close()
    return type_stats

# ========================================================================
# БАЗОВЫЕ ФУНКЦИИ
# ========================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def auth_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if 'authenticated' not in session or not session['authenticated']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return dec

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    if file and allowed_file(file.filename):
        if file.content_length > MAX_FILE_SIZE:
            return None
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return filename
    return None

def delete_file(filename):
    if filename:
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(path):
            os.remove(path)

def get_item_full(item_id):
    conn = get_db()
    base = conn.execute('SELECT * FROM items_base WHERE id = ?', (item_id,)).fetchone()
    if not base:
        conn.close()
        return None

    cat = conn.execute('SELECT * FROM categories WHERE id = ?', (base['category_id'],)).fetchone()

    if cat['type'] == 'anime':
        data = conn.execute('SELECT * FROM items_anime WHERE item_id = ?', (item_id,)).fetchone()
    elif cat['type'] == 'manga':
        data = conn.execute('SELECT * FROM items_manga WHERE item_id = ?', (item_id,)).fetchone()
    elif cat['type'] == 'films':
        data = conn.execute('SELECT * FROM items_films WHERE item_id = ?', (item_id,)).fetchone()
    elif cat['type'] == 'series':
        data = conn.execute('SELECT * FROM items_series WHERE item_id = ?', (item_id,)).fetchone()
    elif cat['type'] == 'books':
        data = conn.execute('SELECT * FROM items_books WHERE item_id = ?', (item_id,)).fetchone()
    elif cat['type'] == 'games':
        data = conn.execute('SELECT * FROM items_games WHERE item_id = ?', (item_id,)).fetchone()
    else:
        data = None

    conn.close()

    if not data:
        return None

    return {'base': base, 'type': cat['type'], 'cat': cat, 'data': data}

def calc_item_hours(item):
    if not item or not item.get('data'):
        return 0

    t = item['type']
    d = item['data']

    if t == 'anime':
        return calc_hours_anime(d['episodes'], d['anime_type'], d['rewatches'], d['status'], d['watched_episodes'])
    elif t == 'manga':
        return calc_hours_manga(d['chapters'], d['rerereads'], d['status'], d['read_chapters'])
    elif t == 'films':
        return calc_hours_films(d['duration'], d['rewatches'], d['status'])
    elif t == 'series':
        return calc_hours_series(d['episodes'], d['episode_duration'], d['rewatches'], d['status'], d['watched_episodes'])
    elif t == 'books':
        return calc_hours_books(d['book_type'], d['pages_duration'], d['hours_reading'], d['rerereads'], d['status'], d['pages_read'])
    elif t == 'games':
        return calc_hours_games(d['hours'], d['status'])
    return 0

# ========================================================================
# AUTH
# ========================================================================

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes")
def login():
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        csrf_token = request.form.get('csrf_token', '')
        
        if not csrf_token or csrf_token != session.get('csrf_token'):
            new_token = secrets.token_hex(32)
            session['csrf_token'] = new_token
            return render_template('login.html', error='Ошибка безопасности', csrf_token=new_token)
        
        if not pin or len(pin) != 6 or not pin.isdigit():
            new_token = secrets.token_hex(32)
            session['csrf_token'] = new_token
            return render_template('login.html', error='PIN должен быть 6 цифр', csrf_token=new_token)
        
        if pin == SITE_PIN:
            session['authenticated'] = True
            session.permanent = True
            session.pop('csrf_token', None)
            return redirect(url_for('dashboard'))
        else:
            new_token = secrets.token_hex(32)
            session['csrf_token'] = new_token
            return render_template('login.html', error='Неверный PIN', csrf_token=new_token)
    
    csrf_token = secrets.token_hex(32)
    session['csrf_token'] = csrf_token
    session.permanent = True
    return render_template('login.html', csrf_token=csrf_token)


    # GET запрос
    csrf_token = secrets.token_hex(32)
    session['csrf_token'] = csrf_token
    session.permanent = True
    return render_template('login.html', csrf_token=csrf_token)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ========================================================================
# DASHBOARD & STATS
# ========================================================================

def get_status_statistics():
    """Статистика по статусам для каждой категории"""
    conn = get_db()
    result = {}

    queries = {
        'anime':  ('SELECT status, COUNT(*) as cnt FROM items_anime GROUP BY status', 'status'),
        'manga':  ('SELECT status, COUNT(*) as cnt FROM items_manga GROUP BY status', 'status'),
        'films':  ('SELECT status, COUNT(*) as cnt FROM items_films GROUP BY status', 'status'),
        'series': ('SELECT status, COUNT(*) as cnt FROM items_series GROUP BY status', 'status'),
        'books':  ('SELECT status, COUNT(*) as cnt FROM items_books GROUP BY status', 'status'),
        'games':  ('SELECT status, COUNT(*) as cnt FROM items_games GROUP BY status', 'status'),
    }

    for key, (sql, _) in queries.items():
        try:
            rows = conn.execute(sql).fetchall()
            result[key] = [{'status': r['status'], 'count': r['cnt']} for r in rows]
        except Exception:
            result[key] = []

    conn.close()
    return result


def get_progress_stats():
    """Общий прогресс: завершено / в процессе / в планах / брошено.
    Используем параметризацию через ? — нет SQL-ошибок с одиночным значением."""
    conn = get_db()

    # Группы статусов задаются как списки Python
    DONE_STATUSES     = ['просмотрено', 'прочитано', 'прошёл целиком']
    PROGRESS_STATUSES = ['смотрю', 'читаю', 'играю']
    PLANNED_STATUSES  = ['планирую']
    DROPPED_STATUSES  = ['не досмотрел', 'не дочитал', 'прошёл частично']

    TABLES = ['items_anime', 'items_manga', 'items_films',
              'items_series', 'items_books', 'items_games']

    counts = {'done': 0, 'in_progress': 0, 'planned': 0, 'dropped': 0}

    for table in TABLES:
        for key, statuses in [('done', DONE_STATUSES), ('in_progress', PROGRESS_STATUSES),
                               ('planned', PLANNED_STATUSES), ('dropped', DROPPED_STATUSES)]:
            try:
                placeholders = ', '.join('?' * len(statuses))
                sql = f'SELECT COUNT(*) FROM {table} WHERE status IN ({placeholders})'
                r = conn.execute(sql, statuses).fetchone()
                counts[key] += r[0] if r else 0
            except Exception:
                pass

    conn.close()
    return counts


def get_recent_items(limit=6):
    """Возвращает последние добавленные записи (по убыванию id)"""
    conn = get_db()
    recent_base = conn.execute(
        'SELECT id FROM items_base ORDER BY id DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()

    result = []
    for row in recent_base:
        item = get_item_full(row['id'])
        if item:
            # Определяем статус записи
            status = ''
            d = item['data']
            t = item['type']
            if t == 'anime':
                status = d['status']
            elif t == 'manga':
                status = d['status']
            elif t == 'films':
                status = d['status']
            elif t == 'series':
                status = d['status']
            elif t == 'books':
                status = d['status']
            elif t == 'games':
                status = d['status']

            result.append({
                'base': item['base'],
                'type': t,
                'cat_name': item['cat']['name'],
                'status': status,
                'hours': round(calc_item_hours(item), 1)
            })
    return result


def get_top_category(categories_stats):
    """Возвращает топ-категорию по часам"""
    if not categories_stats:
        return None
    top = max(categories_stats, key=lambda x: x['hours'])
    return {
        'name': top['category']['name'],
        'hours': top['hours'],
        'count': top['count']
    }


@app.route('/')
@auth_required
def dashboard():
    conn = get_db()
    cats = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    stats = []
    total_h = 0
    total_i = 0
    for cat in cats:
        items = conn.execute('SELECT id FROM items_base WHERE category_id = ?', (cat['id'],)).fetchall()
        h = sum(calc_item_hours(get_item_full(i['id'])) for i in items)
        total_h += h
        total_i += len(items)
        stats.append({'category': cat, 'count': len(items), 'hours': round(h, 1)})
    conn.close()

    recent_items = get_recent_items(6)
    top_category = get_top_category(stats)

    return render_template(
        'dashboard.html',
        categories=stats,
        total_hours=round(total_h, 1),
        total_items=total_i,
        recent_items=recent_items,
        top_category=top_category,
        sidebar_categories=stats
    )

@app.route('/statistics')
@auth_required
def statistics():
    conn = get_db()
    cats = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    stats = []
    total_h = 0
    total_i = 0
    for cat in cats:
        items = conn.execute('SELECT id FROM items_base WHERE category_id = ?', (cat['id'],)).fetchall()
        h = sum(calc_item_hours(get_item_full(i['id'])) for i in items)
        total_h += h
        total_i += len(items)
        stats.append({'category': cat, 'count': len(items), 'hours': round(h, 1)})
    conn.close()

    type_statistics    = get_type_statistics()
    status_statistics  = get_status_statistics()
    progress_stats     = get_progress_stats()

    return render_template(
        'statistics.html',
        categories=stats,
        total_hours=round(total_h, 1),
        total_items=total_i,
        type_statistics=type_statistics,
        status_statistics=status_statistics,
        progress_stats=progress_stats,
        sidebar_categories=stats
    )

# ========================================================================
# CATEGORY VIEW
# ========================================================================

@app.route('/category/<int:category_id>')
@auth_required
def view_category(category_id):
    conn = get_db()
    cat = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
    if not cat:
        conn.close()
        return redirect(url_for('dashboard'))

    items_base = conn.execute('SELECT * FROM items_base WHERE category_id = ? ORDER BY title', (category_id,)).fetchall()

    items_with_data = []
    total_hours_cat = 0
    for ib in items_base:
        item = get_item_full(ib['id'])
        if item:
            hours = calc_item_hours(item)
            total_hours_cat += hours
            items_with_data.append({
                'base': ib,
                'type': item['type'],
                'data': item['data'],
                'hours': round(hours, 1)
            })
    conn.close()

    # Sidebar categories
    conn2 = get_db()
    all_cats = conn2.execute('SELECT * FROM categories ORDER BY name').fetchall()
    sidebar_stats = []
    for c in all_cats:
        cnt = conn2.execute('SELECT COUNT(*) FROM items_base WHERE category_id = ?', (c['id'],)).fetchone()[0]
        sidebar_stats.append({'category': c, 'count': cnt, 'hours': 0})
    conn2.close()

    return render_template(
        'category.html',
        category=cat,
        items=items_with_data,
        stats={'total_items': len(items_with_data), 'total_hours': round(total_hours_cat, 1)},
        sidebar_categories=sidebar_stats
    )

# ========================================================================
# ADD ITEM (6 типов) - ИСПРАВЛЕННАЯ ВЕРСИЯ (ПРАВИЛЬНЫЙ ORDER)
# ========================================================================

@app.route('/add/anime', methods=['GET', 'POST'])
@auth_required
def add_anime():
    return add_item('anime')

@app.route('/add/manga', methods=['GET', 'POST'])
@auth_required
def add_manga():
    return add_item('manga')

@app.route('/add/films', methods=['GET', 'POST'])
@auth_required
def add_films():
    return add_item('films')

@app.route('/add/series', methods=['GET', 'POST'])
@auth_required
def add_series():
    return add_item('series')

@app.route('/add/books', methods=['GET', 'POST'])
@auth_required
def add_books():
    return add_item('books')

@app.route('/add/games', methods=['GET', 'POST'])
@auth_required
def add_games():
    return add_item('games')

def add_item(cat_type):
    conn = get_db()
    cat = conn.execute('SELECT * FROM categories WHERE type = ?', (cat_type,)).fetchone()
    conn.close()

    if not cat:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        cover_file = request.files.get('cover_image')
        cover_url = request.form.get('cover_url', '').strip()
        source_url = request.form.get('source_url', '').strip()

        cover_image = None
        cover_source = None

        if cover_file and cover_file.filename:
            cover_image = save_file(cover_file)
            cover_source = 'upload' if cover_image else None
        elif cover_url:
            cover_image = cover_url
            cover_source = 'url'

        conn = get_db()
        c = conn.cursor()

        c.execute(
            'INSERT INTO items_base (category_id, title, cover_image, cover_source, source_url) VALUES (?, ?, ?, ?, ?)',
            (cat['id'], title, cover_image, cover_source, source_url if source_url else None)
        )
        conn.commit()
        item_id = c.lastrowid

        if cat_type == 'anime':
            episodes = int(request.form.get('episodes', 0) or 0)
            anime_type = request.form.get('anime_type', 'сериал')
            status = request.form.get('status', 'планирую')
            # ВАЖНО: Порядок как в CREATE TABLE!
            c.execute(
                'INSERT INTO items_anime (item_id, episodes, anime_type, rewatches, status, watched_episodes) VALUES (?, ?, ?, ?, ?, ?)',
                (item_id, episodes, anime_type, 0, status, 0)
            )

        elif cat_type == 'manga':
            chapters = int(request.form.get('chapters', 0) or 0)
            manga_type = request.form.get('manga_type', 'манга')
            status = request.form.get('status', 'планирую')
            # ВАЖНО: Порядок как в CREATE TABLE!
            c.execute(
                'INSERT INTO items_manga (item_id, chapters, manga_type, rerereads, status, read_chapters) VALUES (?, ?, ?, ?, ?, ?)',
                (item_id, chapters, manga_type, 0, status, 0)
            )

        elif cat_type == 'films':
            duration = int(request.form.get('duration', 0) or 0)
            status = request.form.get('status', 'планирую')
            # ВАЖНО: Порядок как в CREATE TABLE!
            c.execute(
                'INSERT INTO items_films (item_id, duration, rewatches, status) VALUES (?, ?, ?, ?)',
                (item_id, duration, 0, status)
            )

        elif cat_type == 'series':
            episodes = int(request.form.get('episodes', 0) or 0)
            ep_dur = int(request.form.get('episode_duration', 0) or 0)
            status = request.form.get('status', 'планирую')
            # ВАЖНО: Порядок как в CREATE TABLE!
            c.execute(
                'INSERT INTO items_series (item_id, episodes, episode_duration, rewatches, status, watched_episodes) VALUES (?, ?, ?, ?, ?, ?)',
                (item_id, episodes, ep_dur, 0, status, 0)
            )

        elif cat_type == 'books':
            book_type = request.form.get('book_type', 'бумажная')
            pages_dur = int(request.form.get('pages_duration', 0) or 0)
            hours = float(request.form.get('hours_reading', 0) or 0)
            status = request.form.get('status', 'планирую')
            # ВАЖНО: Порядок как в CREATE TABLE!
            c.execute(
                'INSERT INTO items_books (item_id, book_type, pages_duration, hours_reading, rerereads, status, pages_read) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (item_id, book_type, pages_dur, hours, 0, status, 0)
            )

        elif cat_type == 'games':
            hours = int(request.form.get('hours', 0) or 0)
            status = request.form.get('status', 'планирую')
            c.execute(
                'INSERT INTO items_games (item_id, hours, status) VALUES (?, ?, ?)',
                (item_id, hours, status)
            )

        conn.commit()
        conn.close()

        return redirect(url_for('view_category', category_id=cat['id']))

    # Sidebar
    conn3 = get_db()
    all_cats3 = conn3.execute('SELECT * FROM categories ORDER BY name').fetchall()
    sb3 = []
    for c in all_cats3:
        cnt = conn3.execute('SELECT COUNT(*) FROM items_base WHERE category_id = ?', (c['id'],)).fetchone()[0]
        sb3.append({'category': c, 'count': cnt, 'hours': 0})
    conn3.close()
    return render_template(f'add_{cat_type}.html', category=cat, sidebar_categories=sb3)

# ========================================================================
# EDIT ITEM - ПОЛНАЯ ВЕРСИЯ С REWATCHES/REREREADS
# ========================================================================

@app.route('/edit/anime/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_anime(item_id):
    return edit_item(item_id)

@app.route('/edit/manga/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_manga(item_id):
    return edit_item(item_id)

@app.route('/edit/films/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_films(item_id):
    return edit_item(item_id)

@app.route('/edit/series/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_series(item_id):
    return edit_item(item_id)

@app.route('/edit/books/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_books(item_id):
    return edit_item(item_id)

@app.route('/edit/games/<int:item_id>', methods=['GET', 'POST'])
@auth_required
def edit_games(item_id):
    return edit_item(item_id)

def edit_item(item_id):
    item = get_item_full(item_id)
    if not item:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        cover_file = request.files.get('cover_image')
        cover_url = request.form.get('cover_url', '').strip()
        source_url = request.form.get('source_url', '').strip()

        cover_image = item['base']['cover_image']
        cover_source = item['base']['cover_source']

        if cover_file and cover_file.filename:
            if item['base']['cover_image'] and item['base']['cover_source'] == 'upload':
                delete_file(item['base']['cover_image'])
            cover_image = save_file(cover_file)
            cover_source = 'upload'
        elif cover_url:
            if item['base']['cover_image'] and item['base']['cover_source'] == 'upload':
                delete_file(item['base']['cover_image'])
            cover_image = cover_url
            cover_source = 'url'

        conn = get_db()
        c = conn.cursor()

        c.execute(
            'UPDATE items_base SET title = ?, cover_image = ?, cover_source = ?, source_url = ? WHERE id = ?',
            (title, cover_image, cover_source, source_url if source_url else None, item_id)
        )

        cat_type = item['type']

        if cat_type == 'anime':
            episodes = int(request.form.get('episodes', 0) or 0)
            anime_type = request.form.get('anime_type')
            rewatches = int(request.form.get('rewatches', 0) or 0)
            status = request.form.get('status')
            # ИСПРАВКА: watched_episodes сохраняется при "не досмотрел", иначе = 0
            watched = int(request.form.get('watched_episodes', 0) or 0) if status == 'не досмотрел' else 0
            c.execute(
                'UPDATE items_anime SET episodes = ?, anime_type = ?, rewatches = ?, status = ?, watched_episodes = ? WHERE item_id = ?',
                (episodes, anime_type, rewatches, status, watched, item_id)
            )

        elif cat_type == 'manga':
            chapters = int(request.form.get('chapters', 0) or 0)
            manga_type = request.form.get('manga_type')
            rerereads = int(request.form.get('rerereads', 0) or 0)
            status = request.form.get('status')
            # ИСПРАВКА: read_chapters сохраняется при "не дочитал", иначе = 0
            read = int(request.form.get('read_chapters', 0) or 0) if status == 'не дочитал' else 0
            c.execute(
                'UPDATE items_manga SET chapters = ?, manga_type = ?, rerereads = ?, status = ?, read_chapters = ? WHERE item_id = ?',
                (chapters, manga_type, rerereads, status, read, item_id)
            )

        elif cat_type == 'films':
            duration = int(request.form.get('duration', 0) or 0)
            rewatches = int(request.form.get('rewatches', 0) or 0)
            status = request.form.get('status')
            c.execute(
                'UPDATE items_films SET duration = ?, rewatches = ?, status = ? WHERE item_id = ?',
                (duration, rewatches, status, item_id)
            )

        elif cat_type == 'series':
            episodes = int(request.form.get('episodes', 0) or 0)
            ep_dur = int(request.form.get('episode_duration', 0) or 0)
            rewatches = int(request.form.get('rewatches', 0) or 0)
            status = request.form.get('status')
            # ИСПРАВКА: watched_episodes сохраняется при "не досмотрел", иначе = 0
            watched = int(request.form.get('watched_episodes', 0) or 0) if status == 'не досмотрел' else 0
            c.execute(
                'UPDATE items_series SET episodes = ?, episode_duration = ?, rewatches = ?, status = ?, watched_episodes = ? WHERE item_id = ?',
                (episodes, ep_dur, rewatches, status, watched, item_id)
            )

        elif cat_type == 'books':
            book_type = request.form.get('book_type')
            pages_dur = int(request.form.get('pages_duration', 0) or 0)
            hours = float(request.form.get('hours_reading', 0) or 0)
            rerereads = int(request.form.get('rerereads', 0) or 0)
            status = request.form.get('status')
            # ИСПРАВКА: pages_read сохраняется при "не дочитал", иначе = 0
            pages = int(request.form.get('pages_read', 0) or 0) if status == 'не дочитал' else 0
            c.execute(
                'UPDATE items_books SET book_type = ?, pages_duration = ?, hours_reading = ?, rerereads = ?, status = ?, pages_read = ? WHERE item_id = ?',
                (book_type, pages_dur, hours, rerereads, status, pages, item_id)
            )

        elif cat_type == 'games':
            hours = int(request.form.get('hours', 0) or 0)
            status = request.form.get('status')
            c.execute(
                'UPDATE items_games SET hours = ?, status = ? WHERE item_id = ?',
                (hours, status, item_id)
            )

        conn.commit()
        conn.close()

        return redirect(url_for('view_category', category_id=item['base']['category_id']))

    # Sidebar
    conn4 = get_db()
    all_cats4 = conn4.execute('SELECT * FROM categories ORDER BY name').fetchall()
    sb4 = []
    for c in all_cats4:
        cnt = conn4.execute('SELECT COUNT(*) FROM items_base WHERE category_id = ?', (c['id'],)).fetchone()[0]
        sb4.append({'category': c, 'count': cnt, 'hours': 0})
    conn4.close()
    return render_template(f'edit_{item["type"]}.html', item=item, sidebar_categories=sb4)

# ========================================================================
# AJAX: БЫСТРОЕ ОБНОВЛЕНИЕ СТАТУСА (НОВОЕ!)
# ========================================================================

@app.route('/api/update_partial_watched', methods=['POST'])
@auth_required
def update_partial_watched():
    """AJAX endpoint для быстрого обновления статуса 'не досмотрел' с количеством серий"""
    data = request.get_json()
    item_id = data.get('item_id')
    watched_episodes = int(data.get('watched_episodes', 0))

    if not item_id or watched_episodes <= 0:
        return jsonify({'success': False, 'error': 'Неверные данные'}), 400

    item = get_item_full(item_id)
    if not item:
        return jsonify({'success': False, 'error': 'Запись не найдена'}), 404

    cat_type = item['type']
    
    # Поддерживаем только типы с watched_episodes/read_chapters/pages_read
    if cat_type not in ['anime', 'manga', 'series', 'books']:
        return jsonify({'success': False, 'error': 'Этот тип не поддерживает частичный просмотр'}), 400

    conn = get_db()
    c = conn.cursor()

    try:
        if cat_type == 'anime':
            c.execute(
                'UPDATE items_anime SET status = ?, watched_episodes = ? WHERE item_id = ?',
                ('не досмотрел', watched_episodes, item_id)
            )
        elif cat_type == 'manga':
            c.execute(
                'UPDATE items_manga SET status = ?, read_chapters = ? WHERE item_id = ?',
                ('не дочитал', watched_episodes, item_id)
            )
        elif cat_type == 'series':
            c.execute(
                'UPDATE items_series SET status = ?, watched_episodes = ? WHERE item_id = ?',
                ('не досмотрел', watched_episodes, item_id)
            )
        elif cat_type == 'books':
            c.execute(
                'UPDATE items_books SET status = ?, pages_read = ? WHERE item_id = ?',
                ('не дочитал', watched_episodes, item_id)
            )
        
        conn.commit()
        
        # Пересчитываем часы для обновления в ответе
        updated_item = get_item_full(item_id)
        hours = calc_item_hours(updated_item)
        
        return jsonify({
            'success': True,
            'hours': round(hours, 1),
            'status': 'не досмотрел' if cat_type in ['anime', 'series'] else 'не дочитал'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ========================================================================
# DELETE
# ========================================================================

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@auth_required
def delete_item(item_id):
    item = get_item_full(item_id)
    if not item:
        return redirect(url_for('dashboard'))

    cat_id = item['base']['category_id']
    cat_type = item['type']

    # Удаляем файл изображения если есть
    if item['base']['cover_image'] and item['base']['cover_source'] == 'upload':
        delete_file(item['base']['cover_image'])

    conn = get_db()
    c = conn.cursor()

    # Удаляем запись из основной таблицы
    c.execute('DELETE FROM items_base WHERE id = ?', (item_id,))

    # Удаляем запись из специальной таблицы в зависимости от типа
    if cat_type == 'anime':
        c.execute('DELETE FROM items_anime WHERE item_id = ?', (item_id,))
    elif cat_type == 'manga':
        c.execute('DELETE FROM items_manga WHERE item_id = ?', (item_id,))
    elif cat_type == 'films':
        c.execute('DELETE FROM items_films WHERE item_id = ?', (item_id,))
    elif cat_type == 'series':
        c.execute('DELETE FROM items_series WHERE item_id = ?', (item_id,))
    elif cat_type == 'books':
        c.execute('DELETE FROM items_books WHERE item_id = ?', (item_id,))
    elif cat_type == 'games':
        c.execute('DELETE FROM items_games WHERE item_id = ?', (item_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('view_category', category_id=cat_id))

# ========================================================================
# ИМПОРТ/ЭКСПОРТ (ленивый импорт openpyxl)
# ========================================================================


@app.route('/export/json')
@auth_required
def export_json():
    """Экспортирует данные в JSON для резервного копирования"""
    from export_import import export_to_json
    json_data, filename = export_to_json()
    if json_data is None:
        flash('Ошибка при экспорте', 'error')
        return redirect(url_for('statistics'))
    json_bytes = json_data.encode('utf-8')
    return send_file(
        BytesIO(json_bytes),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )

@app.route('/export/excel')
@auth_required
def export_excel():
    """Экспортирует медиатеку в Excel (листы по категориям + сводка)."""
    from export_import import export_to_excel
    try:
        buf, filename = export_to_excel()
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Ошибка при экспорте: {str(e)}', 'error')
        return redirect(url_for('statistics'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
