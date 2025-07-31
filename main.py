import telebot
import mysql.connector
from mysql.connector import Error

BOT_TOKEN = "8363145008:AAEM6OSKNRjX3SDU6yINZwbMOEcsaOQVdiI"
OWNER_IDS = [7537570296, 5821123636]

DB_HOST = "sql8.freesqldatabase.com"
DB_USER = "sql8792761"
DB_PASSWORD = "1upRsp7dLm"
DB_NAME = "sql8792761"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
chats = set()

import time

def get_connection():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                charset="utf8mb4",
                autocommit=True,
                connection_timeout=10,
                buffered=True
            )
            return conn
        except Error as e:
            print(f"Попытка подключения {attempt + 1}/{max_retries} неудачна: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
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
                user_id VARCHAR(100) PRIMARY KEY,
                role VARCHAR(50) DEFAULT 'непроверенный',
                scam_percent VARCHAR(10) DEFAULT '50%'
            )""")
            
            # Создаем таблицу для username
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS usernames (
                user_id VARCHAR(100) PRIMARY KEY,
                username VARCHAR(100)
            )""")
            
            # Создаем таблицу для чатов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_chats (
                chat_id VARCHAR(100) PRIMARY KEY,
                chat_title VARCHAR(255),
                chat_type VARCHAR(50),
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )""")
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ База данных успешно инициализирована!")
            return
        except Error as e:
            print(f"Ошибка при создании таблицы (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print("❌ Не удалось инициализировать базу данных после всех попыток")

init_db()

def get_risk(user_id):
    try:
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "0%"
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role, scam_percent FROM users WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        
        if result:
            role, scam_percent = result
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
    try:
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "владелец"
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result and result[0] else "непроверенный"
    except Exception as e:
        print(f"Ошибка при получении роли для {user_id}: {e}")
        return "непроверенный"

@bot.message_handler(commands=["start"])
def start_command(msg):
    bot.reply_to(msg, "👋 Привет! Я активен. Используй /help, чтобы увидеть доступные команды.")

@bot.message_handler(commands=["help"])
def help_command(msg):
    if msg.from_user.id in OWNER_IDS:
        text = (
            "📘 Команды:\n"
            "— чек (в ответ на сообщение или без параметров)\n"
            "— занести (в ответ на сообщение)\n"
            "— вынести (в ответ на сообщение)\n"
            "— ип 30 (в ответ на сообщение)\n"
            "— /гс (текст сообщения) — отправить глобальное сообщение во все чаты\n"
            "— /чаты — посмотреть список активных чатов\n"
            "\nБот активен и работает ✅"
        )
    else:
        text = (
            "📘 Команды:\n"
            "— чек (в ответ на сообщение или без параметров)\n"
            "— занести (в ответ на сообщение)\n"
            "— вынести (в ответ на сообщение)\n"
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
            "REPLACE INTO usernames (user_id, username) VALUES (%s, %s)",
            (str(user_id), username)
        )
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
        cursor.execute("SELECT user_id FROM usernames WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Ошибка при поиске username {username} в БД: {e}")
        return None

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)
    
    # Проверяем по reply или автора сообщения
    user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    user_id = user.id
    user_name = user.first_name
    role = get_role(user_id)
    risk = get_risk(user_id)
    profile_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    # Сохраняем username если он есть
    if user.username:
        save_username_mapping(user_id, user.username)

    text = (
        f"👤 Профиль: {profile_link}\n"
        f"🔹 Роль: {role}\n"
        f"📊 Вероятность скама: {risk}"
    )
    bot.reply_to(msg, text)

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя, которого хотите занести.")
        return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: занести скамер (в ответ на сообщение)")
        return

    role = parts[1].lower()
    target = msg.reply_to_message.from_user
    target_id = target.id
    target_name = target.first_name
    profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"

    allowed_roles = ["скамер", "гарант", "владелец_чата", "отказ", "отказ_от_гаранта"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Роли: скамер, гарант, владелец_чата, отказ, отказ_от_гаранта")
        return

    if caller_role in ["гарант", "владелец чата"] and role == "гарант":
        bot.reply_to(msg, "❌ Нельзя заносить гарантов.")
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
    else:
        role_text = role
        scam_percent = "50%"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO users (user_id, role, scam_percent) VALUES (%s, %s, %s)",
            (str(target_id), role_text, scam_percent)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")
        return

    if role_text == "скамер":
        alert = f"⚠️ {profile_link} занесён как <b>СКАМЕР</b>!"
        for chat_id in chats:
            try:
                bot.send_message(chat_id, alert)
            except Exception as e:
                print(f"Не удалось отправить в чат {chat_id}: {e}")

    bot.reply_to(msg, f"{profile_link} ✅ занесён как {role_text.upper()}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("вынести"))
def handle_remove_user(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя, которого хотите вынести.")
        return

    target = msg.reply_to_message.from_user
    target_id = target.id
    profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя выносить владельца.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = %s", (str(target_id),))
        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(msg, f"✅ {profile_link} удален из базы")
        else:
            bot.reply_to(msg, f"❌ {profile_link} не найден")
        cursor.close()
        conn.close()
    except Error as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("ип"))
def handle_change_scam_percent(msg):
    # Проверяем, что команду использует только владелец
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет прав использовать эту команду.")
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
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (str(target_id),))
        user_exists = cursor.fetchone()
        
        if user_exists:
            # Обновляем существующего пользователя
            cursor.execute(
                "UPDATE users SET scam_percent = %s WHERE user_id = %s",
                (percent, str(target_id))
            )
        else:
            # Создаем нового пользователя с кастомным процентом
            cursor.execute(
                "INSERT INTO users (user_id, role, scam_percent) VALUES (%s, %s, %s)",
                (str(target_id), "непроверенный", percent)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(msg, f"✅ Процент скама для {profile_link} установлен на {percent}")
    except Error as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")

def get_all_bot_chats():
    """Получает все чаты из базы данных где бот когда-либо был активен"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Получаем все чаты из базы данных
        cursor.execute("SELECT chat_id FROM bot_chats")
        db_chats = [row[0] for row in cursor.fetchall()]
        
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
        REPLACE INTO bot_chats (chat_id, chat_title, chat_type) 
        VALUES (%s, %s, %s)
        """, (str(chat_id), chat_title, chat_type))
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении чата {chat_id} в БД: {e}")

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
                bot.send_message(chat_id_int, f"📢 <b>Глобальное сообщение:</b>\n{message_to_send}")
                count += 1
                
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
        if role == "непроверенный":
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
    if role == "скамер":
        profile_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        bot.reply_to(msg, f"⚠️ Осторожно! {profile_link} — СКАМЕР.")

@bot.message_handler(func=lambda msg: True)
def register_chat(msg):
    chats.add(msg.chat.id)
    # Сохраняем информацию о чате в базу данных
    save_chat_to_db(msg.chat.id, getattr(msg.chat, 'title', None), msg.chat.type)
    
    # Сохраняем username пользователя если он есть
    if msg.from_user.username:
        save_username_mapping(msg.from_user.id, msg.from_user.username)

print("Бот запускается...")
try:
    bot.infinity_polling()
except Exception as e:
    print(f"Ошибка при запуске бота: {e}")
