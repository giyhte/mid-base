import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from asyncio import Lock

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8363145008:AAEM6OSKNRjX3SDU6yINZwbMOEcsaOQVdiI"
OWNER_ID = 7537570296  # твой Telegram ID

db_path = "mid_base.json"
db_lock = Lock()  # блокировка для безопасной записи

# Инициализация базы данных
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
else:
    db = {"users": {}, "banned": [], "reports": {}}

async def save_db():
    async with db_lock:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)

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

@dp.message(F.text.lower() == "старт")
async def start_cmd(msg: Message):
    await msg.answer("Привет! Я активен.")

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
    await save_db()
    await msg.reply(f"{target.first_name} ‼️ ЗАНЕСЕН В БАЗУ КАК {role.upper()}")

@dp.message(F.text.lower() == "команды")
async def commands_list(msg: Message):
    text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "старт — Проверить, что бот активен\n"
        "чек — Просмотреть профиль пользователя (ответом на сообщение или своё)\n"
        "занести <роль> — Добавить пользователя в базу ролей (ответом на сообщение). Роли: скамер, гарант\n"
        "команды — Показать список доступных команд"
    )
    await msg.reply(text, parse_mode=ParseMode.HTML)

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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
