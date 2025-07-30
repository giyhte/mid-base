
import telebot
import mysql.connector
from mysql.connector import Error

# 🔐 Конфигурация
BOT_TOKEN = "8363145008:AAEM6OSKNRjX3SDU6yINZwbMOEcsaOQVdiI"
OWNER_IDS = [7537570296, 5821123636]

DB_HOST = "sql8.freesqldatabase.com"
DB_USER = "sql8792761"
DB_PASSWORD = "1upRsp7dLm"
DB_NAME = "sql8792761"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# 📌 Список всех чатов, где бот был активен
chats = set()

# 📦 Подключение к БД
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"
    )

# ⚙️ Инициализация таблицы
def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(100) PRIMARY KEY,
                role VARCHAR(50) DEFAULT 'непроверенный',
                scam_percent VARCHAR(10) DEFAULT '50%'
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("База данных инициализирована успешно")
    except Error as e:
        print(f"Ошибка при создании таблицы: {e}")

init_db()

# 📊 Получение роли пользователя
def get_role(user_id, username=None):
    try:
        # Проверяем владельцев только для числовых ID
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "владелец"

        conn = get_connection()
        cursor = conn.cursor()
        
        # Ищем по ID или по username
        if isinstance(user_id, str) and user_id.startswith("@"):
            # Поиск по username
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        else:
            # Поиск по числовому ID
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (str(user_id),))
            
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result[0]:
            return result[0]
        else:
            return "непроверенный"
    except Exception as e:
        print(f"Ошибка при получении роли: {e}")
        return "непроверенный"

# 📈 Вероятность скама
def get_risk(role):
    return {
        "владелец": "0%",
        "гарант": "0%",
        "владелец чата": "10%",
        "отказ от гаранта": "80%",
        "скамер": "100%",
        "непроверенный": "50% (лучше ходить гарантом)"
    }.get(role, "50%")

# 🔁 Команда /start
@bot.message_handler(commands=['start'])
def handle_start(msg):
    chats.add(msg.chat.id)
    bot.reply_to(msg, "🤖 Бот активен и готов к работе!\n\nИспользуйте /help для списка команд.")

# 🔍 Команда /help или "хелп"
@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() == "хелп")
def handle_help(msg):
    chats.add(msg.chat.id)
    bot.reply_to(msg, "📋 Доступные команды:\n/start — Проверить, что бот активен\nчек — Просмотреть профиль пользователя\nчек @username — Проверить профиль по юзернейму\nзанести &lt;роль&gt; — Добавить пользователя в базу\nзанести @username &lt;роль&gt; — Занести по юзернейму\nвынести — Удалить из базы\nкоманды — Показать список команд")

# 📋 Команда "команды"
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() == "команды")
def handle_commands(msg):
    chats.add(msg.chat.id)
    text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Проверить, что бот активен\n"
        "чек — Просмотреть профиль пользователя (ответом)\n"
        "чек @username — Проверить профиль по юзернейму\n"
        "занести &lt;роль&gt; — Добавить пользователя в базу (ответом)\n"
        "занести @username &lt;роль&gt; — Занести по юзернейму\n"
        "вынести — Удалить из базы (ответом или @username)\n"
        "команды — Показать список доступных команд"
    )
    bot.reply_to(msg, text)

# 👀 Чек
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)
    
    parts = msg.text.strip().split()
    
    # Проверяем, есть ли username в команде
    if len(parts) >= 2 and parts[1].startswith("@"):
        # Чек по username
        username = parts[1][1:]  # убираем @
        target_name = f"@{username}"
        target_id = f"@{username}"
        role = get_role(target_id)
        risk = get_risk(role)
        
        text = (
            f"👤 Профиль: {target_name}\n"
            f"🔹 Роль: <code>{role}</code>\n"
            f"📊 Вероятность скама: <code>{risk}</code>"
        )
    else:
        # Чек ответом на сообщение или себя
        user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
        role = get_role(user.id)
        risk = get_risk(role)
        text = (
            f"👤 Профиль: <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
            f"🔹 Роль: <code>{role}</code>\n"
            f"📊 Вероятность скама: <code>{risk}</code>"
        )
    
    bot.reply_to(msg, text)

# ➕ Занести <роль>
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    chats.add(msg.chat.id)
    
    caller_role = get_role(msg.from_user.id)
    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Примеры:\nзанести скамер (ответом на сообщение)\nзанести @username скамер")
        return

    # Проверяем, есть ли username в команде
    if parts[1].startswith("@"):
        # Занесение по username
        if len(parts) < 3:
            bot.reply_to(msg, "Пример: занести @MidGARANT скамер")
            return
        
        username = parts[1][1:]  # убираем @
        role = parts[2].lower()
        
        # Заносим сразу по username без поиска
        target_name = f"@{username}"
        target_id = f"@{username}"  # Используем username как ID
        
    else:
        # Занесение ответом на сообщение
        if not msg.reply_to_message:
            bot.reply_to(msg, "Ответьте на сообщение пользователя или используйте: занести @username роль")
            return
        
        role = parts[1].lower()
        target = msg.reply_to_message.from_user
        target_name = target.first_name
        target_id = target.id

    allowed_roles = ["скамер", "гарант", "владелец_чата", "отказ", "отказ_от_гаранта"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Допустимые роли: скамер, гарант, владелец_чата, отказ")
        return

    if caller_role in ["гарант", "владелец чата"] and role == "гарант":
        bot.reply_to(msg, "❌ Гарант и владелец чата не могут заносить гарантов.")
        return

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "Нельзя менять роль владельцу.")
        return

    # Правильное определение роли для базы данных
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
        cursor.execute("REPLACE INTO users (user_id, role, scam_percent) VALUES (%s, %s, %s)", (str(target_id), role_text, scam_percent))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        bot.reply_to(msg, f"Ошибка базы данных: {e}")
        return

    # 💥 Рассылка если скамер
    if role_text == "скамер":
        alert_text = f"⚠️ <a href='tg://user?id={target_id}'>{target_name}</a> занесён в базу как <b>СКАМЕР</b>!"
        for chat_id in chats:
            try:
                bot.send_message(chat_id, alert_text)
            except Exception as e:
                print(f"Ошибка при рассылке в {chat_id}: {e}")

    bot.reply_to(msg, f"{target_name} ‼️ ЗАНЕСЕН В БАЗУ КАК {role_text.upper()}")

# ➖ Вынести (удалить из базы)
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("вынести"))
def handle_remove_user(msg):
    chats.add(msg.chat.id)
    
    caller_role = get_role(msg.from_user.id)
    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    parts = msg.text.strip().split()
    
    # Проверяем, есть ли username в команде
    if len(parts) >= 2 and parts[1].startswith("@"):
        # Вынести по username
        username = parts[1][1:]  # убираем @
        target_name = f"@{username}"
        target_id = f"@{username}"
        
    else:
        # Вынести ответом на сообщение
        if not msg.reply_to_message:
            bot.reply_to(msg, "Ответьте на сообщение пользователя или используйте: вынести @username")
            return
        
        target = msg.reply_to_message.from_user
        target_name = target.first_name
        target_id = target.id

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "Нельзя выносить владельца.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = %s", (str(target_id),))
        
        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(msg, f"✅ {target_name} удален из базы данных")
        else:
            bot.reply_to(msg, f"❌ {target_name} не найден в базе данных")
        
        cursor.close()
        conn.close()
    except Error as e:
        bot.reply_to(msg, f"Ошибка базы данных: {e}")

# 👥 Новый участник
@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    chats.add(message.chat.id)
    for user in message.new_chat_members:
        user_id = user.id
        role = get_role(user_id)
        risk = get_risk(role)
        if role == "непроверенный":
            bot.send_message(
                message.chat.id,
                f"🚨 Новый пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> не найден в базе.\n"
                f"Роль: <code>{role}</code>\n"
                f"📊 Шанс скама: <code>{risk}</code>"
            )

# Автопроверка в чате
@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def auto_check_group(msg):
    chats.add(msg.chat.id)
    user = msg.from_user
    role = get_role(user.id)
    if role == "скамер":
        bot.reply_to(msg,
            f"⚠️ Осторожно! Игрок <a href='tg://user?id={user.id}'>{user.first_name}</a> занесён в базу как <b>СКАМЕР</b>."
        )

# 📥 Регистрируем чаты (последний обработчик для всех остальных сообщений)
@bot.message_handler(func=lambda msg: True)
def register_chat(msg):
    chats.add(msg.chat.id)

# 🔁 Старт бота
print("Бот запускается...")
try:
    bot.infinity_polling()
except Exception as e:
    print(f"Ошибка при запуске бота: {e}")
