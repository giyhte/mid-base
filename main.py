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

# 🔢 Получение риска по роли
def get_risk(role):
    risks = {
        "владелец": "0%",
        "гарант": "0%",
        "владелец чата": "10%",
        "отказ от гаранта": "80%",
        "скамер": "100%",
        "непроверенный": "50%"
    }
    return risks.get(role, "50%")

# 📊 Получение роли пользователя
def get_role(user_id, username=None):
    try:
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "владелец"

        conn = get_connection()
        cursor = conn.cursor()

        if isinstance(user_id, str) and user_id.startswith("@"):
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (str(user_id),))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result[0]:
            return result[0]
        return "непроверенный"
    except Exception as e:
        print(f"Ошибка при получении роли: {e}")
        return "непроверенный"

# 👀 Чек
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)
    user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    role = get_role(user.id)
    risk = get_risk(role)
    text = (
        f"👤 Профиль: <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"🔹 Роль: <code>{role}</code>\n"
        f"📊 Вероятность скама: <code>{risk}</code>"
    )
    bot.reply_to(msg, text)

# ➕ Занести
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Примеры:\nзанести скамер (ответом)\nзанести @username скамер")
        return

    if parts[1].startswith("@"):
        if len(parts) < 3:
            bot.reply_to(msg, "Пример: занести @MidGARANT скамер")
            return
        username = parts[1][1:]
        role = parts[2].lower()
        target_id = f"@{username}"
        target_name = f"@{username}"
    else:
        if not msg.reply_to_message:
            bot.reply_to(msg, "Ответьте на сообщение или используйте занести @username роль")
            return
        role = parts[1].lower()
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name

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
        alert = f"⚠️ <a href='tg://user?id={target_id}'>{target_name}</a> занесён как <b>СКАМЕР</b>!"
        for chat_id in chats:
            try:
                bot.send_message(chat_id, alert)
            except Exception as e:
                print(f"Не удалось отправить в чат {chat_id}: {e}")

    bot.reply_to(msg, f"{target_name} ✅ занесён как {role_text.upper()}")

# ➖ Вынести
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("вынести"))
def handle_remove_user(msg):
    chats.add(msg.chat.id)
    caller_role = get_role(msg.from_user.id)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    parts = msg.text.strip().split()

    if len(parts) >= 2 and parts[1].startswith("@"):
        username = parts[1][1:]
        target_id = f"@{username}"
        target_name = f"@{username}"
    else:
        if not msg.reply_to_message:
            bot.reply_to(msg, "Ответьте на сообщение или используйте: вынести @username")
            return
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name

    if isinstance(target_id, int) and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя выносить владельца.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = %s", (str(target_id),))
        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(msg, f"✅ {target_name} удален из базы")
        else:
            bot.reply_to(msg, f"❌ {target_name} не найден")
        cursor.close()
        conn.close()
    except Error as e:
        bot.reply_to(msg, f"Ошибка БД: {e}")

# Новые участники
@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    chats.add(message.chat.id)
    for user in message.new_chat_members:
        role = get_role(user.id)
        risk = get_risk(role)
        if role == "непроверенный":
            bot.send_message(
                message.chat.id,
                f"🚨 Новый пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
                f"Роль: <code>{role}</code>\n📊 Риск: <code>{risk}</code>"
            )

# Авточек в чатах
@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def auto_check_group(msg):
    chats.add(msg.chat.id)
    user = msg.from_user
    role = get_role(user.id)
    if role == "скамер":
        bot.reply_to(msg, f"⚠️ Осторожно! <a href='tg://user?id={user.id}'>{user.first_name}</a> — <b>СКАМЕР</b>.")

# Обработка всего
@bot.message_handler(func=lambda msg: True)
def register_chat(msg):
    chats.add(msg.chat.id)

# 🔁 Старт бота
print("Бот запускается...")
try:
    bot.infinity_polling()
except Exception as e:
    print(f"Ошибка при запуске бота: {e}")
