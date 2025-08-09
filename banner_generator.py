import os

def get_role_banner_url(role):
    """Возвращает URL ссылку на баннер для каждой роли"""
    banners = {
        "владелец": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",
        "гарант": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",
        "владелец чата": "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg",
        "проверенный": "https://i.ibb.co/0jqRrPrm/IMG-20250809-120309-325.jpg",
        "отказ от гаранта": "https://i.ibb.co/jPpYnM7H/IMG-20250809-120309-094.jpg",
        "скамер": "https://i.ibb.co/MxkQdSZp/IMG-20250809-120308-534.jpg",
        "непроверенный": "https://i.ibb.co/DD4n7HmF/IMG-20250809-120308-732.jpg"
    }
    return banners.get(role, banners["непроверенный"])

def get_global_message_banner_url():
    """Возвращает URL ссылку на баннер для глобального сообщения"""
    return "https://i.ibb.co/5gQMW4gK/IMG-20250809-120308-934.jpg"

def get_role_banner_file(role, user_name="ПРОФИЛЬ"):
    """Возвращает путь к готовому баннеру для роли"""

    # Создаем папку для баннеров если её нет
    banners_dir = "banners"
    if not os.path.exists(banners_dir):
        os.makedirs(banners_dir)

    # Соответствие ролей файлам баннеров
    role_files = {
        "владелец": "owner.png",
        "гарант": "guarantor.png",
        "владелец чата": "chat_owner.png",
        "проверенный": "verified.png",
        "отказ от гаранта": "refusal.png",
        "скамер": "scammer.png",
        "непроверенный": "unverified.png"
    }

    # Получаем имя файла для роли
    filename = role_files.get(role, "unverified.png")
    filepath = os.path.join(banners_dir, filename)

    # Проверяем существует ли файл
    if os.path.exists(filepath):
        return filepath
    else:
        print(f"Баннер для роли '{role}' не найден: {filepath}")
        return None

# Тестовая функция
if __name__ == "__main__":
    # Создаем тестовые баннеры для всех ролей
    roles = ["владелец", "гарант", "владелец чата", "проверенный", "отказ от гаранта", "скамер", "непроверенный"]

    # Для тестирования, убедитесь, что в папке "banners" есть соответствующие файлы изображений
    # Например: owner.png, guarantor.png, chat_owner.png, verified.png, refusal.png, scammer.png, unverified.png

    for role in roles:
        try:
            filepath = get_role_banner_file(role, "ТЕСТОВЫЙ_ПРОФИЛЬ")
            if filepath:
                print(f"✅ Баннер для роли '{role}' найден: {filepath}")
            else:
                print(f"❌ Баннер для роли '{role}' не найден.")
        except Exception as e:
            print(f"❌ Ошибка получения баннера для роли '{role}': {e}")