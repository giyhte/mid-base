import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8434117020:AAETWdA3rkW_0M2IDtqvVWbFCTcIdTr0eiY"
OWNER_ID = 7537570296  # твой Telegram ID

db_path = "mid_base.json"
if os.path.exists(db_path):
    with open(db_path, "r") as f:
        db = json.load(f)
else:
    db = {"users": {}, "banned": [], "reports": {}}


def save_db():
    with open(db_path, "w") as f:
        json.dump(db, f, indent=4)


def get_role(user_id: int) -> str:
    if str(user_id) == str(OWNER_ID):
        return "владелец"
    return db["users"].get(str(user_id), "игрок")


def get_risk(role: str) -> str:
    return {
        "владелец": "0%",
        "гарант": "0%",
        "скамер": "100%",
        "игрок": "50% (лучше ходить гарантом)"
    }.get(role, "50%")


bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Приветствие
@dp.message(F.text.lower() == "старт")
async def start_cmd(msg: Message):
    await msg.answer("Привет! Я активен.")

# Чек профиля
@dp.message(F.text.lower().startswith("чек"))
async def check_profile(msg: Message):
    user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    role = get_role(user.id)
    risk = get_risk(role)
    text = (
        f"👤 Профиль: <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"🔹 Роль: <code>{role}</code>\n"
        f"📊 Вероятность скама: <code>{risk}</code>"
    )
    await msg.reply(text)

# Установка роли
@dp.message(F.text.lower().startswith("занести"))
async def set_role(msg: Message):
    if msg.chat.type != ChatType.PRIVATE and msg.from_user.id != OWNER_ID:
        return

    if not msg.reply_to_message:
        return await msg.reply("Ответьте на сообщение пользователя.")

    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Пример: занести скамер")

    role = parts[1].lower()
    if role not in ["скамер", "гарант"]:
        return await msg.reply("Допустимые роли: скамер, гарант")

    target = msg.reply_to_message.from_user
    if target.id == OWNER_ID:
        return await msg.reply("Нельзя менять роль владельцу.")

    db["users"][str(target.id)] = role
    save_db()
    await msg.reply(f"{target.first_name} ‼️ ЗАНЕСЕН В БАЗУ КАК {role.upper()}")

# Жалоба — отправка ЛС гарантам и владельцу
@dp.message(F.text.lower().startswith("жалоба"))
async def report_user(msg: Message):
    if not msg.reply_to_message:
        return await msg.reply("Жалоба отправляется в ответ на сообщение.")

    sender = msg.from_user
    reported = msg.reply_to_message.from_user

    now = asyncio.get_event_loop().time()
    key = str(sender.id)
    reports = db["reports"].get(key, {"count": 0, "time": now})

    if now - float(reports["time"]) > 86400:
        reports = {"count": 0, "time": now}

    if reports["count"] >= 5:
        return await msg.reply("Вы исчерпали лимит жалоб на сегодня.")

    reports["count"] += 1
    reports["time"] = now
    db["reports"][key] = reports
    save_db()

    text = (
        f"🚨 <b>Жалоба</b>\n"
        f"👤 От: <a href='tg://user?id={sender.id}'>{sender.first_name}</a>\n"
        f"📌 На: <a href='tg://user?id={reported.id}'>{reported.first_name}</a>\n"
        f"💬 Сообщение: {msg.reply_to_message.text}"
    )

    # Отправляем жалобу в ЛС всем гарантам и владельцу
    recipients = set()
    for uid, role in db["users"].items():
        if role == "гарант":
            recipients.add(int(uid))
    recipients.add(OWNER_ID)  # владелец тоже получает

    for user_id in recipients:
        # не отправляем жалобу отправителю и объекту жалобы (можно убрать, если надо)
        if user_id in [sender.id, reported.id]:
            continue
        try:
            await bot.send_message(user_id, text)
        except Exception as e:
            # Можно логировать ошибку, если нужно
            pass

    await msg.reply("Жалоба отправлена!")

# Сетка бан
@dp.message(F.text.lower() == "сетка бан")
async def net_ban(msg: Message):
    if msg.from_user.id != OWNER_ID:
        return

    if not msg.reply_to_message:
        return await msg.reply("Ответьте на сообщение пользователя.")

    user = msg.reply_to_message.from_user
    if user.id not in db["banned"]:
        db["banned"].append(user.id)
        save_db()
        await msg.reply(f"{user.first_name} теперь в глобальном бане (скамер)")
    else:
        await msg.reply(f"{user.first_name} уже в бане.")

# Автобан при входе
@dp.message(F.new_chat_members)
async def check_ban_on_join(msg: Message):
    for user in msg.new_chat_members:
        if user.id in db["banned"]:
            try:
                await bot.ban_chat_member(msg.chat.id, user.id)
                await msg.reply(f"🚫 {user.first_name} забанен глобально как СКАМЕР.")
            except Exception as e:
                await msg.reply(f"❗ Не удалось забанить {user.first_name}: {e}")

# Предупреждение при сообщении от скамера
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def warn_scammer(msg: Message):
    if not msg.from_user:
        return
    role = get_role(msg.from_user.id)
    if role == "скамер":
        await msg.reply(
            f"⚠️ Осторожно! Игрок <a href='tg://user?id={msg.from_user.id}'>{msg.from_user.first_name}</a> занесён в базу как <b>СКАМЕР</b>.",
            parse_mode=ParseMode.HTML
        )

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
