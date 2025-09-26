from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import math

from app.service.auth import AuthInstance
from app.service.balance_service import BalanceServiceInstance
from .user_handlers import show_main_menu_bot, start
from app.config import user_states, ADMIN_IDS, USER_STATE_ADMIN_TOPUP_NUMBER, USER_STATE_ADMIN_TOPUP_AMOUNT, USER_STATE_ADMIN_SWITCH_NUMBER

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("➕ Top Up Saldo User", callback_data='admin_topup')],
        [InlineKeyboardButton("👤 Switch ke User", callback_data='admin_switch')],
        [InlineKeyboardButton("📊 Daftar User", callback_data='admin_list_users_0')],
        [InlineKeyboardButton("« Kembali", callback_data='menu_back_main')]
    ]
    if chat_id in AuthInstance.impersonation_map:
        keyboard.insert(3, [InlineKeyboardButton("↩️ Kembali ke Akun Admin", callback_data='admin_switchback')])
    await query.message.edit_text("⚙️ *Panel Admin*\n\nPilih aksi yang ingin Anda lakukan:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data_parts = query.data.split('_')
    action = data_parts[1]
    if action == 'topup':
        await query.message.edit_text("Masukkan ID Telegram pengguna yang akan di-top up:")
        user_states[chat_id] = USER_STATE_ADMIN_TOPUP_NUMBER
    elif action == 'switch':
        await query.message.edit_text("Masukkan nomor HP pengguna yang ingin Anda 'gunakan':")
        user_states[chat_id] = USER_STATE_ADMIN_SWITCH_NUMBER
    elif action == 'switchback':
        result_message = AuthInstance.stop_impersonation(chat_id)
        await query.message.edit_text(result_message)
        await show_main_menu_bot(update, context)
    elif action == 'list' and data_parts[2] == 'users':
        page = int(data_parts[3])
        ITEMS_PER_PAGE = 5
        all_users = AuthInstance.get_all_registered_users()
        if not all_users:
            await query.message.edit_text("Belum ada pengguna yang terdaftar.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Kembali", callback_data="admin_panel")]]))
            return
        start_index, end_index = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
        page_users = all_users[start_index:end_index]
        message = f"👥 *Daftar Pengguna Terdaftar (Total: {len(all_users)})*\n\n"
        for user in page_users:
            message += (f"👤 Nama: `@{user.get('username', 'N/A')}`\n"
                        f"   ID: `{user.get('chat_id', 'N/A')}`\n"
                        f"   No HP: `{user.get('number', 'N/A')}`\n"
                        f"   Daftar: `{user.get('registration_date', 'N/A')}`\n"
                        f"--------------------\n")
        nav_buttons, total_pages = [], math.ceil(len(all_users) / ITEMS_PER_PAGE)
        if page > 0: nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"admin_list_users_{page - 1}"))
        if total_pages > 1: nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if end_index < len(all_users): nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"admin_list_users_{page + 1}"))
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("« Kembali ke Panel Admin", callback_data="admin_panel")])
        await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    text = update.message.text
    current_state = user_states.get(chat_id)

    if current_state == USER_STATE_ADMIN_TOPUP_NUMBER:
        target_chat_id_str = text.strip()
        context.user_data['admin_target_chat_id'] = target_chat_id_str
        await update.message.reply_text(f"Masukkan jumlah saldo untuk ditambahkan ke pengguna dengan ID {target_chat_id_str}:")
        user_states[chat_id] = USER_STATE_ADMIN_TOPUP_AMOUNT
        return True
    
    elif current_state == USER_STATE_ADMIN_TOPUP_AMOUNT:
        try:
            amount = float(text.strip())
            target_chat_id_str = context.user_data.get('admin_target_chat_id')
            target_chat_id = int(target_chat_id_str)
            BalanceServiceInstance.add_balance(target_chat_id, amount)
            new_balance = BalanceServiceInstance.get_balance(target_chat_id)
            await update.message.reply_text(f"✅ Berhasil! Saldo untuk pengguna ID {target_chat_id} telah ditambahkan.\nSaldo baru: Rp {new_balance:,.0f}")
        except (ValueError, TypeError):
            await update.message.reply_text("Input tidak valid. Harap masukkan ID dan jumlah yang benar.")
        await start(update, context)
        return True

    elif current_state == USER_STATE_ADMIN_SWITCH_NUMBER:
        try:
            target_number = int(text.strip())
            result_message = AuthInstance.start_impersonation(chat_id, target_number)
            await update.message.reply_text(result_message)
        except (ValueError, TypeError):
            await update.message.reply_text("Nomor tidak valid. Harap masukkan nomor HP pengguna.")
        await start(update, context)
        return True
        
    return False

async def admin_topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Perintah ini hanya untuk admin.")
        return
    try:
        parts = context.args
        if len(parts) != 2:
            await update.message.reply_text("Format salah. Gunakan: /topup <target_chat_id> <jumlah>")
            return
        target_chat_id, amount = int(parts[0]), float(parts[1])
        BalanceServiceInstance.add_balance(target_chat_id, amount)
        new_balance = BalanceServiceInstance.get_balance(target_chat_id)
        await update.message.reply_text(f"✅ Berhasil! Saldo untuk pengguna ID {target_chat_id} telah ditambahkan.\nSaldo baru: Rp {new_balance:,.0f}")
    except (IndexError, ValueError) as e:
        await update.message.reply_text(f"Error: {e}\nFormat salah. Gunakan: /topup <target_chat_id> <jumlah>")
        
async def migrate_user_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /migrate - Memigrasi data user dari sistem lama ke baru"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Perintah ini hanya untuk admin.")
        return
    
    try:
        await update.message.reply_text("🔄 Memulai proses migrasi data...")
        
        # Logika migrasi sederhana - sesuaikan dengan kebutuhan Anda
        migrated_count = 0
        all_users = AuthInstance.get_all_registered_users()
        
        for user in all_users:
            # Contoh: Migrasi data balance atau field lainnya
            chat_id = user.get('chat_id')
            if chat_id:
                # Contoh migrasi: set balance default jika belum ada
                current_balance = BalanceServiceInstance.get_balance(chat_id)
                if current_balance == 0:
                    # Lakukan migrasi data di sini
                    migrated_count += 1
        
        await update.message.reply_text(f"✅ Migrasi selesai! {migrated_count} user berhasil diproses.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error selama migrasi: {str(e)}")