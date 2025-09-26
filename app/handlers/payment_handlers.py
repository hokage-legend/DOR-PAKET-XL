# app/handlers/payment_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import qrcode
import io

# Impor layanan dan data
from app.service.auth import AuthInstance
from app.service.balance_service import BalanceServiceInstance
from app.client.qris import get_qris_payment_data
from app.client.ewallet import settlement_multipayment_v2

# Impor dari handler lain
from .user_handlers import show_main_menu_bot, start

# Impor state dari main.py
from app.config import ADMIN_IDS, user_states, USER_STATE_ENTER_PHONE, USER_STATE_ENTER_OTP

async def purchase_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    if query.data == 'confirm_purchase':
        active_user = AuthInstance.get_active_user(chat_id)
        if not active_user:
            await context.bot.send_message(chat_id=chat_id, text="Sesi Anda berakhir, silakan /start lagi.")
            return
        user_number = str(active_user['number'])
        TRANSACTION_FEE = 5000
        if BalanceServiceInstance.get_balance(chat_id) < TRANSACTION_FEE:
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Transaksi Gagal: Saldo aplikasi Anda tidak cukup untuk membayar biaya transaksi (Rp {TRANSACTION_FEE:,.0f}). Silakan top up terlebih dahulu.")
            await show_main_menu_bot(update, context)
            return
        await query.edit_message_reply_markup(reply_markup=None)
        selected_package_shortcut = context.user_data.get('selected_package_to_buy')
        if not selected_package_shortcut:
            await context.bot.send_message(chat_id=chat_id, text="Terjadi kesalahan, data paket tidak ditemukan.")
            return
        await context.bot.send_message(chat_id=chat_id, text="✅ Memproses detail paket...")
        full_package_details_list = []
        is_bundle = 'packages' in selected_package_shortcut and isinstance(selected_package_shortcut['packages'], list)
        if is_bundle:
            for sub_package in selected_package_shortcut['packages']:
                details = await get_full_package_details_from_hot_data(context, sub_package)
                if details:
                    full_package_details_list.append(details)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Gagal mengambil detail untuk sub-paket: {sub_package.get('option_name')}.")
                    return
        else:
            if 'family_code' in selected_package_shortcut:
                details = await get_full_package_details_from_hot_data(context, selected_package_shortcut)
                if details:
                    full_package_details_list.append(details)
            else:
                if 'code' in selected_package_shortcut and 'item_code' not in selected_package_shortcut:
                    selected_package_shortcut['item_code'] = selected_package_shortcut['code']
                selected_package_shortcut.setdefault('token_confirmation', '')
                full_package_details_list.append(selected_package_shortcut)
        if not full_package_details_list:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gagal mengambil detail lengkap paket dari server.")
            return
        context.user_data['full_package_details_list'] = full_package_details_list
        context.user_data['bundle_info'] = selected_package_shortcut if is_bundle else None
        keyboard = [
            [InlineKeyboardButton("💳 QRIS", callback_data='pay_qris')],
            [InlineKeyboardButton("📱 E-Wallet", callback_data='pay_ewallet')]
        ]
        await context.bot.send_message(chat_id=chat_id, text="Silakan pilih metode pembayaran:", reply_markup=InlineKeyboardMarkup(keyboard))
        user_states[chat_id] = USER_STATE_SELECTING_PAYMENT_METHOD
    elif query.data == 'cancel_purchase':
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat_id, text="Pembelian dibatalkan.")
        await show_main_menu_bot(update, context)

async def payment_method_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_reply_markup(reply_markup=None)
    
    package_list = context.user_data.get('full_package_details_list')

    if query.data == 'pay_qris':
        await show_qris_payment_bot(update, context, package_list)
    elif query.data == 'pay_ewallet':
        keyboard = [
            [InlineKeyboardButton("DANA", callback_data='ewallet_DANA'), InlineKeyboardButton("OVO", callback_data='ewallet_OVO')],
            [InlineKeyboardButton("GoPay", callback_data='ewallet_GOPAY'), InlineKeyboardButton("ShopeePay", callback_data='ewallet_SHOPEEPAY')]
        ]
        await context.bot.send_message(chat_id=chat_id, text="Pilih E-Wallet:", reply_markup=InlineKeyboardMarkup(keyboard))
        user_states[chat_id] = USER_STATE_SELECTING_EWALLET

async def ewallet_choice_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_reply_markup(reply_markup=None)
    payment_method = query.data.split('_')[1]
    
    if payment_method in ["DANA", "OVO"]:
        context.user_data['selected_ewallet'] = payment_method
        await context.bot.send_message(chat_id=chat_id, text=f"Masukkan nomor {payment_method} Anda (Contoh: 081234567890):")
        user_states[chat_id] = USER_STATE_ENTER_EWALLET_NUMBER
    else:
        await process_ewallet_payment(update, context, payment_method)

async def show_qris_payment_bot(update: Update, context: ContextTypes.DEFAULT_TYPE, package_list: list):
    chat_id = update.effective_chat.id
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user:
        await context.bot.send_message(chat_id=chat_id, text="Sesi login habis.")
        return
    api_key, tokens = AuthInstance.api_key, active_user["tokens"]
    if not package_list:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Tidak ada paket untuk diproses.")
        return
    payment_items, total_price = [], 0
    for package in package_list:
        item_code, item_price, item_name = package.get("item_code") or package.get("code"), package.get("price", 0), package.get("name") or package.get("option_name")
        if not item_code:
            error_name = item_name or 'Tidak Dikenal'
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Gagal: Paket '{error_name}' tidak memiliki kode item valid.")
            await show_main_menu_bot(update, context)
            return
        payment_items.append({"item_code": item_code, "item_price": item_price, "item_name": item_name, "token_confirmation": package.get("token_confirmation", "")})
        total_price += int(item_price)
    bundle_info = context.user_data.get('bundle_info')
    display_name = bundle_info['name'] if bundle_info else payment_items[0]['item_name']
    await context.bot.send_message(chat_id=chat_id, text="Membuat transaksi QRIS...")
    try:
        qris_url = get_qris_payment_data(api_key, tokens, payment_items)
        if qris_url:
            BalanceServiceInstance.deduct_balance(chat_id, 5000)
            qr_image = qrcode.make(qris_url)
            buffer = io.BytesIO()
            qr_image.save(buffer, 'PNG')
            buffer.seek(0)
            await context.bot.send_photo(chat_id=chat_id, photo=buffer, caption=f"✅ Silakan scan QRIS untuk pembayaran *{display_name}* seharga *Rp {total_price}*.", parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gagal membuat QRIS.")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Terjadi error: {e}")
    await show_main_menu_bot(update, context)

async def process_ewallet_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_method: str, wallet_number: str = ""):
    chat_id = update.effective_chat.id if update.message else update.callback_query.effective_chat.id
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user:
        await context.bot.send_message(chat_id=chat_id, text="Sesi login habis.")
        return
    api_key, tokens = AuthInstance.api_key, active_user["tokens"]
    package_list = context.user_data.get('full_package_details_list')
    if not package_list:
        await context.bot.send_message(chat_id=chat_id, text="❌ Tidak ada paket untuk diproses.")
        return
    payment_items = []
    for package in package_list:
        item_code, item_name = package.get("item_code") or package.get("code"), package.get("name") or package.get("option_name")
        if not item_code:
            error_name = item_name or 'Tidak Dikenal'
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Gagal: Paket '{error_name}' tidak memiliki kode item valid.")
            await show_main_menu_bot(update, context)
            return
        payment_items.append({"item_code": item_code, "item_price": package.get("price"), "item_name": item_name, "token_confirmation": package.get("token_confirmation", "")})
    await context.bot.send_message(chat_id=chat_id, text=f"✅ Memproses pembayaran via {payment_method}...")
    try:
        settlement_response = settlement_multipayment_v2(api_key, tokens, payment_items, wallet_number, payment_method.upper())
        if settlement_response and settlement_response.get("status") == "SUCCESS":
            BalanceServiceInstance.deduct_balance(chat_id, 5000)
            if payment_method not in ["OVO", "SHOPEEPAY"]:
                deeplink = settlement_response["data"].get("deeplink", "")
                if deeplink:
                    await context.bot.send_message(chat_id=chat_id, text=f"✅ Pembayaran {payment_method} berhasil dibuat.\n\nSelesaikan pembayaran di link:\n{deeplink}")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=f"✅ Pembayaran {payment_method} berhasil dibuat. Buka aplikasi Anda.")
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"✅ Pembayaran {payment_method} berhasil dibuat. Buka aplikasi Anda dan selesaikan pembayaran.")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Gagal memproses pembayaran: {settlement_response.get('message', 'Terjadi kesalahan.')}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error internal: {e}")
    await show_main_menu_bot(update, context)