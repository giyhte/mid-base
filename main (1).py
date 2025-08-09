import telebot
import sqlite3
from telebot import types
from datetime import datetime, timedelta
import os
from banner_generator import get_role_banner_file, get_role_banner_url

BOT_TOKEN = "8363145008:AAGpk3nkNYzTMFpQ0Ve--aOhxPYFWyp5EGg"
OWNER_IDS = [7537570296, 5821123636]

DB_PATH = "bot_database.db"

# Проверяем валидность токена перед созданием бота
if not BOT_TOKEN or len(BOT_TOKEN.split(':')) != 2:
    print("❌ Неверный формат токена бота!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
chats = set()

# Словарь для отслеживания последних предупреждений о скамерах в чатах
scammer_warnings = {}

import time

def get_connection():
    """Создает подключение к SQLite базе данных"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        raise e

def init_db():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"Попытка инициализации БД {attempt + 1}/{max_retries}...")
            conn = get_connection()
            cursor = conn.cursor()

            # Создаем таблицу пользователей
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                role TEXT DEFAULT 'непроверенный',
                scam_percent TEXT DEFAULT '50%'
            )""")

            # Создаем таблицу для username
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS usernames (
                user_id TEXT PRIMARY KEY,
                username TEXT
            )""")

            # Создаем таблицу для чатов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_chats (
                chat_id TEXT PRIMARY KEY,
                chat_title TEXT,
                chat_type TEXT,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

            # Создаем таблицу для прав пользователей на команды
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                command_name TEXT,
                has_permission INTEGER DEFAULT 1,
                granted_by TEXT,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, command_name)
            )""")

            # Создаем таблицу для отслеживания предупреждений о скамерах
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scammer_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                user_id TEXT,
                last_warning TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, user_id)
            )""")

            # Создаем таблицу для отслеживания проверок пользователей
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                verified_by TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )""")

            # Создаем таблицу для счетчика просмотров профилей
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_views (
                user_id TEXT PRIMARY KEY,
                view_count INTEGER DEFAULT 0
            )""")

            # Создаем таблицу для биографий пользователей
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_bios (
                user_id TEXT PRIMARY KEY,
                bio TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

            conn.commit()
            cursor.close()
            conn.close()
            print("✅ База данных успешно инициализирована!")
            return
        except Exception as e:
            print(f"Ошибка при создании таблицы (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print("❌ Не удалось инициализировать базу данных после всех попыток")

init_db()

def get_risk(user_id):
    """Получает процент риска пользователя"""
    try:
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "0%"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role, scam_percent FROM users WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()

        if result:
            role, scam_percent = result['role'], result['scam_percent']
            cursor.close()
            conn.close()

            # Если есть кастомный процент, используем его
            if scam_percent and scam_percent != "50%":
                return scam_percent
            # Иначе используем стандартный для роли
            risks = {
                "владелец": "0%",
                "гарант": "0%",
                "владелец чата": "10%",
                "проверенный": "10%",
                "отказ от гаранта": "80%",
                "скамер": "100%",
                "непроверенный": "50%"
            }
            return risks.get(role, "50%")
        else:
            cursor.close()
            conn.close()
            return "50%"
    except Exception as e:
        print(f"Ошибка при получении риска для {user_id}: {e}")
        return "50%"

def get_role(user_id):
    """Получает роль пользователя из базы данных"""
    try:
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "владелец"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return result['role'] if result and result['role'] else "непроверенный"
    except Exception as e:
        print(f"Ошибка при получении роли для {user_id}: {e}")
        return "непроверенный"

def get_verification_info(user_id):
    """Получает информацию о том, кто проверил пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT verified_by, verified_at FROM user_verifications WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return {
                'verified_by': result['verified_by'],
                'verified_at': result['verified_at']
            }
        return None
    except Exception as e:
        print(f"Ошибка при получении информации о проверке для {user_id}: {e}")
        return None

def increment_profile_views(user_id):
    """Увеличивает счетчик просмотров профиля пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO profile_views (user_id, view_count)
            VALUES (?, COALESCE((SELECT view_count FROM profile_views WHERE user_id = ?), 0) + 1)
        """, (str(user_id), str(user_id)))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при увеличении счетчика просмотров для {user_id}: {e}")

def get_profile_views(user_id):
    """Получает количество просмотров профиля пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT view_count FROM profile_views WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['view_count'] if result else 0
    except Exception as e:
        print(f"Ошибка при получении счетчика просмотров для {user_id}: {e}")
        return 0

def get_user_bio(user_id):
    """Получает биографию пользователя из базы данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bio FROM user_bios WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['bio'] if result else None
    except Exception as e:
        print(f"Ошибка при получении биографии для {user_id}: {e}")
        return None

@bot.message_handler(commands=["start"])
def start_command(msg):
    # Проверяем, есть ли параметр для показа профиля
    if len(msg.text.split()) > 1 and msg.text.split()[1].startswith("profile_"):
        user_id = msg.text.split()[1].replace("profile_", "")
        show_detailed_profile(msg, user_id)
    else:
        bot.reply_to(msg, "👋 Привет! Я активен. Используй /help, чтобы увидеть доступные команды.")

def show_detailed_profile(msg, user_id):
    """Показывает детальный профиль пользователя"""
    try:
        # Получаем актуальную информацию о пользователе
        user_info = None
        try:
            user_info = bot.get_chat(int(user_id))
        except Exception as api_error:
            print(f"Не удалось получить данные пользователя через API для {user_id}: {api_error}")
            # Пытаемся найти username в нашей базе, если API не работает
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM usernames WHERE user_id = ?", (str(user_id),))
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                if result and result['username']:
                    # Создаем простой объект с нужными атрибутами
                    class UserInfo:
                        def __init__(self, user_id, username):
                            self.id = int(user_id)
                            self.username = username
                            self.first_name = "Неизвестный"
                    
                    user_info = UserInfo(user_id, result['username'])
            except:
                pass

        if not user_info:
            bot.send_message(msg.chat.id, f"❌ Не удалось найти информацию о пользователе с ID <code>{user_id}</code>.")
            return

        user_name = user_info.first_name or "Неизвестный пользователь"
        username_display = f"@{user_info.username}" if hasattr(user_info, 'username') and user_info.username else "Не указан"

        # Получаем роль, риск и информацию о проверке
        role = get_role(user_id)
        risk = get_risk(user_id)
        verification_info = get_verification_info(user_id)

        # Определяем текстовое представление роли и эмодзи риска
        status_emoji = get_status_emoji(role)
        status_name = get_status_name(role)
        risk_color = get_risk_color(risk)

        # Получаем биографию пользователя
        user_bio = get_user_bio(user_id)
        bio_text = user_bio if user_bio else "Биография не установлена. /bio"

        # Получаем время проверки
        check_time = datetime.now().strftime('%H:%M МСК • %d %B')

        # Определяем текст проверяющего
        verified_by_text = "Не проверен"
        if verification_info:
            try:
                verifier_chat = bot.get_chat(int(verification_info['verified_by']))
                verifier_name = verifier_chat.username or verifier_chat.first_name
                verifier_username = f"@{verifier_name}" if verifier_chat.username else verifier_name
                verified_by_text = f"Проверен гарантом {verifier_username}"
            except:
                verified_by_text = f"Проверен гарантом ID: {verification_info['verified_by']}"

        text = (
            f"ℹ️ | {user_name} | <code>{user_id}</code>\n"
            f"🗓 | Дата проверки: {check_time}\n\n"
            f"{status_emoji} | Статус: {status_name} |\n"
            f"{risk_color} | Процент скама: {risk} |\n"
            f"{verified_by_text}\n\n"
            f"📝 | О себе: {bio_text}\n\n"
            f"👤 | Профиль: <a href='tg://user?id={user_id}'>{user_name}</a>"
        )

        # Увеличиваем счетчик просмотров профиля
        increment_profile_views(user_id)
        views_count = get_profile_views(user_id)
        text += f"       👁️ {views_count}\n"
        text += f"📅 Последняя активность: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Создаем кнопку "Профиль"
        markup = types.InlineKeyboardMarkup()
        profile_button = types.InlineKeyboardButton(
            "📋 Подробный профиль",
            url=f"https://t.me/{bot.get_me().username}?start=profile_{user_id}"
        )
        markup.add(profile_button)

        # Добавляем баннер в текст через HTML ссылку
        banner_url = get_role_banner_url(role)
        if banner_url:
            text += f'\n<a href="{banner_url}">&#8203;</a>'

        # Отправляем сообщение с встроенным баннером
        try:
            bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка при отправке сообщения: {e}")
            try:
                bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
            except:
                bot.send_message(msg.chat.id, "❌ Ошибка при отображении профиля")

    except Exception as e:
        print(f"Критическая ошибка при отображении профиля {user_id}: {e}")
        error_text = (
            f"❌ <b>ОШИБКА ЗАГРУЗКИ ПРОФИЛЯ</b>\n\n"
            f"Не удалось получить детальную информацию о пользователе <code>{user_id}</code>\n\n"
            f"<b>Возможные причины:</b>\n"
            f"• Пользователь заблокировал бота\n"
            f"• Пользователь удалил аккаунт\n"
            f"• Проблемы с соединением"
        )
        bot.send_message(msg.chat.id, error_text)

def get_user_groups(user_id):
    """Получает список групп где есть и пользователь и бот"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM bot_chats WHERE chat_type IN ('group', 'supergroup')")
        bot_groups = cursor.fetchall()
        cursor.close()
        conn.close()

        user_groups = []
        for row in bot_groups:
            chat_id, chat_title = row['chat_id'], row['chat_title']
            try:
                # Проверяем, есть ли пользователь в этой группе
                member = bot.get_chat_member(int(chat_id), int(user_id))
                if member.status in ['member', 'administrator', 'creator']:
                    # Получаем актуальную информацию о группе
                    try:
                        chat_info = bot.get_chat(int(chat_id))
                        actual_title = chat_info.title or chat_title or f"Группа {chat_id}"
                        # Обновляем информацию в базе если изменилась
                        if chat_info.title and chat_info.title != chat_title:
                            save_chat_to_db(chat_id, chat_info.title, chat_info.type)
                    except:
                        actual_title = chat_title or f"Группа {chat_id}"

                    user_groups.append({
                        'chat_id': chat_id,
                        'title': actual_title
                    })
            except Exception as check_error:
                # Если не можем проверить участие, возможно пользователь покинул группу
                print(f"Не удалось проверить участие пользователя {user_id} в группе {chat_id}: {check_error}")
                continue

        return user_groups
    except Exception as e:
        print(f"Ошибка при получении групп пользователя {user_id}: {e}")
        return []

@bot.message_handler(commands=["help"])
def help_command(msg):
    user_id = msg.from_user.id

    # Базовые команды доступные всем
    text = (
        "📘 <b>Доступные команды:</b>\n"
        "— чек (в ответ на сообщение, без параметров или @username)\n"
        "— гаранты (показать всех гарантов)\n"
    )

    # Проверяем доступность каждой команды для пользователя
    if has_command_permission(user_id, "занести"):
        text += "— занести роль (в ответ на сообщение или @username роль)\n"

    if has_command_permission(user_id, "вынести"):
        text += "— вынести (в ответ на сообщение или @username)\n"

    if has_command_permission(user_id, "ип"):
        text += "— ип 30 (в ответ на сообщение)\n"

    # Команда проверки для гарантов и владельцев
    user_role = get_role(user_id)
    if user_role in ["гарант", "владелец чата", "владелец"] or user_id in OWNER_IDS:
        text += "— проверен (в ответ на сообщение или @username) — отметить как проверенного\n"

    # Команды только для владельцев
    if user_id in OWNER_IDS:
        text += "— +кмд команда (в ответ на сообщение) — выдать права\n"
        text += "— -кмд команда (в ответ на сообщение) — отнять права\n"
        text += "— /гс (текст сообщения) — отправить глобальное сообщение во все чаты\n"
        text += "— /чаты — посмотреть список активных чатов\n"
        text += "— сетка_бан (для команды сетка бан)\n"

    text += (
        "\nСпециальные права заноса:\n"
        "— заносить_скамер, заносить_гарант, заносить_владелец_чата\n"
        "— заносить_отказ, заносить_проверенный\n"
        "— сетка_бан (для команды сетка бан)\n"
    )

    text += (
        "\nДоступные роли: скамер, гарант, владелец_чата, проверенный, отказ_от_гаранта\n"
        "\nПримеры с username:\n"
        "— чек @username\n"
        "— занести @username проверенный\n"
        "— вынести @username\n"
        "— проверен @username\n"
        "\nБот активен и работает ✅"
    )

    bot.reply_to(msg, text)

def get_user_by_username(username):
    """Сохраняет username в базе данных для последующего поиска по ID"""
    try:
        # Убираем @ если он есть
        username = username.lstrip('@')

        # Пытаемся найти пользователя через разные методы
        user_info = None

        # Метод 1: Прямой поиск через API
        try:
            user_info = bot.get_chat(f"@{username}")
        except:
            pass

        # Если не найден, возвращаем None
        if user_info is None:
            return None

        return user_info
    except Exception as e:
        print(f"Ошибка при получении пользователя по username {username}: {e}")
        return None

def save_username_mapping(user_id, username):
    """Сохраняет связь user_id -> username в базе данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Сохраняем или обновляем username
        cursor.execute(
            "INSERT OR REPLACE INTO usernames (user_id, username) VALUES (?, ?)",
            (str(user_id), username)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении username для {user_id}: {e}")

def find_user_by_username(username):
    """Ищет пользователя по username в базе данных"""
    try:
        username = username.lstrip('@')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM usernames WHERE username = ?", (username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['user_id'] if result else None
    except Exception as e:
        print(f"Ошибка при поиске username {username} в БД: {e}")
        return None

def has_command_permission(user_id, command_name):
    """Проверяет, есть ли у пользователя право на выполнение команды"""
    try:
        # Владельцы всегда имеют все права
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return True

        # Конвертируем все в строки для избежания проблем с кодировкой
        user_id_str = str(user_id)
        command_name_str = str(command_name)

        # Сначала проверяем явно выданные права в базе данных
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT has_permission FROM user_permissions WHERE user_id = ? AND command_name = ?",
            (user_id_str, command_name_str)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        # Если найдена явная запись о правах, используем её
        if result is not None:
            return bool(result['has_permission'])

        # Если явных прав нет, проверяем права по роли (только для базовых команд)
        role = get_role(user_id)
        if role in ["гарант", "владелец чата"] and command_name_str in ["занести", "вынести"]:
            return True

        # Владельцы имеют право на команду "ип" по умолчанию
        if role == "владелец" and command_name_str == "ип":
            return True

        # Если нет ни явных прав, ни прав по роли - отказываем
        return False

    except Exception as e:
        print(f"Ошибка при проверке прав для {user_id}, команда {command_name}: {e}")
        return False

def grant_command_permission(user_id, command_name, granted_by, has_permission=True):
    """Выдает или отнимает право на команду у пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_permissions (user_id, command_name, has_permission, granted_by, granted_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (str(user_id), command_name, int(has_permission), str(granted_by)))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при изменении прав для {user_id}, команда {command_name}: {e}")
        return False

def get_status_emoji(role):
    """Получает эмодзи для статуса"""
    status_emojis = {
        "владелец": "👑",
        "гарант": "🛡️",
        "владелец чата": "⭐",
        "проверенный": "✅",
        "отказ от гаранта": "⚠️",
        "скамер": "🚫",
        "непроверенный": "❓"
    }
    return status_emojis.get(role, "❓")

def get_status_name(role):
    """Преобразует роль в статус"""
    status_names = {
        "владелец": "Владелец",
        "гарант": "Гарант",
        "владелец чата": "Владелец чата",
        "проверенный": "Проверенный",
        "отказ от гаранта": "Отказ от гаранта",
        "скамер": "Скамер",
        "непроверенный": "Непроверенный"
    }
    return status_names.get(role, "Непроверенный")

def get_risk_color(risk):
    """Получает цветовой индикатор для риска"""
    if risk == "0%":
        return "🟢"
    elif risk in ["10%", "20%"]:
        return "🟡"
    elif risk in ["50%"]:
        return "🟠"
    elif risk in ["80%", "100%"]:
        return "🔴"
    else:
        return "⚪"

def get_role_banner_url(role):
    """Возвращает URL ссылку на баннер для каждой роли"""
    banners = {
        "владелец": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",  # Ваша ссылка для владельца
        "гарант": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",  # Замените на вашу ссылку для гаранта
        "владелец чата": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",  # Замените на вашу ссылку для владельца чата
        "проверенный": "https://i.ibb.co/0jqRrPrm/IMG-20250809-120309-325.jpg",  # Замените на вашу ссылку для проверенного
        "отказ от гаранта": "https://i.ibb.co/jPpYnM7H/IMG-20250809-120309-094.jpg",  # Замените на вашу ссылку для отказа
        "скамер": "https://i.ibb.co/MxkQdSZp/IMG-20250809-120308-534.jpg",  # Замените на вашу ссылку для скамера
        "непроверенный": "https://i.ibb.co/DD4n7HmF/IMG-20250809-120308-732.jpg"  # Замените на вашу ссылку для непроверенного
    }
    return banners.get(role, banners["непроверенный"])

# --- Обновленная функция для баннера глобального сообщения ---
def get_global_message_banner_url():
    """Возвращает URL ссылку на баннер для глобального сообщения"""
    return "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg" # Замените на вашу ссылку

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)

    parts = msg.text.strip().split()

    # Проверяем, указан ли username
    if len(parts) > 1 and parts[1].startswith('@'):
        username = parts[1]

        # Сначала ищем в нашей базе данных
        user_id = find_user_by_username(username.lstrip('@'))
        user_info = None # Инициализируем user_info

        if user_id:
            # Нашли в базе данных, пытаемся получить актуальную информацию
            try:
                user_info = bot.get_chat(int(user_id))
            except Exception as api_error:
                print(f"Не удалось получить актуальные данные для user_id {user_id} из API: {api_error}")
                # Если API не работает, создаем простой объект с нужными атрибутами
                class UserInfo:
                    def __init__(self, user_id, username):
                        self.id = int(user_id)
                        self.username = username.lstrip('@')
                        self.first_name = "Неизвестный"
                
                user_info = UserInfo(user_id, username)

            target_name = user_info.first_name or "Неизвестный"
            role = get_role(user_id)
            risk = get_risk(user_id)
            profile_link = f"<a href='tg://user?id={user_id}'>{target_name}</a>"
            username_display = username

            # Создаем красивый интерфейс
            status_emoji = get_status_emoji(role)
            status_name = get_status_name(role)
            risk_color = get_risk_color(risk)

            # Получаем информацию о проверке
            verification_info = get_verification_info(user_id)

            # Получаем биографию пользователя
            user_bio = get_user_bio(user_id)
            bio_text = user_bio if user_bio else "Биография не установлена. /bio"

            # Получаем время проверки
            check_time = datetime.now().strftime('%H:%M МСК • %d %B')

            # Определяем текст проверяющего
            verified_by_text = "Не проверен"
            if verification_info:
                try:
                    verifier_chat = bot.get_chat(int(verification_info['verified_by']))
                    verifier_name = verifier_chat.username or verifier_chat.first_name
                    verifier_username = f"@{verifier_name}" if verifier_chat.username else verifier_name
                    verified_by_text = f"Проверен гарантом {verifier_username}"
                except:
                    verified_by_text = f"Проверен гарантом ID: {verification_info['verified_by']}"

            text = (
                f"ℹ️ | {target_name} | <code>{user_id}</code>\n"
                f"🗓 | Дата проверки: {check_time}\n\n"
                f"{status_emoji} | Статус: {status_name} |\n"
                f"{risk_color} | Процент скама: {risk} |\n"
                f"{verified_by_text}\n\n"
                f"📝 | О себе: {bio_text}\n\n"
                f"👤 | Профиль: <a href='tg://user?id={user_id}'>{target_name}</a>\n\n"
            )
        else:
            # Пытаемся найти через API Telegram
            user_info = get_user_by_username(username)
            if user_info:
                user_id = user_info.id
                target_name = user_info.first_name
                role = get_role(user_id)
                risk = get_risk(user_id)
                profile_link = f"<a href='tg://user?id={user_id}'>{target_name}</a>"

                # Сохраняем связь username -> user_id
                save_username_mapping(user_id, username.lstrip('@'))

                # Создаем красивый интерфейс
                status_emoji = get_status_emoji(role)
                status_name = get_status_name(role)
                risk_color = get_risk_color(risk)
                username_display = username

                # Получаем информацию о проверке
                verification_info = get_verification_info(user_id)

                # Получаем биографию пользователя
                user_bio = get_user_bio(user_id)
                bio_text = user_bio if user_bio else "Биография не установлена. /bio"

                # Получаем время проверки
                check_time = datetime.now().strftime('%H:%M МСК • %d %B')

                # Определяем текст проверяющего
                verified_by_text = "Не проверен"
                if verification_info:
                    try:
                        verifier_chat = bot.get_chat(int(verification_info['verified_by']))
                        verifier_name = verifier_chat.username or verifier_chat.first_name
                        verifier_username = f"@{verifier_name}" if verifier_chat.username else verifier_name
                        verified_by_text = f"Проверен гарантом {verifier_username}"
                    except:
                        verified_by_text = f"Проверен гарантом ID: {verification_info['verified_by']}"

                text = (
                    f"ℹ️ | {target_name} | <code>{user_id}</code>\n"
                    f"🗓 | Дата проверки: {check_time}\n\n"
                    f"{status_emoji} | Статус: {status_name} |\n"
                    f"{risk_color} | Процент скама: {risk} |\n"
                    f"{verified_by_text}\n\n"
                    f"📝 | О себе: {bio_text}\n\n"
                    f"👤 | Профиль: <a href='tg://user?id={user_id}'>{target_name}</a>\n\n"
                )
            else:
                text = f"❌ Пользователь {username} не найден"
    else:
        # Проверяем по reply или автора сообщения
        user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
        user_id = user.id
        target_name = user.first_name or "Неизвестный"
        username_display = f"@{user.username}" if user.username else "Не указан"
        role = get_role(user_id)
        risk = get_risk(user_id)
        profile_link = f"<a href='tg://user?id={user_id}'>{target_name}</a>"

        # Сохраняем username если он есть
        if user.username:
            save_username_mapping(user_id, user.username)

        # Создаем красивый интерфейс
        status_emoji = get_status_emoji(role)
        status_name = get_status_name(role)
        risk_color = get_risk_color(risk)

        # Получаем информацию о проверке
        verification_info = get_verification_info(user_id)

        # Получаем биографию пользователя
        user_bio = get_user_bio(user_id)
        bio_text = user_bio if user_bio else "Биография не установлена. /bio"

        # Получаем время проверки
        check_time = datetime.now().strftime('%H:%M МСК • %d %B')

        # Определяем текст проверяющего
        verified_by_text = "Не проверен"
        if verification_info:
            try:
                verifier_chat = bot.get_chat(int(verification_info['verified_by']))
                verifier_name = verifier_chat.username or verifier_chat.first_name
                verifier_username = f"@{verifier_name}" if verifier_chat.username else verifier_name
                verified_by_text = f"Проверен гарантом {verifier_username}"
            except:
                verified_by_text = f"Проверен гарантом ID: {verification_info['verified_by']}"

        text = (
            f"ℹ️ | {target_name} | <code>{user_id}</code>\n"
            f"🗓 | Дата проверки: {check_time}\n\n"
            f"{status_emoji} | Статус: {status_name} |\n"
            f"{risk_color} | Процент скама: {risk} |\n"
            f"{verified_by_text}\n\n"
            f"📝 | О себе: {bio_text}\n\n"
            f"👤 | Профиль: <a href='tg://user?id={user_id}'>{target_name}</a>"
        )

    # Определяем финальные значения для использования в дальнейшем коде
    final_user_id = user_id if 'user_id' in locals() else (user.id if 'user' in locals() else None)
    final_role = role if 'role' in locals() else "непроверенный"
    final_target_name = target_name if 'target_name' in locals() else "Неизвестный"

    # Создаем кнопку "Профиль"
    markup = types.InlineKeyboardMarkup()
    profile_button = types.InlineKeyboardButton(
        "📋 Подробный профиль",
        url=f"https://t.me/{bot.get_me().username}?start=profile_{final_user_id if final_user_id else 'unknown'}"
    )
    markup.add(profile_button)

    # Увеличиваем счетчик просмотров профиля
    if final_user_id:
        increment_profile_views(final_user_id)
        views_count = get_profile_views(final_user_id)
        # Добавляем информацию о просмотрах
        text += f"       👁️ {views_count}\n"
        text += f"📅 Последняя активность: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # Добавляем баннер в текст через HTML ссылку
    banner_url = get_role_banner_url(final_role)
    if banner_url:
        text += f'\n<a href="{banner_url}">&#8203;</a>'

    # Отправляем сообщение с встроенным баннером
    try:
        bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        try:
            bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
        except:
            bot.send_message(msg.chat.id, "❌ Ошибка при отображении профиля")

@bot.message_handler(commands=["bio"])
def handle_bio(msg):
    user_id = msg.from_user.id
    parts = msg.text.split(maxsplit=1)

    if len(parts) < 2:
        # Если команда вызвана без текста, показываем текущую биографию или сообщение об ее отсутствии
        current_bio = get_user_bio(user_id)
        if current_bio:
            bot.reply_to(msg, f"Ваша текущая биография:\n\n{current_bio}\n\nЧтобы изменить, используйте команду:\n/bio ваш_новый_текст_биографии (до 30 слов)")
        else:
            bot.reply_to(msg, "Биография не установлена. Используйте команду:\n/bio ваш_текст_биографии (до 30 слов)")
        return

    new_bio = parts[1].strip()

    # Ограничение длины биографии
    if len(new_bio.split()) > 30:
        bot.reply_to(msg, "❌ Ваша биография слишком длинная. Максимум 30 слов.")
        return
    elif len(new_bio) == 0:
        bot.reply_to(msg, "❌ Биография не может быть пустой.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO user_bios (user_id, bio, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (str(user_id), new_bio)
        )
        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(msg, f"✅ Ваша биография успешно обновлена!\n\n{new_bio}")
    except Exception as e:
        bot.reply_to(msg, f"❌ Ошибка при сохранении биографии: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("проверен"))
def handle_verify_user(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    # Проверяем права на команду (гаранты, владельцы чата и владельцы)
    if caller_role not in ["гарант", "владелец чата", "владелец"] and msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав на использование команды 'проверен'. Доступно только гарантам и владельцам чата.")
        return

    parts = msg.text.strip().split()

    # Проверяем, указан ли username
    if len(parts) >= 2 and parts[1].startswith('@'):
        username = parts[1]

        # Ищем пользователя по username
        user_id = find_user_by_username(username.lstrip('@'))

        if not user_id:
            # Пытаемся найти через API
            user_info = get_user_by_username(username)
            if user_info:
                user_id = user_info.id
                target_name = user_info.first_name
                save_username_mapping(user_id, username.lstrip('@'))
            else:
                bot.reply_to(msg, f"❌ Пользователь {username} не найден")
                return
        else:
            # Если нашли в базе, получаем имя через API для актуальности
            try:
                user_info = bot.get_chat(int(user_id))
                target_name = user_info.first_name
            except:
                target_name = username

        target_id = int(user_id)
        profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"

    elif msg.reply_to_message:
        # Работаем через reply
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name
        profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"
    else:
        bot.reply_to(msg, "Ответьте на сообщение пользователя или укажите @username.\nПример: проверен @username")
        return

    # Защита от самопроверки
    if target_id == msg.from_user.id:
        bot.reply_to(msg, "❌ Нельзя проверять самого себя.")
        return

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Владелец не нуждается в проверке.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Присваиваем роль "проверенный" пользователю
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, role, scam_percent) VALUES (?, ?, ?)",
            (str(target_id), "проверенный", "10%")
        )

        # Сохраняем информацию о проверке
        cursor.execute(
            "INSERT OR REPLACE INTO user_verifications (user_id, verified_by, verified_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (str(target_id), str(msg.from_user.id))
        )

        conn.commit()
        cursor.close()
        conn.close()

        # Получаем имя проверяющего
        verifier_name = msg.from_user.first_name
        verifier_role = get_role(msg.from_user.id)

        # Определяем название роли проверяющего
        role_names = {
            "владелец": "владельцем",
            "гарант": "гарантом",
            "владелец чата": "владельцем чата"
        }
        verifier_role_name = role_names.get(verifier_role, "гарантом")

        bot.reply_to(msg, f"✅ {profile_link} получил статус 'Проверенный' и проверен {verifier_role_name} <a href='tg://user?id={msg.from_user.id}'>{verifier_name}</a>")

    except Exception as e:
        bot.reply_to(msg, f"❌ Ошибка при проверке пользователя: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    # Проверяем права на команду
    if not has_command_permission(msg.from_user.id, "занести"):
        bot.reply_to(msg, "❌ У вас нет прав на использование команды 'занести'.")
        return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: занести скамер (в ответ на сообщение) или занести @username скамер")
        return

    # Проверяем, указан ли username
    if len(parts) >= 3 and parts[1].startswith('@'):
        username = parts[1]
        role = parts[2].lower()

        # Ищем пользователя по username
        user_id = find_user_by_username(username.lstrip('@'))

        if not user_id:
            # Пытаемся найти через API
            user_info = get_user_by_username(username)
            if user_info:
                user_id = user_info.id
                target_name = user_info.first_name
                save_username_mapping(user_id, username.lstrip('@'))
            else:
                # Если пользователь не найден через API, создаем фиктивную запись
                # Используем хеш от username как временный ID
                import hashlib
                temp_id = abs(hash(username.lstrip('@'))) % (10**9)  # Генерируем уникальный ID
                user_id = temp_id
                target_name = username.lstrip('@')
                # Сохраняем связь username -> temp_id в обе стороны
                save_username_mapping(temp_id, username.lstrip('@'))
                print(f"Создан временный ID {temp_id} для username {username}")
        else:
            # Если нашли в базе, получаем имя через API для актуальности
            try:
                user_info = bot.get_chat(int(user_id))
                target_name = user_info.first_name
            except:
                target_name = username

        target_id = int(user_id)
        profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"

    elif msg.reply_to_message:
        # Работаем через reply
        role = parts[1].lower()
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name
        profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"
    else:
        bot.reply_to(msg, "Ответьте на сообщение пользователя или укажите @username.\nПример: занести @username скамер")
        return

    # Защита от самозаноса
    if target_id == msg.from_user.id:
        bot.reply_to(msg, "❌ Нельзя заносить самого себя в базу.")
        return

    allowed_roles = ["скамер", "гарант", "владелец_чата", "отказ", "отказ_от_гаранта", "проверенный"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Роли: скамер, гарант, владелец_чата, отказ, отказ_от_гаранта, проверенный")
        return

    # Проверяем специфические права на занос конкретных ролей
    role_permission_map = {
        "скамер": "заносить_скамер",
        "гарант": "заносить_гарант",
        "владелец_чата": "заносить_владелец_чата",
        "отказ": "заносить_отказ",
        "отказ_от_гаранта": "заносить_отказ",
        "проверенный": "заносить_проверенный"
    }

    # Проверяем есть ли специфическое право на занос этой роли
    specific_permission = role_permission_map.get(role)
    if specific_permission and not has_command_permission(msg.from_user.id, specific_permission):
        bot.reply_to(msg, f"❌ У вас нет прав на занос роли '{role}'. Нужно право '{specific_permission}'.")
        return

    if caller_role in ["гарант", "владелец чата"] and role == "гарант":
        bot.reply_to(msg, "❌ Нельзя заносить гарантов.")
        return

    # Проверяем права на выдачу роли "проверенный"
    if role == "проверенный" and caller_role not in ["владелец", "владелец чата"] and not has_command_permission(msg.from_user.id, "заносить_проверенный"):
        bot.reply_to(msg, "❌ Роль 'проверенный' может выдавать только владелец или владелец чата.")
        return

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя менять роль владельцу.")
        return

    if role.startswith("отказ"):
        role_text = "отказ от гаранта"
        scam_percent = "80%"
    elif role == "владелец_чата":
        role_text = "владелец чата"
        scam_percent = "10%"
    elif role == "скамер":
        role_text = "скамер"
        scam_percent = "100%"
    elif role == "гарант":
        role_text = "гарант"
        scam_percent = "0%"
    elif role == "проверенный":
        role_text = "проверенный"
        scam_percent = "10%"
    else:
        role_text = role
        scam_percent = "50%"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, role, scam_percent) VALUES (?, ?, ?)",
            (str(target_id), role_text, scam_percent)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")
        return

    if role_text == "скамер":
        # Создаем сообщение с кликабельной ссылкой на профиль
        if len(parts) >= 3 and parts[1].startswith('@'):
            # Если через username, создаем ссылку на профиль через ID
            username_clean = username.lstrip('@')
            alert = f"⚠️ Осторожно! В базу занесен скамер: <a href='tg://user?id={target_id}'>@{username_clean}</a>"
        else:
            # Если через reply, используем имя пользователя и ссылку
            username_text = f"@{target.username}" if hasattr(target, 'username') and target.username else target.first_name
            alert = f"⚠️ Осторожно! В базу занесен скамер: <a href='tg://user?id={target_id}'>{username_text}</a>"

        # Отправляем во все возможные чаты
        all_possible_chats = get_all_bot_chats()
        for chat_id in all_possible_chats:
            try:
                # Преобразуем в int если возможно
                try:
                    chat_id_int = int(chat_id)
                except:
                    chat_id_int = chat_id

                # Проверяем, что бот все еще есть в чате
                member = bot.get_chat_member(chat_id_int, bot.get_me().id)
                if member.status in ['member', 'administrator', 'creator']:
                    bot.send_message(chat_id_int, alert)

            except Exception as e:
                print(f"Не удалось отправить в чат {chat_id}: {e}")

    bot.reply_to(msg, f"{profile_link} ✅ занесён как {role_text.upper()}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("вынести"))
def handle_remove_user(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    # Проверяем права на команду
    if not has_command_permission(msg.from_user.id, "вынести"):
        bot.reply_to(msg, "❌ У вас нет прав на использование команды 'вынести'.")
        return

    parts = msg.text.strip().split()

    # Проверяем, указан ли username
    if len(parts) >= 2 and parts[1].startswith('@'):
        username = parts[1].lstrip('@')
        
        # Сначала ищем в базе данных по username
        user_id = find_user_by_username(username)
        
        if user_id:
            # Нашли в базе по username
            try:
                user_info = bot.get_chat(int(user_id))
                target_name = user_info.first_name
            except:
                target_name = username
            
            target_id = int(user_id)
            profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"
            
        else:
            # Не нашли в базе по username, пробуем через API
            user_info = get_user_by_username(f"@{username}")
            if user_info:
                # Нашли через API, проверяем есть ли в базе по ID
                target_id = user_info.id
                target_name = user_info.first_name
                profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"
                
                # Проверяем есть ли этот пользователь в базе по ID
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (str(target_id),))
                    exists = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if not exists:
                        bot.reply_to(msg, f"❌ Пользователь @{username} не найден в базе данных")
                        return
                        
                except Exception as e:
                    print(f"Ошибка при проверке пользователя в базе: {e}")
                    bot.reply_to(msg, f"❌ Ошибка при поиске пользователя")
                    return
            else:
                # Не нашли через API, пробуем найти по временному ID
                temp_id = abs(hash(username)) % (10**9)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (str(temp_id),))
                    temp_user_exists = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if temp_user_exists:
                        target_id = temp_id
                        target_name = username
                        profile_link = f"<a href='tg://user?id={target_id}'>@{target_name}</a>"
                        print(f"Найден пользователь с временным ID {temp_id} для username @{username}")
                    else:
                        bot.reply_to(msg, f"❌ Пользователь @{username} не найден в базе данных")
                        return
                except Exception as e:
                    print(f"Ошибка при поиске временного ID: {e}")
                    bot.reply_to(msg, f"❌ Пользователь @{username} не найден")
                    return

    elif msg.reply_to_message:
        # Работаем через reply
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name
        profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"
        
        # Проверяем есть ли пользователь в базе
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (str(target_id),))
            exists = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not exists:
                bot.reply_to(msg, f"❌ Пользователь {target_name} не найден в базе данных")
                return
                
        except Exception as e:
            print(f"Ошибка при проверке пользователя в базе: {e}")
            bot.reply_to(msg, f"❌ Ошибка при поиске пользователя")
            return
    else:
        bot.reply_to(msg, "Ответьте на сообщение пользователя или укажите @username.\nПример: вынести @username")
        return

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя выносить владельца.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Удаляем пользователя из всех таблиц
        cursor.execute("DELETE FROM users WHERE user_id = ?", (str(target_id),))
        cursor.execute("DELETE FROM user_verifications WHERE user_id = ?", (str(target_id),))
        cursor.execute("DELETE FROM profile_views WHERE user_id = ?", (str(target_id),))
        cursor.execute("DELETE FROM user_bios WHERE user_id = ?", (str(target_id),))
        cursor.execute("DELETE FROM usernames WHERE user_id = ?", (str(target_id),))

        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(msg, f"✅ {profile_link} удален из базы")
        else:
            bot.reply_to(msg, f"❌ {profile_link} не найден в базе")
            
        cursor.close()
        conn.close()
    except Exception as e:
        bot.reply_to(msg, f"❌ Ошибка БД: {e}")
        print(f"Database error in handle_remove_user: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("гаранты"))
def handle_show_guarantors(msg):
    chats.add(msg.chat.id)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получаем всех пользователей с ролью "гарант", исключая владельцев и владельцев чата
        cursor.execute("SELECT user_id FROM users WHERE role = 'гарант' AND role NOT IN ('владелец', 'владелец чата')")
        guarantors = cursor.fetchall()

        cursor.close()
        conn.close()

        # Также исключаем владельцев из OWNER_IDS
        filtered_guarantors = []
        for row in guarantors:
            user_id = row['user_id']
            if int(user_id) not in OWNER_IDS:
                filtered_guarantors.append(user_id)

        if not filtered_guarantors:
            bot.reply_to(msg, "📋 В активном списке гарантов базы нет зарегистрированных пользователей.")
            return

        # Формируем список гарантов с кликабельными ссылками на профили
        guarantor_list = []
        for user_id in filtered_guarantors:
            try:
                # Пытаемся получить информацию о пользователе через API
                user_info = bot.get_chat(int(user_id))
                first_name = user_info.first_name or "Пользователь"

                # Создаем кликабельную ссылку на профиль
                profile_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                guarantor_list.append(f"• {profile_link}")

            except Exception as api_error:
                # Если API не работает, все равно создаем кликабельную ссылку
                profile_link = f"<a href='tg://user?id={user_id}'>Гарант (ID: {user_id})</a>"
                guarantor_list.append(f"• {profile_link}")
                print(f"Не удалось получить данные для user_id {user_id}: {api_error}")

        # Создаем сообщение с улучшенным заголовком
        text = f"🛡️ <b>Активный список гарантов базы ({len(guarantor_list)}):</b>\n\n"
        text += "\n".join(guarantor_list)

        # Добавляем информацию о кликабельности
        text += f"\n\n💡 <i>Все гаранты кликабельны для перехода в профиль</i>"

        # Ограничиваем длину сообщения (Telegram имеет лимит 4096 символов)
        if len(text) > 4000:
            text = text[:3950] + "\n\n... и другие\n\n💡 <i>Все гаранты кликабельны для перехода в профиль</i>"

        bot.reply_to(msg, text)

    except Exception as e:
        bot.reply_to(msg, f"❌ Ошибка при получении активного списка гарантов базы: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("ип"))
def handle_change_scam_percent(msg):
    chats.add(msg.chat.id)

    # Проверяем права на команду
    if not has_command_permission(msg.from_user.id, "ип"):
        bot.reply_to(msg, "❌ У вас нет прав на использование команды 'ип'.")
        return

    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя, которому хотите изменить процент.")
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(msg, "Пример: ип 30 (в ответ на сообщение)")
        return

    target = msg.reply_to_message.from_user
    target_id = target.id
    percent = parts[1] + "%"
    profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Сначала проверяем, есть ли пользователь в базе
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (str(target_id),))
        user_exists = cursor.fetchone()

        if user_exists:
            # Обновляем существующего пользователя
            cursor.execute(
                "UPDATE users SET scam_percent = ? WHERE user_id = ?",
                (percent, str(target_id))
            )
        else:
            # Создаем нового пользователя с кастомным процентом
            cursor.execute(
                "INSERT INTO users (user_id, role, scam_percent) VALUES (?, ?, ?)",
                (str(target_id), "непроверенный", percent)
            )

        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(msg, f"✅ Процент скама для {profile_link} установлен на {percent}")
    except Exception as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")

def get_all_bot_chats():
    """Получает все чаты из базы данных где бот когда-либо был активен"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получаем все чаты из базы данных
        cursor.execute("SELECT chat_id FROM bot_chats")
        db_chats = [row['chat_id'] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        # Объединяем с текущими активными чатами
        all_chats = set(db_chats + [str(chat_id) for chat_id in chats])
        return all_chats
    except Exception as e:
        print(f"Ошибка при получении чатов из БД: {e}")
        return set(str(chat_id) for chat_id in chats)

def save_chat_to_db(chat_id, chat_title=None, chat_type=None):
    """Сохраняет информацию о чате в базу данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR REPLACE INTO bot_chats (chat_id, chat_title, chat_type, last_activity)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (str(chat_id), chat_title, chat_type))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении чата {chat_id} в БД: {e}")

def should_warn_about_scammer(chat_id, user_id):
    """Проверяет, нужно ли предупреждать о скамере (с кулдауном 3 минуты)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получаем последнее предупреждение
        cursor.execute("""
        SELECT last_warning FROM scammer_warnings
        WHERE chat_id = ? AND user_id = ?
        """, (str(chat_id), str(user_id)))

        result = cursor.fetchone()
        current_time = datetime.now()

        if result:
            last_warning = datetime.fromisoformat(result['last_warning'])
            # Проверяем, прошло ли 3 минуты
            if current_time - last_warning < timedelta(minutes=3):
                cursor.close()
                conn.close()
                return False

        # Обновляем время последнего предупреждения
        cursor.execute("""
        INSERT OR REPLACE INTO scammer_warnings (chat_id, user_id, last_warning)
        VALUES (?, ?, ?)
        """, (str(chat_id), str(user_id), current_time.isoformat()))

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Ошибка при проверке предупреждения о скамере: {e}")
        return True  # В случае ошибки показываем предупреждение

# --- Добавленная команда глобального сообщения ---
@bot.message_handler(commands=["гс"])
def handle_global_message(msg):
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав использовать эту команду.")
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "❗️ Использование: /гс текст_сообщения")
        return

    message_to_send = parts[1]
    count = 0
    failed = 0

    # Получаем все возможные чаты
    all_possible_chats = get_all_bot_chats()

    bot.reply_to(msg, f"🔄 Начинаю отправку глобального сообщения в {len(all_possible_chats)} чат(ов)...")

    # Отправляем во все найденные чаты
    for chat_id in all_possible_chats:
        try:
            # Преобразуем в int если возможно
            try:
                chat_id_int = int(chat_id)
            except:
                chat_id_int = chat_id

            # Проверяем, что бот все еще есть в чате
            member = bot.get_chat_member(chat_id_int, bot.get_me().id)
            if member.status in ['member', 'administrator', 'creator']:
                try:
                    # Добавляем баннер в текст глобального сообщения
                    banner_url = get_global_message_banner_url()
                    message_text = message_to_send
                    if banner_url:
                        message_text += f'\n\n<a href="{banner_url}">&#8203;</a>'

                    bot.send_message(chat_id_int, message_text, parse_mode="HTML")
                    count += 1
                except Exception as e:
                    print(f"Не удалось отправить сообщение в чат {chat_id}: {e}")
                    failed += 1

                # Обновляем информацию о чате
                try:
                    chat_info = bot.get_chat(chat_id_int)
                    save_chat_to_db(chat_id_int, chat_info.title, chat_info.type)
                except:
                    save_chat_to_db(chat_id_int)
            else:
                failed += 1

        except Exception as e:
            print(f"Не удалось отправить в чат {chat_id}: {e}")
            failed += 1
            # Удаляем из активных чатов если бот больше не участник
            if "bot was kicked" in str(e).lower() or "chat not found" in str(e).lower():
                chats.discard(int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id)

    bot.send_message(msg.chat.id, f"✅ Глобальное сообщение отправлено!\n📊 Успешно: {count} чат(ов)\n❌ Ошибок: {failed}")

# --- Команды для управления правами пользователей ---
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("+кмд"))
def handle_grant_permission(msg):
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав использовать эту команду.")
        return

    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя, которому хотите выдать права.")
        return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: +кмд занести (в ответ на сообщение)\nИли: +кмд заносить_скамер")
        return

    command_name = parts[1].lower()
    available_commands = [
        "занести", "вынести", "ип", "сетка_бан",
        "заносить_скамер", "заносить_гарант", "заносить_владелец_чата",
        "заносить_отказ", "заносить_проверенный", "проверенный" # Добавлена команда "проверенный"
    ]

    if command_name not in available_commands:
        bot.reply_to(msg, f"Доступные команды:\n• Основные: занести, вынести, ип, сетка_бан\n• Специфические: заносить_скамер, заносить_гарант, заносить_владелец_чата, заносить_отказ, заносить_проверенный, проверенный")
        return

    target = msg.reply_to_message.from_user
    target_id = target.id
    target_name = target.first_name
    profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Владелец уже имеет все права.")
        return

    success = grant_command_permission(target_id, command_name, msg.from_user.id, True)

    if success:
        bot.reply_to(msg, f"✅ {profile_link} получил право на команду '{command_name}'")
    else:
        bot.reply_to(msg, "❌ Ошибка при выдаче прав.")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("-кмд"))
def handle_revoke_permission(msg):
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав использовать эту команду.")
        return

    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя, у которого хотите отнять права.")
        return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: -кмд занести (в ответ на сообщение)\nИли: -кмд заносить_скамер")
        return

    command_name = parts[1].lower()
    available_commands = [
        "занести", "вынести", "ип", "сетка_бан",
        "заносить_скамер", "заносить_гарант", "заносить_владелец_чата",
        "заносить_отказ", "заносить_проверенный", "проверенный"
    ]

    if command_name not in available_commands:
        bot.reply_to(msg, f"Доступные команды:\n• Основные: занести, вынести, ип, сетка_бан\n• Специфические: заносить_скамер, заносить_гарант, заносить_владелец_чата, заносить_отказ, заносить_проверенный, проверенный")
        return

    target = msg.reply_to_message.from_user
    target_id = target.id
    target_name = target.first_name
    profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя отнимать права у владельца.")
        return

    success = grant_command_permission(target_id, command_name, msg.from_user.id, False)

    if success:
        bot.reply_to(msg, f"❌ У {profile_link} отнято право на команду '{command_name}'")
    else:
        bot.reply_to(msg, "❌ Ошибка при отнятии прав.")

# --- Команда для проверки активных чатов ---
@bot.message_handler(commands=["чаты"])
def handle_list_chats(msg):
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав использовать эту команду.")
        return

    active_chats = []
    inactive_chats = []

    for chat_id in chats.copy():
        try:
            chat_info = bot.get_chat(chat_id)
            bot.get_chat_member(chat_id, bot.get_me().id)
            active_chats.append(f"• {chat_info.title or 'Приватный чат'} (ID: {chat_id})")
        except Exception as e:
            inactive_chats.append(chat_id)
            if "bot was kicked" in str(e).lower() or "chat not found" in str(e).lower():
                chats.discard(chat_id)

    response = f"📊 <b>Статистика чатов:</b>\n\n"
    response += f"✅ <b>Активные чаты ({len(active_chats)}):</b>\n"
    if active_chats:
        response += "\n".join(active_chats[:20])  # Показываем максимум 20 чатов
        if len(active_chats) > 20:
            response += f"\n... и еще {len(active_chats) - 20} чат(ов)"
    else:
        response += "Нет активных чатов"

    if inactive_chats:
        response += f"\n\n❌ <b>Неактивные чаты ({len(inactive_chats)}):</b> удалены из списка"

    bot.reply_to(msg, response)

# --- Команда сетка бан ---
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("сетка бан"))
def handle_network_ban(msg):
    # Проверяем права на команду
    if not has_command_permission(msg.from_user.id, "сетка_бан"):
        bot.reply_to(msg, "❌ У вас нет прав на использование команды 'сетка бан'.")
        return

    parts = msg.text.strip().split()

    # Проверяем, указан ли username
    if len(parts) >= 3 and parts[2].startswith('@'):
        username = parts[2]

        # Ищем пользователя по username
        user_id = find_user_by_username(username.lstrip('@'))

        if not user_id:
            # Пытаемся найти через API
            user_info = get_user_by_username(username)
            if user_info:
                user_id = user_info.id
                target_name = user_info.first_name
                save_username_mapping(user_id, username.lstrip('@'))
            else:
                bot.reply_to(msg, f"❌ Пользователь {username} не найден")
                return
        else:
            # Если нашли в базе, получаем имя через API для актуальности
            try:
                user_info = bot.get_chat(int(user_id))
                target_name = user_info.first_name
            except:
                target_name = username

        target_id = int(user_id)

    elif msg.reply_to_message:
        # Работаем через reply
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name
    else:
        bot.reply_to(msg, "Использование: сетка бан (в ответ на сообщение) или сетка бан @username")
        return

    # Защита от бана владельцев
    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя банить владельца.")
        return

    profile_link = f"<a href='tg://user?id={target_id}'>{target_name}</a>"

    # Получаем все возможные чаты
    all_possible_chats = get_all_bot_chats()

    banned_count = 0
    failed_count = 0
    no_rights_count = 0

    bot.reply_to(msg, f"🔨 Начинаю сетка бан для {profile_link} в {len(all_possible_chats)} чат(ах)...")

    # Баним пользователя во всех найденных чатах
    for chat_id in all_possible_chats:
        try:
            # Преобразуем в int если возможно
            try:
                chat_id_int = int(chat_id)
            except:
                chat_id_int = chat_id

            # Проверяем, что бот все еще есть в чате и имеет права админа
            bot_member = bot.get_chat_member(chat_id_int, bot.get_me().id)
            if bot_member.status in ['administrator', 'creator']:
                # Проверяем, что у бота есть права на бан
                if bot_member.can_restrict_members or bot_member.status == 'creator':
                    try:
                        # Баним пользователя
                        bot.ban_chat_member(chat_id_int, target_id)
                        banned_count += 1
                    except Exception as ban_error:
                        print(f"Ошибка при бане в чате {chat_id}: {ban_error}")
                        failed_count += 1
                else:
                    no_rights_count += 1
            else:
                # Бот не админ в этом чате
                no_rights_count += 1

        except Exception as e:
            print(f"Не удалось забанить в чате {chat_id}: {e}")
            failed_count += 1
            # Удаляем из активных чатов если бот больше не участник
            if "bot was kicked" in str(e).lower() or "chat not found" in str(e).lower():
                chats.discard(int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id)

    # Отправляем результат
    result_text = f"🔨 <b>Результат сетка бан для {profile_link}:</b>\n\n"
    result_text += f"✅ Забанен в: {banned_count} чат(ах)\n"
    result_text += f"❌ Ошибки: {failed_count} чат(ов)\n"
    result_text += f"🚫 Нет прав: {no_rights_count} чат(ов)\n"
    result_text += f"📊 Всего обработано: {len(all_possible_chats)} чат(ов)"

    bot.send_message(msg.chat.id, result_text)

# ----------------------------------------------

@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    chats.add(message.chat.id)
    # Сохраняем информацию о чате в базу данных
    save_chat_to_db(message.chat.id, message.chat.title, message.chat.type)

    for user in message.new_chat_members:
        role = get_role(user.id)
        risk = get_risk(user.id)
        profile_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

        # Исключаем владельцев, владельцев чата и проверенных из уведомлений
        excluded_roles = ["владелец", "владелец чата", "проверенный"]

        if role == "непроверенный" and role not in excluded_roles:
            bot.send_message(
                message.chat.id,
                f"🚨 Новый пользователь {profile_link}\n"
                f"Роль: {role}\n📊 Риск: {risk}"
            )

@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def auto_check_group(msg):
    chats.add(msg.chat.id)
    # Сохраняем информацию о чате в базу данных
    save_chat_to_db(msg.chat.id, msg.chat.title, msg.chat.type)

    user = msg.from_user
    role = get_role(user.id)

    # Исключаем владельцев, владельцев чата и проверенных из автопроверки
    excluded_roles = ["владелец", "владелец чата", "проверенный"]

    if role == "скамер" and role not in excluded_roles:
        # Проверяем, нужно ли предупреждать (с кулдауном 3 минуты)
        if should_warn_about_scammer(msg.chat.id, user.id):
            profile_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
            username_text = f"@{user.username}" if user.username else user.first_name

            warning_text = (
                f"⚠️ <b>Осторожно!</b>\n"
                f"Пользователь {profile_link} ({username_text}) со статусом <b>СКАМЕР</b> замечен в чате!\n"
                f"🚫 Будьте внимательны при взаимодействии с этим пользователем."
            )

            bot.send_message(msg.chat.id, warning_text)

@bot.message_handler(func=lambda msg: True)
def register_chat(msg):
    chats.add(msg.chat.id)
    # Сохраняем информацию о чате в базу данных
    save_chat_to_db(msg.chat.id, getattr(msg.chat, 'title', None), msg.chat.type)

    # Сохраняем username пользователя если он есть
    if msg.from_user.username:
        save_username_mapping(msg.from_user.id, msg.from_user.username)

def safe_reply(msg, text):
    """Безопасная отправка ответа с обработкой ошибок"""
    try:
        bot.reply_to(msg, text)
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        try:
            # Пытаемся отправить через send_message если reply_to не работает
            bot.send_message(msg.chat.id, text)
        except Exception as e2:
            print(f"Не удалось отправить сообщение в чат {msg.chat.id}: {e2}")

def run_bot():
    """Функция для запуска бота с улучшенной обработкой ошибок"""
    print("🤖 Инициализация бота...")

    try:
        # Проверяем валидность токена
        bot_info = bot.get_me()
        print(f"✅ Бот успешно подключен: @{bot_info.username}")
    except Exception as token_error:
        print(f"❌ Ошибка токена: {token_error}")
        return

    # Очищаем pending updates
    try:
        bot.delete_webhook()
        print("🧹 Webhook очищен")
    except:
        pass

    # Получаем обновления и очищаем очередь
    try:
        updates = bot.get_updates(timeout=1)
        if updates:
            last_update_id = updates[-1].update_id
            bot.get_updates(offset=last_update_id + 1, timeout=1)
            print("🧹 Очередь обновлений очищена")
    except:
        pass

    print("🚀 Запуск бота...")

    try:
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=20,
            none_stop=True,
            interval=0,
            allowed_updates=None,
            skip_pending=True
        )
    except KeyboardInterrupt:
        print("\n⛔ Получен сигнал остановки")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("🛑 Бот остановлен")

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Telegram Bot Starting...")
    print("=" * 50)
    run_bot()