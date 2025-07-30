import telebot
import json
import os

# Токен и ID владельца
BOT_TOKEN = "8363145008:AAEM6OSKNRjX3SDU6yINZwbMOEcsaOQVdiI"
OWNER_ID = 7537570296
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# База данных
db_path = "mid_base.json"

def load_or_init_db():
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
        except json.JSONDecodeError:
            db = {}
    else:
        db = {}

    if "users" not in db:
        db["users"] = {}
    if "banned" not in db:
        db["banned"] = []
    if "reports" not in db:
        db["reports"] = {}
    
    return db

db = load_or_init_db()

def save_db():
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def get_role(user_id: int) -> str:
    if str(user_id) == str(OWNER_ID):
        return "владелец"
    return db["users"].get(str(user_id), {}).get("role", "непроверенный")

def get_risk(role: str) -> str:
    return {
        "владелец": "0%",
        "гарант": "0%",
        "отказ от гаранта": "80%",
        "скамер": "100%",
        "непроверенный": "50% (лучше ходить гарантом)"
    }.get(role, "50%")

# /старт
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() == "хелп")
def handle_start(msg):
    bot.reply_to(msg, " 📋 Доступные команды: старт — Проверить, что бот активен чек — Просмотреть профиль пользователя (ответом на сообщение или своё) занести <роль> — Добавить пользователя в базу (ответом на сообщение) команды — Показать список доступных команд)")

# /команды
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() == "команды")
def handle_commands(msg):
    text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "старт — Проверить, что бот активен\n"
        "чек — Просмотреть профиль пользователя (ответом на сообщение или своё)\n"
        "занести <роль> — Добавить пользователя в базу (ответом на сообщение)\n"
        "команды — Показать список доступных команд"
    )
    bot.reply_to(msg, text)

# /чек
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    role = get_role(user.id)
    risk = get_risk(role)
    text = (
        f"👤 Профиль: <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"🔹 Роль: <code>{role}</code>\n"
        f"📊 Вероятность скама: <code>{risk}</code>"
    )
    bot.reply_to(msg, text)

# /занести <роль>
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    if not msg.reply_to_message:
        bot.reply_to(msg, "Ответьте на сообщение пользователя.")
        return

    # Кто вызывает команду и его роль
    caller_role = get_role(msg.from_user.id)

    # В группах менять роли может только владелец и гарант с ограничениями
    if msg.chat.type != "private":
        if msg.from_user.id != OWNER_ID and caller_role != "гарант":
            return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: занести скамер")
        return

    role = parts[1].lower()
    allowed_roles = ["скамер", "гарант", "отказ", "отказ_от_гаранта"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Допустимые роли: скамер, гарант, отказ")
        return

    # Проверка, если вызывающий — гарант, то он не может заносить роль гарант
    if caller_role == "гарант" and role == "гарант":
        bot.reply_to(msg, "❌ Роль гарант не может заносить других гарантов.")
        return

    target = msg.reply_to_message.from_user
    if target.id == OWNER_ID:
        bot.reply_to(msg, "Нельзя менять роль владельцу.")
        return

    role_text = "отказ от гаранта" if role.startswith("отказ") else role
    db["users"][str(target.id)] = {"role": role_text}

    # Если отказ от гаранта — добавим фиксированный процент скама
    if role_text == "отказ от гаранта":
        db["users"][str(target.id)]["scam_percent"] = "80%"

    save_db()
    bot.reply_to(msg, f"{target.first_name} ‼️ ЗАНЕСЕН В БАЗУ КАК {role_text.upper()}")

# Автопроверка в группах
@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def auto_check_group(msg):
    user = msg.from_user
    role = get_role(user.id)
    if role == "скамер":
        bot.reply_to(msg,
            f"⚠️ Осторожно! Игрок <a href='tg://user?id={user.id}'>{user.first_name}</a> занесён в базу как <b>СКАМЕР</b>."
        )

# Новый участник - через content_types
@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    for user in message.new_chat_members:
        user_id = str(user.id)
        if user_id not in db["users"]:
            role = "непроверенный"
            risk = get_risk(role)
            bot.send_message(
                message.chat.id,
                f"🚨 Новый пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> не найден в базе.\n"
                f"Роль: <code>{role}</code>\n"
                f"📊 Шанс скама: <code>{risk}</code>"
            )

bot.infinity_polling()
