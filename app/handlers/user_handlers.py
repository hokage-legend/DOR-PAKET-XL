# app/handlers/user_handlers.py (kode yang sudah diperbaiki final)

import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Impor layanan, data, dan konfigurasi
from app.service.auth import AuthInstance
from app.service.balance_service import BalanceServiceInstance
from app.client.engsel import get_balance, get_otp, submit_otp
from app.config import ADMIN_IDS, user_states, USER_STATE_ENTER_PHONE, USER_STATE_ENTER_OTP

async def show_main_menu_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_user = AuthInstance.get_active_user(chat_id)
    user_info = update.effective_user
    user_id = user_info.id
    username = user_info.username if user_info.username else "Tidak ada"

    if active_user:
        user_number = str(active_user['number'])
        app_balance = BalanceServiceInstance.get_balance(chat_id)

        # --- PERUBAHAN #1: Menambahkan Tombol "Cek Status Deposit" ---
        keyboard = [
            [
                InlineKeyboardButton("🔥 Paket HOT", callback_data='menu_hot1'),
                InlineKeyboardButton("🔥 Paket HOT-2", callback_data='menu_hot2')
            ],
            [
                InlineKeyboardButton("📜 Semua Paket", callback_data='menu_family'),
                InlineKeyboardButton("🏢 Paket Enterprise", callback_data='menu_enterprise')
            ],
            [
                InlineKeyboardButton("⭐ Bookmark Paket", callback_data='menu_bookmark'),
                InlineKeyboardButton("💰 Saldo & Top Up", callback_data='menu_topup')
            ],
            [
                # Tombol baru ditambahkan di baris ini
                InlineKeyboardButton("📊 Cek Status Deposit", callback_data='menu_cek_status')
            ],
            [
                InlineKeyboardButton("🔄 Ganti Akun / Logout", callback_data='menu_logout'),
                InlineKeyboardButton("Tutup", callback_data='menu_close')
            ]
        ]
        
        if chat_id in ADMIN_IDS:
            keyboard.insert(0, [InlineKeyboardButton("⚙️ Panel Admin", callback_data='menu_admin')])
        
        # Sisa dari fungsi ini tidak diubah...
        message_text = (
            f"*Informasi Akun*\n"
            f"Nomor HP: `{user_number}`\n"
            f"ID Telegram: `{user_id}`\n"
            f"Username: `@{username}`\n\n"
        )
        try:
            balance = get_balance(AuthInstance.api_key, active_user["tokens"]["id_token"])
            if balance:
                remaining_balance = balance.get("remaining", "N/A")
                expired_at = balance.get("expired_at", 0)
                expired_at_dt = datetime.datetime.fromtimestamp(expired_at).strftime("%Y-%m-%d %H:%M:%S")
                message_text += f"Pulsa XL: Rp {remaining_balance}\nMasa aktif: {expired_at_dt}\n"
            else:
                message_text += "Pulsa XL: Gagal mengambil data\n"
        except Exception as e:
            print(f"Error fetching balance: {e}")
            message_text += "Pulsa XL: Error fetching data\n"

        message_text += (
            f"Saldo Aplikasi: *Rp {app_balance:,.0f}*\n\n"
            f"⚠️ *Catatan Penting:*\nSaldo pulsa di atas **tidak bisa** digunakan untuk pembelian paket. "
            f"Pembayaran hanya dapat dilakukan melalui **QRIS** atau **E-Wallet**. "
            f"Setiap transaksi akan dikenakan biaya *Rp 5.000* dari Saldo Aplikasi Anda.\n\n"
            f"*Menu:*\nPilih menu di bawah ini."
        )
    else:
        keyboard = [[InlineKeyboardButton("👤 Login", callback_data='menu_login')]]
        message_text = (
            "Selamat datang!\n\n"
            f"ID Telegram Anda adalah: `{user_id}`\n"
            f"Username Anda: `@{username}`\n\n"
            "Anda belum login. Silakan klik 'Login' untuk memulai."
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text=message_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(text=message_text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            print(f"Could not edit message, sending new one: {e}")
            await context.bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states.pop(update.effective_chat.id, None)
    await show_main_menu_bot(update, context)

async def login_flow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Fungsi ini tidak diubah...
    chat_id = update.effective_chat.id
    text = update.message.text
    current_state = user_states.get(chat_id)

    if current_state == USER_STATE_ENTER_PHONE:
        phone_number = text.strip().replace(" ", "").replace("-", "")
        if phone_number.startswith("08"):
            phone_number = "628" + phone_number[2:]
        if phone_number.startswith("628") and phone_number.isdigit() and len(phone_number) >= 11:
            context.user_data["phone_number"] = phone_number
            await update.message.reply_text("⏳ Meminta pengiriman OTP...")
            subscriber_id = get_otp(phone_number)
            if subscriber_id:
                context.user_data["subscriber_id"] = subscriber_id
                await update.message.reply_text(f"✅ OTP telah dikirim ke nomor {phone_number}.\nSilakan masukkan 6 digit kode OTP:")
                user_states[chat_id] = USER_STATE_ENTER_OTP
            else:
                await update.message.reply_text("❌ Gagal mengirim OTP. Nomor mungkin tidak terdaftar atau terjadi masalah server.")
                await start(update, context)
        else:
            await update.message.reply_text("Format nomor tidak valid. Gunakan format `08...` atau `628...`.")
        return True

    elif current_state == USER_STATE_ENTER_OTP:
        otp_code = text.strip()
        phone_number = context.user_data.get("phone_number")
        if otp_code.isdigit() and len(otp_code) == 6:
            await update.message.reply_text("🔐 Memverifikasi OTP...")
            tokens = submit_otp(AuthInstance.api_key, phone_number, otp_code)
            if tokens and "refresh_token" in tokens:
                user_info = update.effective_user
                AuthInstance.add_refresh_token(
                    number=int(phone_number), 
                    refresh_token=tokens["refresh_token"],
                    chat_id=user_info.id,
                    username=user_info.username
                )
                AuthInstance.set_active_user(chat_id, int(phone_number))
                await update.message.reply_text("✅ Login berhasil!")
                await start(update, context)
            else:
                await update.message.reply_text("❌ Kode OTP salah. Silakan coba lagi.")
        else:
            await update.message.reply_text("OTP harus berupa 6 digit angka.")
        return True
    
    return False

async def main_menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Impor handler di dalam fungsi ini
    from .package_handlers import (
        search_and_display_hot_packages, search_and_display_hot2_packages,
        show_predefined_packages_menu, show_bookmark_menu
    )
    # --- PERUBAHAN #2: Impor fungsi yang dibutuhkan ---
    from .topup_handlers import topup_menu_handler, prompt_deposit_id_handler
    from .admin_handlers import admin_panel_handler

    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    command = query.data

    if command == 'menu_back_main':
        await show_main_menu_bot(update, context)
        return

    # Jangan hapus keyboard jika hanya mau cek status
    if command != 'menu_close' and command != 'menu_cek_status':
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            print(f"Could not remove old keyboard: {e}")

    if command == 'menu_login':
        await context.bot.send_message(chat_id=chat_id, text="Masukkan nomor XL Prabayar (contoh: 08123456789):")
        user_states[chat_id] = USER_STATE_ENTER_PHONE
    elif command == 'menu_hot1':
        await search_and_display_hot_packages(update, context)
    elif command == 'menu_hot2':
        await search_and_display_hot2_packages(update, context)
    elif command == 'menu_family':
        context.user_data['package_filter'] = 'all'
        await show_predefined_packages_menu(update, context)
    elif command == 'menu_enterprise':
        context.user_data['package_filter'] = 'enterprise'
        await show_predefined_packages_menu(update, context)
    elif command == 'menu_bookmark':
        await show_bookmark_menu(update, context)
    elif command == 'menu_topup':
        await topup_menu_handler(update, context)
    # --- PERUBAHAN #3: Menambahkan blok logika untuk tombol baru ---
    elif command == 'menu_cek_status':
        # Hapus pesan menu utama agar tidak menumpuk
        await query.message.delete()
        # Panggil fungsi dari topup_handlers untuk meminta ID
        await prompt_deposit_id_handler(update, context)
    elif command == 'menu_admin':
        await admin_panel_handler(update, context)
    elif command == 'menu_logout':
        AuthInstance.logout(chat_id)
        await context.bot.send_message(chat_id=chat_id, text="Anda telah berhasil logout.")
        await show_main_menu_bot(update, context)
    elif command == 'menu_close':
        await query.message.edit_text(text="👋 Terima kasih, sampai jumpa! Ketik /start untuk memulai kembali.")