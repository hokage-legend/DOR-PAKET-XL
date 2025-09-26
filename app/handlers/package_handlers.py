from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import math
import re

# Impor layanan, data, dan fungsi dari file lain
from app.service.auth import AuthInstance
from app.service.bookmark import BookmarkInstance
from app.data.package_data import PREDEFINED_FAMILY_CODES
from app.menus.package import get_packages_by_family_data
from app.menus.hot import get_hot_packages_data, get_hot2_packages_data
from app.client.engsel import get_family, get_package

# Impor dari handler lain
from .user_handlers import show_main_menu_bot

# Impor state dari config
from app.config import user_states, USER_STATE_SELECTING_PACKAGE, USER_STATE_CONFIRM_PURCHASE

# ====================================================================
# === FUNGSI HELPER UNTUK MENGOLAH DATA PAKET ========================
# ====================================================================

async def get_full_package_details_from_hot_data(context: ContextTypes.DEFAULT_TYPE, hot_package_shortcut: dict, chat_id: int):
    """
    Mengambil data paket lengkap (harga, kode, dll.) dari API
    berdasarkan data pintasan dari file JSON (untuk paket HOT).
    """
    api_key = AuthInstance.api_key
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user: return None
    
    tokens = active_user["tokens"]
    family_code = hot_package_shortcut.get("family_code")
    is_enterprise = hot_package_shortcut.get("is_enterprise", False)
    target_variant_name = hot_package_shortcut.get("variant_name")
    target_order = hot_package_shortcut.get("order")

    if not all([family_code, target_variant_name, target_order is not None]):
        return None
        
    family_data = get_family(api_key, tokens, family_code, is_enterprise)
    if not family_data or "package_variants" not in family_data:
        return None

    for variant in family_data.get("package_variants", []):
        if variant.get("name") == target_variant_name:
            for option in variant.get("package_options", []):
                if option.get("order") == target_order:
                    package_name = option.get("name")
                    package_code = option.get("package_option_code")
                    if not package_name or not package_code:
                        return None
                    
                    full_details = option
                    full_details['token_confirmation'] = ""
                    full_details['item_code'] = package_code
                    full_details['name'] = package_name
                    # Tambahkan info penting lain yang mungkin kurang
                    full_details['family_code'] = family_code
                    full_details['package_variant_code'] = variant.get("package_variant_code")
                    return full_details
    return None

def format_package_benefits(package_details: dict) -> str:
    """Mengubah data benefit dari API menjadi teks yang rapi dan mudah dibaca."""
    if not package_details:
        return "Detail tidak tersedia."

    option = package_details.get("package_option", {})
    family = package_details.get("package_family", {})
    variant = package_details.get("package_detail_variant", {})
    
    name = f"{family.get('name', '')} {variant.get('name', '')} {option.get('name', '')}".strip()
    price = option.get('price', 0)
    validity = option.get('validity', 'N/A')
    
    message = (
        f"📦 *Detail Paket*\n\n"
        f"🏷️ *Nama*: {name}\n"
        f"💰 *Harga*: Rp {price:,}\n"
        f"🗓️ *Masa Aktif*: {validity}\n\n"
        f"🎁 *Benefit Paket:*\n"
    )

    benefits = option.get("benefits", [])
    if not benefits:
        message += "Tidak ada benefit spesifik yang terdaftar.\n"
    else:
        for benefit in benefits:
            b_name = benefit.get('name', 'Benefit')
            b_total = benefit.get('total', 0)
            quota_str = ""
            if b_total > 0:
                if "Call" in b_name or "SMS" in b_name:
                    quota_str = f"{int(b_total / 60)} menit" if "Call" in b_name else f"{b_total} SMS"
                else:
                    if b_total >= 1024**3: quota_str = f"{b_total / (1024**3):.2f} GB"
                    elif b_total >= 1024**2: quota_str = f"{b_total / (1024**2):.2f} MB"
                    else: quota_str = f"{b_total / 1024:.2f} KB"
            message += f"- {b_name} ({quota_str})\n" if quota_str else f"- {b_name}\n"

    tnc = option.get("tnc", "")
    if tnc:
        clean_tnc = re.sub('<[^<]+?>', '', tnc).replace('&amp;', '&')
        message += f"\n📜 *Syarat & Ketentuan:*\n{clean_tnc}"
        
    return message

# ====================================================================
# === HANDLER UNTUK BROWSE DAN MEMILIH PAKET =========================
# ====================================================================

async def show_predefined_packages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    chat_id = update.effective_chat.id
    ITEMS_PER_PAGE = 8
    package_filter = context.user_data.get('package_filter', 'all')
    
    if package_filter == 'enterprise':
        display_list = [pkg for pkg in PREDEFINED_FAMILY_CODES if pkg.get('is_enterprise')]
        menu_title = "🏢 Silakan pilih dari daftar Paket Enterprise:"
    else:
        display_list = PREDEFINED_FAMILY_CODES
        menu_title = "📜 Silakan pilih dari daftar Semua Paket:"

    if not display_list:
        await context.bot.send_message(chat_id, text=f"😢 Tidak ada paket '{package_filter}' yang terdaftar.")
        await show_main_menu_bot(update, context)
        return

    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    page_items = display_list[start_index:end_index]
    keyboard = []
    
    for item in page_items:
        callback_data = f"family_{item['family_code']}_{item['is_enterprise']}"
        keyboard.append([InlineKeyboardButton(item['name'], callback_data=callback_data)])

    nav_buttons = []
    total_pages = math.ceil(len(display_list) / ITEMS_PER_PAGE)
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"family_page_{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if end_index < len(display_list):
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"family_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')])
    
    if update.callback_query:
        await update.callback_query.message.edit_text(menu_title, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id, text=menu_title, reply_markup=InlineKeyboardMarkup(keyboard))

async def search_packages_and_display(update: Update, context: ContextTypes.DEFAULT_TYPE, family_code: str, is_enterprise: bool):
    chat_id = update.effective_chat.id
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user:
        await context.bot.send_message(chat_id=chat_id, text="Sesi Anda tidak ditemukan, silakan login kembali.")
        await show_main_menu_bot(update, context)
        return

    tokens = active_user.get("tokens")
    packages = get_packages_by_family_data(family_code, is_enterprise, tokens) 
    
    if not packages:
        await context.bot.send_message(chat_id=chat_id, text="😢 Tidak ditemukan paket untuk family code ini.")
        await show_main_menu_bot(update, context)
        return

    context.user_data['current_packages'] = packages
    message = "✅ **Paket Tersedia:**\n\nSilakan pilih salah satu paket di bawah ini."
    keyboard = []
    for idx, pkg in enumerate(packages):
        button_text = f"{pkg.get('number', '?')}. {pkg.get('option_name', 'N/A')} - Rp {pkg.get('price', 'N/A')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_pkg_{idx}")])
    keyboard.append([InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')])
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    user_states[chat_id] = USER_STATE_SELECTING_PACKAGE

async def search_and_display_hot_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    packages = get_hot_packages_data()
    chat_id = update.effective_chat.id
    if not packages:
        await context.bot.send_message(chat_id=chat_id, text="😢 Tidak ditemukan paket HOT.")
        return
    context.user_data['current_packages'] = packages
    message = "🔥 **Paket Hot Tersedia:**\n\nSilakan pilih salah satu paket di bawah ini."
    keyboard = []
    for idx, p in enumerate(packages):
        button_text = f"{idx + 1}. {p.get('option_name', '')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_pkg_{idx}")])
    keyboard.append([InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')])
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    user_states[chat_id] = USER_STATE_SELECTING_PACKAGE

async def search_and_display_hot2_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    packages = get_hot2_packages_data()
    chat_id = update.effective_chat.id
    if not packages:
        await context.bot.send_message(chat_id=chat_id, text="😢 Tidak ditemukan paket HOT 2.")
        return
    context.user_data['current_packages'] = packages
    message = "🔥 **Paket Hot 2 Tersedia:**\n\nSilakan pilih salah satu paket di bawah ini."
    keyboard = []
    for idx, p in enumerate(packages):
        button_text = f"{idx + 1}. {p.get('name', '')} - Rp {p.get('price', 'N/A')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_pkg_{idx}")])
    keyboard.append([InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')])
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    user_states[chat_id] = USER_STATE_SELECTING_PACKAGE

async def package_selection_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    
    await query.message.edit_text("⏳ *Mengambil detail paket...*", parse_mode="Markdown")

    choice_idx = int(query.data.split('_')[2])
    packages_data = context.user_data.get('current_packages')
    
    if not packages_data or choice_idx >= len(packages_data):
        await query.message.edit_text("Pilihan tidak valid atau data sudah kedaluwarsa.")
        return

    selected_shortcut = packages_data[choice_idx]
    
    active_user = AuthInstance.get_active_user(chat_id)
    if not active_user:
        await query.message.edit_text("Sesi Anda berakhir, silakan /start lagi.")
        return

    complete_package_data = None
    if 'family_code' in selected_shortcut and 'code' not in selected_shortcut:
        complete_package_data = await get_full_package_details_from_hot_data(context, selected_shortcut, chat_id)
    else:
        complete_package_data = selected_shortcut

    if not complete_package_data:
        await query.message.edit_text("Gagal mendapatkan informasi dasar untuk paket ini.")
        return
        
    context.user_data['selected_package_to_buy'] = complete_package_data

    tokens = active_user['tokens']
    package_option_code = complete_package_data.get('code') or complete_package_data.get('item_code')
    package_family_code = complete_package_data.get('family_code')
    package_variant_code = complete_package_data.get('package_variant_code')
    # Ambil status enterprise dari data paket yang sudah lengkap
    is_enterprise = complete_package_data.get('is_enterprise', False) 
    
    # Panggil API dengan semua parameter yang dibutuhkan, termasuk is_enterprise
    full_details = get_package(
        api_key=AuthInstance.api_key, 
        tokens=tokens, 
        package_option_code=package_option_code,
        is_enterprise=is_enterprise, # <-- KIRIM STATUS ENTERPRISE
        package_family_code=package_family_code,
        package_variant_code=package_variant_code
    )
    
    if not full_details:
        await query.message.edit_text("Gagal mengambil detail benefit untuk paket ini dari server.")
        return
        
    detail_message = format_package_benefits(full_details)

    keyboard = [
        [
            InlineKeyboardButton("✅ Lanjutkan Pembelian", callback_data='confirm_purchase'),
            InlineKeyboardButton("❌ Batal", callback_data='cancel_purchase')
        ],
        [
            InlineKeyboardButton(f"⭐ Tambah ke Bookmark", callback_data=f'add_bookmark_{choice_idx}')
        ]
    ]
    
    await query.message.edit_text(
        text=detail_message, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    user_states[chat_id] = USER_STATE_CONFIRM_PURCHASE

async def family_code_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action = data[1]
    if action == "page":
        page = int(data[2])
        await show_predefined_packages_menu(update, context, page=page)
    else:
        await query.edit_message_reply_markup(reply_markup=None)
        family_code, is_enterprise_str = data[1], data[2]
        is_enterprise = is_enterprise_str.lower() == 'true'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔍 Mencari paket...")
        await search_packages_and_display(update, context, family_code, is_enterprise)

async def show_bookmark_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    bookmarks = BookmarkInstance.get_bookmarks()
    if not bookmarks:
        await context.bot.send_message(chat_id=chat_id, text="😢 Belum ada paket yang di-bookmark.")
        await show_main_menu_bot(update, context)
        return
    message = "⭐ **Paket Bookmark Tersedia:**\n\nSilakan pilih salah satu paket favorit di bawah ini."
    keyboard = []
    for idx, item in enumerate(bookmarks):
        keyboard.append([InlineKeyboardButton(item.get('option_name', item.get('name', 'N/A')), callback_data=f"bookmark_{idx}")])
    keyboard.append([InlineKeyboardButton("« Kembali ke Menu Utama", callback_data='menu_back_main')])
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def bookmark_selection_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_reply_markup(reply_markup=None)
    try:
        bookmarks = BookmarkInstance.get_bookmarks()
        choice_idx = int(query.data.split('_')[1])
        if choice_idx >= len(bookmarks):
            await context.bot.send_message(chat_id=chat_id, text="Pilihan bookmark tidak valid.")
            return
        selected_bookmark = bookmarks[choice_idx]
        
        # Bookmark adalah shortcut, jadi kita perlakukan seperti paket HOT
        # Kita panggil package_selection_handler dengan data shortcut ini
        # Ini akan memicu alur pengambilan detail lengkap secara otomatis
        context.user_data['current_packages'] = [selected_bookmark] # Simpan sebagai list agar index 0 valid
        query.data = "select_pkg_0" # Palsukan callback seolah-olah item pertama dipilih
        await package_selection_callback_handler(update, context)

    except (IndexError, ValueError) as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Terjadi error saat memproses bookmark: {e}")

async def add_bookmark_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    choice_idx = int(query.data.split('_')[2])
    packages_data = context.user_data.get('current_packages')
    if not packages_data or choice_idx >= len(packages_data):
        await context.bot.send_message(chat_id=chat_id, text="Gagal menambah bookmark, data sudah kedaluwarsa.")
        return
    pkg = packages_data[choice_idx]
    
    # Memastikan semua data yang dibutuhkan class Bookmark ada
    success = BookmarkInstance.add_bookmark(
        family_code=pkg.get('family_code'),
        family_name=pkg.get('family_name', ''),
        is_enterprise=pkg.get('is_enterprise', False),
        variant_name=pkg.get('variant_name'),
        option_name=pkg.get('option_name'),
        order=pkg.get('option_order') # Gunakan option_order yang kita simpan
    )
    if success:
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Paket '{pkg.get('option_name')}' berhasil ditambahkan ke bookmark.")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"ℹ️ Paket '{pkg.get('option_name')}' sudah ada di bookmark.")