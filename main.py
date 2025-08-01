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

            # Таблица user_permissions теперь не удаляется при перезапуске

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

            # Создаем таблицу для прав пользователей на команды
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
                command_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
                has_permission BOOLEAN DEFAULT TRUE,
                granted_by VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_command (user_id, command_name)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci""")

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
    user_id = msg.from_user.id

    # Базовые команды доступные всем
    text = (
        "📘 Команды:\n"
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

    # Команды только для владельцев
    if user_id in OWNER_IDS:
        text += "— +кмд команда (в ответ на сообщение) — выдать права\n"
        text += "— -кмд команда (в ответ на сообщение) — отнять права\n"
        text += "— /гс (текст сообщения) — отправить глобальное сообщение во все чаты\n"
        text += "— /чаты — посмотреть список активных чатов\n"

    text += (
        "\nДоступные роли: скамер, гарант, владелец_чата, проверенный, отказ_от_гаранта\n"
        "\nПримеры с username:\n"
        "— чек @username\n"
        "— занести @username проверенный\n"
        "— вынести @username\n"
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
            "SELECT has_permission FROM user_permissions WHERE CAST(user_id AS CHAR) = %s AND CAST(command_name AS CHAR) = %s",
            (user_id_str, command_name_str)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        # Если найдена явная запись о правах, используем её
        if result is not None:
            return bool(result[0])

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
            REPLACE INTO user_permissions (user_id, command_name, has_permission, granted_by, granted_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (str(user_id), command_name, has_permission, str(granted_by)))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при изменении прав для {user_id}, команда {command_name}: {e}")
        return False

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith("чек"))
def handle_check(msg):
    chats.add(msg.chat.id)

    parts = msg.text.strip().split()

    # Если указан username
    if len(parts) > 1 and parts[1].startswith('@'):
        username = parts[1]

        # Сначала ищем в нашей базе данных
        user_id = find_user_by_username(username.lstrip('@'))

        if user_id:
            # Нашли в базе данных
            role = get_role(user_id)
            risk = get_risk(user_id)
            profile_link = f"<a href='tg://user?id={user_id}'>{username}</a>"

            text = (
                f"👤 Профиль: {profile_link}\n"
                f"🔹 Роль: {role}\n"
                f"📊 Вероятность скама: {risk}"
            )
        else:
            # Пытаемся найти через API Telegram
            user_info = get_user_by_username(username)
            if user_info:
                user_id = user_info.id
                user_name = user_info.first_name
                role = get_role(user_id)
                risk = get_risk(user_id)
                profile_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"

                # Сохраняем связь username -> user_id
                save_username_mapping(user_id, username.lstrip('@'))

                text = (
                    f"👤 Профиль: {profile_link}\n"
                    f"🔹 Роль: {role}\n"
                    f"📊 Вероятность скама: {risk}"
                )
            else:
                text = f"❌ Пользователь {username} не найден"
    else:
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
                # Сохраняем связь username -> temp_id
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

    allowed_roles = ["скамер", "гарант", "владелец_чата", "отказ", "отказ_от_гаранта", "проверенный"]
    if role not in allowed_roles:
        bot.reply_to(msg, "Роли: скамер, гарант, владелец_чата, отказ, отказ_от_гаранта, проверенный")
        return

    if caller_role in ["гарант", "владелец чата"] and role == "гарант":
        bot.reply_to(msg, "❌ Нельзя заносить гарантов.")
        return

    # Проверяем права на выдачу роли "проверенный"
    if role == "проверенный" and caller_role not in ["владелец", "владелец чата"]:
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
        # Создаем сообщение с кликабельной ссылкой на профиль
        if len(parts) >= 3 and parts[1].startswith('@'):
            # Если через username, создаем ссылку на профиль через ID
            alert = f"⚠️ <a href='tg://user?id={target_id}'>Пользователь</a> (@{username.lstrip('@')}) занесён как <b>СКАМЕР</b>!"
        else:
            # Если через reply, используем обычную ссылку
            alert = f"⚠️ {profile_link} занесён как <b>СКАМЕР</b>!"

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
                # Если пользователь не найден, проверяем есть ли он в базе по username
                import hashlib
                temp_id = abs(hash(username.lstrip('@'))) % (10**9)
                user_id = temp_id
                target_name = username.lstrip('@')
                print(f"Ищем пользователя с временным ID {temp_id} для username {username}")
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
        profile_link = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"
    else:
        bot.reply_to(msg, "Ответьте на сообщение пользователя или укажите @username.\nПример: вынести @username")
        return

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
        for (user_id,) in guarantors:
            if int(user_id) not in OWNER_IDS:
                filtered_guarantors.append((user_id,))
        
        if not filtered_guarantors:
            bot.reply_to(msg, "📋 В активном списке гарантов базы нет зарегистрированных пользователей.")
            return
        
        # Формируем список гарантов с кликабельными ссылками на профили
        guarantor_list = []
        for (user_id,) in filtered_guarantors:
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
        bot.reply_to(msg, "Пример: +кмд занести (в ответ на сообщение)")
        return

    command_name = parts[1].lower()
    available_commands = ["занести", "вынести", "ип"]

    if command_name not in available_commands:
        bot.reply_to(msg, f"Доступные команды: {', '.join(available_commands)}")
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
        bot.reply_to(msg, "Пример: -кмд занести (в ответ на сообщение)")
        return

    command_name = parts[1].lower()
    available_commands = ["занести", "вынести", "ип"]

    if command_name not in available_commands:
        bot.reply_to(msg, f"Доступные команды: {', '.join(available_commands)}")
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
    """Функция для запуска бота с автоматическим перезапуском"""
    while True:
        try:
            print("Бот запускается...")
            bot.infinity_polling(timeout=20, long_polling_timeout=10, none_stop=True)
        except Exception as e:
            print(f"❌ Ошибка при работе бота: {e}")
            print("🔄 Перезапуск через 10 секунд...")
            time.sleep(10)
            print("🚀 Попытка перезапуска бота...")

# Запускаем бота с автоматическим перезапуском
run_bot()
