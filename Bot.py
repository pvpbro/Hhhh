import logging
import json
import os
import secrets
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище заявок
sell_requests = {}
ADMIN_ID = 7990799592

# Главное меню продажи
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💥 ПРОДАТЬ BRAWL STARS", callback_data="sell_bs")],
        [InlineKeyboardButton("⚔️ ПРОДАТЬ CLASH ROYALE", callback_data="sell_cr")],
    ]
    await update.message.reply_text(
        "💎 <b>ПРОДАЖА АККАУНТОВ</b>\n\nВыберите игру:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# Начало процесса продажи
async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.replace("sell_", "")
    game_names = {"bs": "BRAWL STARS", "cr": "CLASH ROYALE"}
    context.user_data['sell_game'] = game
    context.user_data['sell_step'] = 'awaiting_data'
    context.user_data['sell_data'] = {}
    context.user_data['sell_photo'] = None
    await query.edit_message_text(
        f"💎 <b>ПРОДАЖА {game_names.get(game, '')}</b>\n\n"
        f"📝 Отправьте данные аккаунта:\n\n"
        f"📌 <b>Brawl Stars:</b>\n"
        f"├ Тэг: #...\n├ Кубков: ...\n├ Персонажей: ...\n└ Праймов: ...\n\n"
        f"📌 <b>Clash Royale:</b>\n"
        f"├ Тэг: #...\n├ Трофеев: ...\n├ Карт: ...\n└ Уровень башни: ...\n\n"
        f"📸 Отправьте <b>ОДНО фото</b> аккаунта\n\n"
        f"После отправки нажмите <b>ГОТОВО</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ГОТОВО", callback_data="sell_ready")]]),
        parse_mode='HTML'
    )

# Сбор данных и фото
async def sell_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('sell_step') != 'awaiting_data':
        return
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        context.user_data['sell_photo'] = photo_file.file_id
        await update.message.reply_text("📸 Фото получено! Отправьте данные аккаунта")
        return
    if update.message.text:
        context.user_data['sell_data']['text'] = update.message.text
        await update.message.reply_text("✅ Данные сохранены! Нажмите ГОТОВО")

# Отправка заявки админу
async def sell_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    game = context.user_data.get('sell_game')
    game_names = {"bs": "BRAWL STARS", "cr": "CLASH ROYALE"}
    sell_data = context.user_data.get('sell_data', {})
    photo_id = context.user_data.get('sell_photo')
    if not sell_data.get('text'):
        await query.edit_message_text("❌ Сначала отправьте данные аккаунта!")
        return
    request_id = secrets.token_hex(8)
    sell_requests[request_id] = {
        'id': request_id, 'user_id': user.id, 'user_name': user.username or str(user.id),
        'game': game, 'data': sell_data['text'], 'photo_id': photo_id,
        'status': 'pending', 'price': None, 'created_at': time.time()
    }
    admin_text = f"🆕 <b>НОВАЯ ЗАЯВКА!</b>\n\n🆔 ID: {request_id}\n🎮 {game_names.get(game, '')}\n👤 @{user.username or user.id}\n📝 {sell_data['text']}"
    keyboard = [[InlineKeyboardButton("💰 НАЗНАЧИТЬ ЦЕНУ", callback_data=f"setprice_{request_id}")], [InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{request_id}")]]
    try:
        if photo_id:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        await query.edit_message_text(f"✅ ЗАЯВКА ОТПРАВЛЕНА!\n\n🆔 ID: {request_id}\nОжидайте ответа!")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")
    context.user_data.clear()

# Админ назначает цену
async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Не для тебя!", show_alert=True)
        return
    request_id = query.data.replace("setprice_", "")
    context.user_data['price_request_id'] = request_id
    await query.edit_message_text(f"💰 Введите цену для заявки {request_id}:")

# Обработка цены от админа
async def process_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    request_id = context.user_data.get('price_request_id')
    if not request_id or request_id not in sell_requests:
        await update.message.reply_text("❌ Заявка не найдена!")
        return
    try:
        price = int(update.message.text)
        if price <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Введите число больше 0!")
        return
    req = sell_requests[request_id]
    req['price'] = price
    req['status'] = 'price_set'
    keyboard = [[InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"accept_{request_id}")], [InlineKeyboardButton("❌ ОТКАЗАТЬСЯ", callback_data=f"reject_{request_id}")]]
    await context.bot.send_message(chat_id=req['user_id'], text=f"💰 Вам предложили {price:,} ₽ за аккаунт!", reply_markup=InlineKeyboardMarkup(keyboard))
    await update.message.reply_text(f"✅ Цена {price:,} ₽ отправлена!")

# Покупатель принимает цену
async def accept_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.replace("accept_", "")
    if request_id not in sell_requests:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    req = sell_requests[request_id]
    req['status'] = 'accepted'
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Пользователь @{req['user_name']} ПРИНЯЛ цену {req['price']:,} ₽!")
    await query.edit_message_text(f"✅ Вы приняли цену {req['price']:,} ₽!\nОжидайте реквизиты от администратора.")

# Покупатель отклоняет цену
async def reject_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.replace("reject_", "")
    if request_id not in sell_requests:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    req = sell_requests[request_id]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Пользователь @{req['user_name']} ОТКАЗАЛСЯ от цены {req['price']:,} ₽")
    await query.edit_message_text("❌ Вы отказались от предложения.")
    del sell_requests[request_id]

# Админ отправляет реквизиты
async def send_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ Использование: /pay [ID заявки] [реквизиты]")
        return
    request_id = context.args[0]
    payment_text = ' '.join(context.args[1:])
    if request_id not in sell_requests:
        await update.message.reply_text("❌ Заявка не найдена!")
        return
    req = sell_requests[request_id]
    await context.bot.send_message(chat_id=req['user_id'], text=f"💳 <b>РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ</b>\n\n{payment_text}\n\nПосле оплаты нажмите <b>ОПЛАЧЕНО</b>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ОПЛАЧЕНО", callback_data=f"paid_{request_id}")]]))
    await update.message.reply_text(f"✅ Реквизиты отправлены @{req['user_name']}!")

# Покупатель подтверждает оплату
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.replace("paid_", "")
    if request_id not in sell_requests:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    req = sell_requests[request_id]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💰 @{req['user_name']} ПОДТВЕРДИЛ ОПЛАТУ {req['price']:,} ₽!\n\nПередайте данные аккаунта покупателю!")
    await query.edit_message_text("✅ Спасибо! Администратор скоро свяжется с вами.")

# Админ отправляет данные аккаунта
async def send_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ Использование: /give [ID заявки] [данные аккаунта]")
        return
    request_id = context.args[0]
    account_data = ' '.join(context.args[1:])
    if request_id not in sell_requests:
        await update.message.reply_text("❌ Заявка не найдена!")
        return
    req = sell_requests[request_id]
    await context.bot.send_message(chat_id=req['user_id'], text=f"🎮 <b>ДАННЫЕ АККАУНТА</b>\n\n{account_data}\n\nСделка завершена!", parse_mode='HTML')
    await update.message.reply_text(f"✅ Данные аккаунта отправлены @{req['user_name']}!")

# Админ отклоняет заявку
async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Не для тебя!", show_alert=True)
        return
    request_id = query.data.replace("reject_", "")
    if request_id in sell_requests:
        del sell_requests[request_id]
    await query.edit_message_text("✅ Заявка отклонена!")

# Команда для админа - список заявок
async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Не для тебя!")
        return
    if not sell_requests:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    text = "📋 ЗАЯВКИ:\n\n"
    for rid, req in list(sell_requests.items())[:20]:
        text += f"🆔 {rid[:8]}... | @{req['user_name']} | {req['status']}\n"
    await update.message.reply_text(text)

def main():
    app = Application.builder().token("8941994828:AAEvdg97xKy6C-sUd_itWglfW2JXQdWJjx8").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("requests", my_requests))
    app.add_handler(CommandHandler("pay", send_payment))
    app.add_handler(CommandHandler("give", send_account))
    app.add_handler(CallbackQueryHandler(sell_start, pattern=r"^sell_"))
    app.add_handler(CallbackQueryHandler(sell_ready, pattern=r"^sell_ready$"))
    app.add_handler(CallbackQueryHandler(set_price, pattern=r"^setprice_"))
    app.add_handler(CallbackQueryHandler(accept_price, pattern=r"^accept_"))
    app.add_handler(CallbackQueryHandler(reject_price, pattern=r"^reject_"))
    app.add_handler(CallbackQueryHandler(paid, pattern=r"^paid_"))
    app.add_handler(CallbackQueryHandler(reject, pattern=r"^reject_"))
    app.add_handler(MessageHandler(filters.PHOTO, sell_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sell_data))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), process_price))
    app.run_polling()

if __name__ == "__main__":
    main()
