from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
# threading dan webhook_server sudah tidak diperlukan di sini
# import threading
# from webhook_server import run_webhook_server

from app.config import BOT_TOKEN
from app.handlers.user_handlers import *
from app.handlers.package_handlers import *
from app.handlers.payment_handlers import *
from app.handlers.topup_handlers import *
from app.handlers.admin_handlers import *

async def master_message_handler(update, context):
    if await login_flow_handler(update, context): return
    if await topup_amount_handler(update, context): return
    if await handle_deposit_id_input(update, context): return
    if await admin_input_handler(update, context): return
    await show_main_menu_bot(update, context)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Perintah
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("topup", admin_topup_command))
    application.add_handler(CommandHandler("migrate", migrate_user_data_command))

    # Callbacks
    application.add_handler(CallbackQueryHandler(main_menu_callback_handler, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(topup_menu_handler, pattern='^menu_topup$'))
    application.add_handler(CallbackQueryHandler(topup_action_handler, pattern='^topup_'))
    application.add_handler(CallbackQueryHandler(check_deposit_status_handler, pattern='^check_deposit_'))
    # ... (handler lain tidak diubah)

    # Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, master_message_handler))
    
    # --- KODE UNTUK MENJALANKAN WEBHOOK DIHAPUS DARI SINI ---
    
    print("BOT Token ditemukan, bot utama dijalankan...")
    application.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN tidak ditemukan.")
    else:
        main()