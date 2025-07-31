
import telebot
import mysql.connector
from mysql.connector import Error
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8363145008:AAEM6OSKNRjX3SDU6yINZwbMOEcsaOQVdiI"
OWNER_IDS = [7537570296, 5821123636]
# Словарь соответствия username владельцев (без @)
OWNER_USERNAMES = {
    "midgarant": 7537570296,  # ваш username в нижнем регистре
    "MidGarant": 7537570296,  # дублируем для совместимости
    # добавьте других владельцев если нужно
}

DB_HOST = "sql8.freesqldatabase.com"
DB_USER = "sql8792761"
DB_PASSWORD = "1upRsp7dLm"
DB_NAME = "sql8792761"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
chats = set()

def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"
    )

def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(100) PRIMARY KEY,
                username VARCHAR(100),
                role VARCHAR(50) DEFAULT 'непроверенный',
                scam_percent VARCHAR(10) DEFAULT '50%'
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Ошибка при создании таблицы: {e}")

init_db()

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

def normalize_user_id(user_id, username=None):
    """Нормализует ID пользователя - приоритет username с @"""
    if username:
        return f"@{username.lower()}"
    return str(user_id)

def get_user_role(user_id, username=None):
    """Получает роль пользователя"""
    try:
        # Проверяем владельцев по ID
        if isinstance(user_id, int) and user_id in OWNER_IDS:
            return "владелец"
        
        # Проверяем владельцев по username
        if username and username.lower() in [k.lower() for k in OWNER_USERNAMES.keys()]:
            return "владелец"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Если передан username, ищем по нему
        if username:
            cursor.execute("SELECT role FROM users WHERE LOWER(user_id) = LOWER(%s) OR LOWER(user_id) = LOWER(%s)", 
                          (f"@{username}", username))
            result = cursor.fetchone()
            if result and result[0]:
                cursor.close()
                conn.close()
                return result[0]
        
        # Ищем по ID
        if user_id:
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (str(user_id),))
            result = cursor.fetchone()
            if result and result[0]:
                cursor.close()
                conn.close()
                return result[0]
        
        cursor.close()
        conn.close()
        return "непроверенный"
    except Exception as e:
        print(f"Ошибка при получении роли: {e}")
        return "непроверенный"

def save_user_role(user_id, username, role, scam_percent):
    """Сохраняет роль пользователя с единой логикой"""
    try:
        normalized_id = normalize_user_id(user_id, username)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Удаляем все старые записи для этого пользователя
        cursor.execute("DELETE FROM users WHERE user_id = %s OR LOWER(user_id) = LOWER(%s)", 
                      (str(user_id), f"@{username.lower()}" if username else ""))
        
        if username:
            cursor.execute("DELETE FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        
        # Вставляем новую запись
        cursor.execute(
            "INSERT INTO users (user_id, username, role, scam_percent) VALUES (%s, %s, %s, %s)",
            (normalized_id, username.lower() if username else None, role, scam_percent)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Error as e:
        print(f"Ошибка при сохранении роли: {e}")
        return False

def delete_user(user_id, username):
    """Удаляет пользователя из БД"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Удаляем все возможные записи
        cursor.execute("DELETE FROM users WHERE user_id = %s OR LOWER(user_id) = LOWER(%s)", 
                      (str(user_id), f"@{username.lower()}" if username else ""))
        
        if username:
            cursor.execute("DELETE FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        
        rowcount = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return rowcount > 0
    except Error as e:
        print(f"Ошибка при удалении: {e}")
        return False

def format_user_profile(user_id, username, first_name):
    """Форматирует профиль пользователя"""
    if username:
        return f"<a href='https://t.me/{username}'>@{username}</a>"
    else:
        return f"<a href='tg://user?id={user_id}'>{first_name}</a>"

def get_all_scammers():
    """Получает всех скамеров и пользователей с отказом от гаранта"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, role FROM users WHERE role IN ('скамер', 'отказ от гаранта')")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Ошибка при получении скамеров: {e}")
        return []

def create_admin_keyboard():
    """Создает клавиатуру для админ-панели"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Список скамеров", callback_data="list_scammers"))
    markup.row(InlineKeyboardButton("🚫 Список отказов от гаранта", callback_data="list_refuses"))
    markup.row(InlineKeyboardButton("📊 Все проблемные", callback_data="list_all"))
    markup.row(InlineKeyboardButton("👥 Все пользователи", callback_data="list_users"))
    markup.row(InlineKeyboardButton("✏️ Изменить пользователя", callback_data="edit_user"))
    markup.row(InlineKeyboardButton("🔄 Обновить", callback_data="refresh_admin"))
    return markup

def create_edit_keyboard():
    """Создает клавиатуру для редактирования"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔴 Скамер (100%)", callback_data="edit_role_scammer"))
    markup.row(InlineKeyboardButton("🟡 Отказ от гаранта (80%)", callback_data="edit_role_refuse"))
    markup.row(InlineKeyboardButton("🟢 Гарант (0%)", callback_data="edit_role_garant"))
    markup.row(InlineKeyboardButton("🔵 Владелец чата (10%)", callback_data="edit_role_owner"))
    markup.row(InlineKeyboardButton("⚪ Непроверенный (50%)", callback_data="edit_role_unverified"))
    markup.row(InlineKeyboardButton("🔢 Изменить процент", callback_data="edit_percent"))
    markup.row(InlineKeyboardButton("🗑️ Удалить из БД", callback_data="edit_delete"))
    markup.row(InlineKeyboardButton("◀️ Назад", callback_data="refresh_admin"))
    return markup

def get_all_users():
    """Получает всех пользователей из БД"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, role, scam_percent FROM users ORDER BY role")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Ошибка при получении пользователей: {e}")
        return []

def update_user_role_by_id(user_id, new_role, new_percent):
    """Обновляет роль и процент пользователя по ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = %s, scam_percent = %s WHERE user_id = %s", 
                      (new_role, new_percent, user_id))
        rowcount = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return rowcount > 0
    except Exception as e:
        print(f"Ошибка при обновлении пользователя: {e}")
        return False

# Временное хранилище для редактирования
edit_sessions = {}

@bot.message_handler(commands=["start"])
def start_command(msg):
    bot.reply_to(msg, "👋 Привет! Я активен. Используй /help, чтобы увидеть доступные команды.")

@bot.message_handler(commands=["help"])
def help_command(msg):
    text = (
        "<b>📘 Команды:</b>\n"
        "— <code>чек</code> (в ответ на сообщение или для проверки себя)\n"
        "— <code>занести</code> (только в ответ на сообщение)\n"
        "— <code>вынести</code> (только в ответ на сообщение)\n"
        "\n"
        "Бот активен и работает ✅"
    )
    bot.reply_to(msg, text)

@bot.message_handler(commands=["admin"])
def admin_panel(msg):
    """Админ-панель только для владельцев в приватных чатах"""
    if msg.chat.type != "private":
        return
    
    if msg.from_user.id not in OWNER_IDS:
        bot.reply_to(msg, "❌ У вас нет доступа к админ-панели")
        return
    
    markup = create_admin_keyboard()
    bot.reply_to(msg, "🔧 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callbacks(call):
    """Обработчик кнопок админ-панели"""
    if call.from_user.id not in OWNER_IDS:
        bot.answer_callback_query(call.id, "❌ Нет доступа")
        return
    
    try:
        if call.data == "list_scammers":
            scammers = get_all_scammers()
            scammer_list = [user for user in scammers if user[2] == "скамер"]
            
            if not scammer_list:
                text = "📋 <b>Список скамеров:</b>\n\n❌ Скамеров не найдено"
            else:
                text = f"📋 <b>Список скамеров ({len(scammer_list)}):</b>\n\n"
                for user_id, username, role in scammer_list:
                    if user_id.startswith("@"):
                        text += f"• <a href='https://t.me/{user_id[1:]}'>{user_id}</a>\n"
                    else:
                        text += f"• ID: <code>{user_id}</code>\n"
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "list_refuses":
            scammers = get_all_scammers()
            refuse_list = [user for user in scammers if user[2] == "отказ от гаранта"]
            
            if not refuse_list:
                text = "🚫 <b>Список отказов от гаранта:</b>\n\n❌ Отказов не найдено"
            else:
                text = f"🚫 <b>Список отказов от гаранта ({len(refuse_list)}):</b>\n\n"
                for user_id, username, role in refuse_list:
                    if user_id.startswith("@"):
                        text += f"• <a href='https://t.me/{user_id[1:]}'>{user_id}</a>\n"
                    else:
                        text += f"• ID: <code>{user_id}</code>\n"
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "list_all":
            scammers = get_all_scammers()
            
            if not scammers:
                text = "📊 <b>Все проблемные пользователи:</b>\n\n❌ Проблемных пользователей не найдено"
            else:
                text = f"📊 <b>Все проблемные пользователи ({len(scammers)}):</b>\n\n"
                for user_id, username, role in scammers:
                    role_emoji = "🔴" if role == "скамер" else "🟡"
                    if user_id.startswith("@"):
                        text += f"{role_emoji} <a href='https://t.me/{user_id[1:]}'>{user_id}</a> - <code>{role}</code>\n"
                    else:
                        text += f"{role_emoji} ID: <code>{user_id}</code> - <code>{role}</code>\n"
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "list_users":
            users = get_all_users()
            
            if not users:
                text = "👥 <b>Все пользователи:</b>\n\n❌ Пользователей не найдено"
            else:
                text = f"👥 <b>Все пользователи ({len(users)}):</b>\n\n"
                for user_id, username, role, percent in users:
                    role_emoji = {"скамер": "🔴", "отказ от гаранта": "🟡", "гарант": "🟢", "владелец чата": "🔵"}.get(role, "⚪")
                    if user_id.startswith("@"):
                        text += f"{role_emoji} <a href='https://t.me/{user_id[1:]}'>{user_id}</a> - <code>{role}</code> ({percent})\n"
                    else:
                        text += f"{role_emoji} ID: <code>{user_id}</code> - <code>{role}</code> ({percent})\n"
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "edit_user":
            text = "✏️ <b>Редактирование пользователя</b>\n\nОтправьте ID пользователя или @username для редактирования:"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=create_admin_keyboard(), parse_mode="HTML")
            # Устанавливаем режим ожидания ID
            edit_sessions[call.from_user.id] = {"waiting_for_id": True, "message_id": call.message.message_id}
        
        elif call.data == "refresh_admin":
            markup = create_admin_keyboard()
            bot.edit_message_text("🔧 <b>Админ-панель</b>\n\nВыберите действие:", 
                                 call.message.chat.id, call.message.message_id, 
                                 reply_markup=markup, parse_mode="HTML")
        
        elif call.data.startswith("edit_role_"):
            role_map = {
                "edit_role_scammer": ("скамер", "100%"),
                "edit_role_refuse": ("отказ от гаранта", "80%"),
                "edit_role_garant": ("гарант", "0%"),
                "edit_role_owner": ("владелец чата", "10%"),
                "edit_role_unverified": ("непроверенный", "50%")
            }
            
            if call.from_user.id in edit_sessions and "target_id" in edit_sessions[call.from_user.id]:
                target_id = edit_sessions[call.from_user.id]["target_id"]
                new_role, new_percent = role_map[call.data]
                
                if update_user_role_by_id(target_id, new_role, new_percent):
                    text = f"✅ <b>Пользователь обновлен</b>\n\nID: <code>{target_id}</code>\nРоль: <code>{new_role}</code>\nПроцент: <code>{new_percent}</code>"
                    del edit_sessions[call.from_user.id]
                else:
                    text = "❌ Ошибка при обновлении пользователя"
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "edit_delete":
            if call.from_user.id in edit_sessions and "target_id" in edit_sessions[call.from_user.id]:
                target_id = edit_sessions[call.from_user.id]["target_id"]
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM users WHERE user_id = %s", (target_id,))
                    success = cursor.rowcount > 0
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    if success:
                        text = f"✅ <b>Пользователь удален</b>\n\nID: <code>{target_id}</code>"
                    else:
                        text = "❌ Пользователь не найден в БД"
                    
                    del edit_sessions[call.from_user.id]
                except Exception as e:
                    text = f"❌ Ошибка при удалении: {e}"
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        elif call.data == "edit_percent":
            if call.from_user.id in edit_sessions and "target_id" in edit_sessions[call.from_user.id]:
                text = "🔢 <b>Изменение процента</b>\n\nОтправьте новый процент (например: 25%):"
                edit_sessions[call.from_user.id]["waiting_for_percent"] = True
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
    
    except Exception as e:
        print(f"Ошибка в callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)
    
    # Если команда без ответа - проверяем себя
    if not msg.reply_to_message:
        user = msg.from_user
        role = get_user_role(user.id, user.username)
        risk = get_risk(role)
        profile_link = format_user_profile(user.id, user.username, user.first_name)
        
        text = (
            f"👤 Ваш профиль: {profile_link}\n"
            f"🔹 Роль: <code>{role}</code>\n"
            f"📊 Вероятность скама: <code>{risk}</code>"
        )
        bot.reply_to(msg, text)
        return
    
    # Проверка по ответу на сообщение
    if msg.reply_to_message:
        user = msg.reply_to_message.from_user
        role = get_user_role(user.id, user.username)
        risk = get_risk(role)
        profile_link = format_user_profile(user.id, user.username, user.first_name)
            
        text = (
            f"👤 Профиль: {profile_link}\n"
            f"🔹 Роль: <code>{role}</code>\n"
            f"📊 Вероятность скама: <code>{risk}</code>"
        )
        bot.reply_to(msg, text)
        return

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("занести"))
def handle_add_role(msg):
    chats.add(msg.chat.id)
    caller_role = get_user_role(msg.from_user.id, msg.from_user.username)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    parts = msg.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(msg, "Пример: занести скамер (ответом на сообщение)")
        return

    if not msg.reply_to_message:
        bot.reply_to(msg, "❌ Ответьте на сообщение пользователя")
        return
    
    role = parts[1].lower()
    target = msg.reply_to_message.from_user
    target_id = target.id
    target_username = target.username
    profile_link = format_user_profile(target.id, target.username, target.first_name)

    allowed_roles = ["скамер", "гарант", "владелец_чата", "отказ", "отказ_от_гаранта"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Роли: скамер, гарант, владелец_чата, отказ, отказ_от_гаранта")
        return

    if caller_role in ["гарант", "владелец чата"] and role == "гарант":
        bot.reply_to(msg, "❌ Нельзя заносить гарантов.")
        return

    # Проверка на владельца
    if target_username and target_username.lower() in [k.lower() for k in OWNER_USERNAMES.keys()]:
        bot.reply_to(msg, "❌ Нельзя менять роль владельцу.")
        return
    
    if target_id and target_id in OWNER_IDS:
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

    if not save_user_role(target_id, target_username, role_text, scam_percent):
        bot.reply_to(msg, "❌ Ошибка при сохранении в БД")
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
    caller_role = get_user_role(msg.from_user.id, msg.from_user.username)

    if msg.chat.type != "private":
        if msg.from_user.id not in OWNER_IDS and caller_role not in ["гарант", "владелец чата"]:
            return

    if not msg.reply_to_message:
        bot.reply_to(msg, "❌ Ответьте на сообщение пользователя")
        return
    
    target = msg.reply_to_message.from_user
    target_id = target.id
    target_username = target.username
    profile_link = format_user_profile(target.id, target.username, target.first_name)

    # Проверка на владельца
    if target_username and target_username.lower() in [k.lower() for k in OWNER_USERNAMES.keys()]:
        bot.reply_to(msg, "❌ Нельзя выносить владельца.")
        return
    
    if target_id and target_id in OWNER_IDS:
        bot.reply_to(msg, "❌ Нельзя выносить владельца.")
        return

    if delete_user(target_id, target_username):
        bot.reply_to(msg, f"✅ {profile_link} удален из базы")
    else:
        bot.reply_to(msg, f"❌ {profile_link} не найден")

@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    chats.add(message.chat.id)
    for user in message.new_chat_members:
        role = get_user_role(user.id, user.username)
        risk = get_risk(role)
        if role == "непроверенный":
            bot.send_message(
                message.chat.id,
                f"🚨 Новый пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
                f"Роль: <code>{role}</code>\n📊 Риск: <code>{risk}</code>"
            )

@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def auto_check_group(msg):
    chats.add(msg.chat.id)
    user = msg.from_user
    role = get_user_role(user.id, user.username)
    if role == "скамер":
        bot.reply_to(msg, f"⚠️ Осторожно! <a href='tg://user?id={user.id}'>{user.first_name}</a> — <b>СКАМЕР</b>.")

@bot.message_handler(func=lambda msg: msg.chat.type == "private" and msg.from_user.id in edit_sessions)
def handle_edit_input(msg):
    """Обработчик ввода для редактирования в админ-панели"""
    user_id = msg.from_user.id
    session = edit_sessions.get(user_id, {})
    
    if session.get("waiting_for_id"):
        # Получили ID для редактирования
        target_input = msg.text.strip()
        
        # Проверяем существование пользователя в БД
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            if target_input.startswith("@"):
                cursor.execute("SELECT user_id, role, scam_percent FROM users WHERE LOWER(user_id) = LOWER(%s)", (target_input,))
            else:
                cursor.execute("SELECT user_id, role, scam_percent FROM users WHERE user_id = %s", (target_input,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                user_db_id, current_role, current_percent = result
                session["target_id"] = user_db_id
                session["waiting_for_id"] = False
                edit_sessions[user_id] = session
                
                text = f"👤 <b>Редактирование пользователя</b>\n\nID: <code>{user_db_id}</code>\nТекущая роль: <code>{current_role}</code>\nТекущий процент: <code>{current_percent}</code>\n\nВыберите действие:"
                
                try:
                    bot.edit_message_text(text, msg.chat.id, session["message_id"], 
                                         reply_markup=create_edit_keyboard(), parse_mode="HTML")
                except:
                    bot.send_message(msg.chat.id, text, reply_markup=create_edit_keyboard(), parse_mode="HTML")
            else:
                text = f"❌ Пользователь <code>{target_input}</code> не найден в базе данных"
                try:
                    bot.edit_message_text(text, msg.chat.id, session["message_id"], 
                                         reply_markup=create_admin_keyboard(), parse_mode="HTML")
                except:
                    bot.send_message(msg.chat.id, text, reply_markup=create_admin_keyboard(), parse_mode="HTML")
                del edit_sessions[user_id]
        
        except Exception as e:
            print(f"Ошибка при поиске пользователя: {e}")
            text = "❌ Ошибка при поиске пользователя"
            try:
                bot.edit_message_text(text, msg.chat.id, session["message_id"], 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
            except:
                bot.send_message(msg.chat.id, text, reply_markup=create_admin_keyboard(), parse_mode="HTML")
            del edit_sessions[user_id]
    
    elif session.get("waiting_for_percent"):
        # Получили новый процент
        new_percent = msg.text.strip()
        
        if not new_percent.endswith("%"):
            new_percent += "%"
        
        target_id = session["target_id"]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET scam_percent = %s WHERE user_id = %s", (new_percent, target_id))
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            conn.close()
            
            if success:
                text = f"✅ <b>Процент обновлен</b>\n\nID: <code>{target_id}</code>\nНовый процент: <code>{new_percent}</code>"
            else:
                text = "❌ Ошибка при обновлении процента"
            
            del edit_sessions[user_id]
            
            try:
                bot.edit_message_text(text, msg.chat.id, session["message_id"], 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
            except:
                bot.send_message(msg.chat.id, text, reply_markup=create_admin_keyboard(), parse_mode="HTML")
        
        except Exception as e:
            print(f"Ошибка при обновлении процента: {e}")
            text = "❌ Ошибка при обновлении процента"
            try:
                bot.edit_message_text(text, msg.chat.id, session["message_id"], 
                                     reply_markup=create_admin_keyboard(), parse_mode="HTML")
            except:
                bot.send_message(msg.chat.id, text, reply_markup=create_admin_keyboard(), parse_mode="HTML")
            del edit_sessions[user_id]

@bot.message_handler(func=lambda msg: True)
def register_chat(msg):
    chats.add(msg.chat.id)

print("Бот запускается...")
try:
    bot.infinity_polling()
except Exception as e:
    print(f"Ошибка при запуске бота: {e}")
