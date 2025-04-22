import json
import os
import requests
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Константы
RELEASES_FILE = 'releases.json'
ROLES_FILE = 'roles.json'
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbze_m_fmwBClM9C276BwshOjS_SXWz6HiKq-C0Z5JXcauOU4trUGpVcKbsCEuqVm5zq/exec"

# Функции работы с файлами
def load_releases():
    if not os.path.exists(RELEASES_FILE):
        return {}
    with open(RELEASES_FILE, 'r') as f:
        return json.load(f)

def save_releases(data):
    with open(RELEASES_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_roles():
    if not os.path.exists(ROLES_FILE):
        return {}
    with open(ROLES_FILE, 'r') as f:
        return json.load(f)

def save_roles(roles):
    with open(ROLES_FILE, 'w') as f:
        json.dump(roles, f, indent=2)

# Отправка релиза в Google Таблицу
def add_release_to_gsheet(title, artist, status="В обработке"):
    data = {
        "title": title,
        "artist": artist,
        "status": status
    }
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, data=data)
        print("Релиз в таблицу:", response.text)
    except Exception as e:
        print("Ошибка:", str(e))

# Отправка жалобы в Google Таблицу
def report_issue_to_gsheet(title, username, issue):
    data = {
        "title": title,
        "username": username,
        "issue": issue
    }
    print(f"Отправляем данные: {data}")  # Печатаем данные перед отправкой
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, data=data)
        if response.status_code == 200:
            print("Жалоба в таблицу:", response.text)
        else:
            print("Ошибка при отправке жалобы:", response.text)
    except Exception as e:
        print("Ошибка при отправке жалобы:", str(e))

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Я менеджер", callback_data="set_role_manager")],
        [InlineKeyboardButton("Я артист", callback_data="set_role_artist")]
    ]
    await update.message.reply_text("Кто вы?", reply_markup=InlineKeyboardMarkup(keyboard))

# Меню менеджера
async def send_manager_menu(query):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить релиз", callback_data="manager_add_release")],
        [InlineKeyboardButton("🔍 Проверить статус", callback_data="manager_check_status")],
        [InlineKeyboardButton("Обновить статус: Одобрен и доставлен", callback_data="step_approved")]
    ]
    await query.edit_message_text("Меню менеджера:", reply_markup=InlineKeyboardMarkup(keyboard))

# Меню артиста
async def send_artist_menu(query):
    keyboard = [
        [InlineKeyboardButton("🔍 Проверить статус релиза", callback_data="artist_check_status")],
        [InlineKeyboardButton("Сообщить о проблеме", callback_data="artist_report_issue")]
    ]
    await query.edit_message_text("Меню артиста:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    roles = load_roles()

    await query.answer()

    if query.data == "set_role_manager":
        roles[user_id] = "manager"
        save_roles(roles)
        await send_manager_menu(query)

    elif query.data == "set_role_artist":
        roles[user_id] = "artist"
        save_roles(roles)
        await send_artist_menu(query)

    elif query.data == "manager_add_release":
        await query.edit_message_text("Введите название релиза и @артиста через пробел:")
        context.user_data['next_action'] = 'add_release'

    elif query.data == "manager_check_status":
        await query.edit_message_text("Введите название релиза для проверки:")
        context.user_data['next_action'] = 'check_status'

    elif query.data == "step_approved":
        context.user_data["next_action"] = "update_step"
        await query.edit_message_text("Введите название релиза, чтобы установить статус 'Одобрен и доставлен':")

    elif query.data == "artist_check_status":
        await query.edit_message_text("Введите название своего релиза:")
        context.user_data["next_action"] = "artist_check_status"

    elif query.data == "artist_report_issue":
        await query.edit_message_text("Опишите проблему и укажите название релиза:")
        context.user_data["next_action"] = "report_issue"

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    roles = load_roles()
    role = roles.get(user_id)
    action = context.user_data.get("next_action")

    if role == "manager":
        if action == "add_release":
            parts = update.message.text.strip().split()
            if len(parts) != 2:
                await update.message.reply_text("Введите в формате: Название @артист")
                return
            title, artist = parts
            releases = load_releases()
            releases[title] = {
                "artist": artist,
                "status": "В обработке"
            }
            save_releases(releases)
            add_release_to_gsheet(title, artist)
            await update.message.reply_text(f"Релиз '{title}' добавлен.")
            context.user_data.clear()

        elif action == "check_status":
            await show_status(update, update.message.text.strip())
            context.user_data.clear()

        elif action == "update_step":
            title = update.message.text.strip()
            releases = load_releases()
            if title in releases:
                releases[title]["status"] = "Одобрен и доставлен"
                save_releases(releases)
                await update.message.reply_text(f"Статус обновлён для '{title}': Одобрен и доставлен")
                await context.bot.send_message(
                    chat_id=releases[title]["artist"],
                    text=f"✅ Ваш релиз '{title}' получил статус: Одобрен и доставлен"
                )
            else:
                await update.message.reply_text("Релиз не найден.")
            context.user_data.clear()

    elif role == "artist":
        if action == "artist_check_status":
            title = update.message.text.strip()
            releases = load_releases()
            release = releases.get(title)
            if release and release["artist"] == f"@{update.message.from_user.username}":
                await show_status(update, title)
            else:
                await update.message.reply_text("Вы не являетесь владельцем этого релиза.")
            context.user_data.clear()

        elif action == "report_issue":
            issue_text = update.message.text.strip()
            username = update.message.from_user.username or "Неизвестный пользователь"
            title = issue_text.split()[0] if issue_text else "Не указано"
            report_issue_to_gsheet(title, username, issue_text)
            await update.message.reply_text("Спасибо, проблема отправлена менеджеру!")
            context.user_data.clear()

# Отображение статуса релиза
async def show_status(update, title):
    releases = load_releases()
    if title in releases:
        status = releases[title]["status"]
        await update.message.reply_text(f"Статус релиза '{title}': {status}")
    else:
        await update.message.reply_text("Релиз не найден.")

# Запуск бота
def main():
    app = ApplicationBuilder().token("7989351182:AAHZrsNWZEQR-Fsd2PzaK2-SJyyIvIEHJXU").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()