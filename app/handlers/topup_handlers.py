from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import urllib.parse
import qrcode
import io
import time
import traceback

from app.service.auth import AuthInstance
from app.service.balance_service import BalanceServiceInstance
from app.client.atlantic import get_deposit_methods, create_deposit_request, request_instant_deposit, check_deposit_status

from .user_handlers import show_main_menu_bot
from app.config import user_states, USER_STATE_ENTER_TOPUP_AMOUNT, reff_id_to_chat_id_map, USER_STATE_ENTER_DEPOSIT_ID


async def topup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user:
        await context.bot.send_message(chat_id=chat_id, text="Silakan login terlebih dahulu.")
        return
        
    balance = BalanceServiceInstance.get_balance(chat_id)
    message = (f"Saldo Aplikasi Anda saat ini: *Rp {balance:,.0f}*\n\n"
               "Silakan pilih metode Top Up di bawah ini:")
    keyboard = [[InlineKeyboardButton("💳 Top Up Manual (Admin)", callback_data='topup_manual')],
                [InlineKeyboardButton("🤖 Top Up Otomatis (QRIS INSTANT)", callback_data='topup_auto')],
                [InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')]]
    await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def topup_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    action = query.data

    if action == 'topup_auto':
        await query.message.edit_text("Silakan masukkan jumlah saldo yang ingin Anda top up via QRIS INSTANT (contoh: 50000).")
        user_states[chat_id] = USER_STATE_ENTER_TOPUP_AMOUNT
    
    elif action == 'topup_manual':
        # Logika topup manual
        pass

async def topup_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    text = update.message.text
    if user_states.get(chat_id) != USER_STATE_ENTER_TOPUP_AMOUNT:
        return False

    try:
        amount = int(text.strip())
        if amount < 1000:
            await update.message.reply_text("Jumlah top up minimal adalah Rp 1,000.")
            return True

        user_states.pop(chat_id, None)
        msg = await update.message.reply_text("⏳ Mencari metode QRIS INSTANT dan membuat invoice...")
        
        all_methods = get_deposit_methods()
        qris_instant_method = None
        
        if all_methods is None:
             await msg.edit_text("❌ Gagal mengambil daftar metode pembayaran dari server.")
             return True

        for method in all_methods:
            if method.get('name', '').upper() == 'QRIS INSTANT':
                qris_instant_method = method
                break
        
        if not qris_instant_method:
            await msg.edit_text("❌ Gagal menemukan metode 'QRIS INSTANT' di akun Anda.")
            return True

        method_code = qris_instant_method.get('metode')
        method_type = qris_instant_method.get('type')
        reff_id = f"TOPUP-{chat_id}-{int(time.time())}"
        
        deposit_data = create_deposit_request(amount, method_code, method_type, reff_id)

        if deposit_data and 'qr_string' in deposit_data:
            reff_id_to_chat_id_map[reff_id] = chat_id
            deposit_id = deposit_data.get('id')
            final_amount = deposit_data.get('nominal', amount)
            keyboard = [[InlineKeyboardButton("✅ Cek Status Pembayaran", callback_data=f"check_deposit_{deposit_id}")]]
            
            qr_image = qrcode.make(deposit_data['qr_string'])
            buffer = io.BytesIO()
            qr_image.save(buffer, 'PNG')
            buffer.seek(0)
            
            caption = (f"✅ Invoice Top Up berhasil dibuat.\n\n"
                       f"Silakan scan QRIS di atas untuk membayar *Rp {final_amount:,}*.\n\n"
                       f"ID Deposit Anda: `{deposit_id}`\n"
                       f"Gunakan ID ini untuk /cekstatus jika diperlukan.\n\n"
                       f"Setelah pembayaran berhasil, saldo akan masuk secara otomatis.")
            
            await msg.delete()
            await context.bot.send_photo(chat_id=chat_id, photo=buffer, caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        else:
            await msg.edit_text("❌ Gagal membuat invoice QRIS INSTANT.")

    except (ValueError, TypeError):
        await update.message.reply_text("Input tidak valid. Harap masukkan angka saja.")
    
    except Exception as e:
        print(f"Error di topup_amount_handler: {traceback.format_exc()}")
        await update.message.reply_text(f"Terjadi error teknis: `{str(e)}`", parse_mode="Markdown")

    return True


async def check_deposit_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fungsi ini tidak diubah
    pass

# --- FUNGSI BARU UNTUK CEK STATUS ---

async def prompt_deposit_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Meminta pengguna memasukkan ID Deposit setelah menekan tombol."""
    chat_id = update.effective_chat.id
    
    # --- PERBAIKAN DI SINI ---
    # Menggunakan context.bot.send_message karena ini adalah respons dari tombol (CallbackQuery)
    # bukan balasan dari pesan teks (Message)
    await context.bot.send_message(chat_id=chat_id, text="Silakan masukkan ID Deposit (Transaction ID) yang ingin Anda cek:")
    user_states[chat_id] = USER_STATE_ENTER_DEPOSIT_ID

async def handle_deposit_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Menangani input ID Deposit dari pengguna dan menampilkan statusnya."""
    chat_id = update.effective_chat.id
    if user_states.get(chat_id) != USER_STATE_ENTER_DEPOSIT_ID:
        return False

    deposit_id = update.message.text.strip()
    msg = await update.message.reply_text(f"🔎 Mengecek status untuk ID: `{deposit_id}`...", parse_mode="Markdown")
    user_states.pop(chat_id, None)

    status_data = check_deposit_status(deposit_id)

    if status_data:
        status_emoji = {
            "success": "✅ Berhasil", "pending": "⏳ Pending", "expired": "❌ Kedaluwarsa",
            "failed": "❗️ Gagal", "processing": "⚙️ Diproses"
        }
        status_text = status_data.get('status', 'N/A')
        emoji = status_emoji.get(status_text.lower(), "❓")

        pesan = (
            f"Berikut adalah status transaksi Anda:\n\n"
            f"<b>ID Deposit:</b> {status_data.get('id', 'N/A')}\n"
            f"<b>Reff ID Anda:</b> {status_data.get('reff_id', 'N/A')}\n"
            f"<b>Metode:</b> {status_data.get('metode', 'N/A')}\n"
            f"<b>Nominal:</b> Rp {int(status_data.get('nominal', 0)):,}\n"
            f"<b>Dibuat Pada:</b> {status_data.get('created_at', 'N/A')}\n"
            f"<b>Status:</b> {emoji}\n"
        )
        await msg.edit_text(pesan, parse_mode="HTML")
    else:
        await msg.edit_text("❌ ID Deposit tidak ditemukan atau terjadi kesalahan saat pengecekan.")
    
    return True