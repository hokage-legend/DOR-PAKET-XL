from flask import Flask, request, jsonify
import hashlib
import asyncio

# Variabel global untuk menyimpan referensi
bot_instance = None
balance_service_instance = None
reff_id_map_instance = None
ATLANTIC_API_USERNAME = "ganti_dengan_username_api_anda" # PENTING: Ganti ini

# Nama variabel diubah menjadi 'app' agar Gunicorn bisa menemukannya
app = Flask(__name__)

@app.route('/webhook/atlantic', methods=['POST'])
def atlantic_webhook():
    # ... (Isi fungsi ini tidak diubah) ...
    signature = request.headers.get('X-ATL-Signature')
    expected_signature = hashlib.md5(ATLANTIC_API_USERNAME.encode()).hexdigest()

    if signature != expected_signature:
        return jsonify({"status": "error", "message": "Invalid signature"}), 401

    data = request.json
    event = data.get('event')
    status = data.get('status')
    
    if (event == 'deposit.fast' or event == 'deposit') and status == 'success':
        try:
            deposit_data = data.get('data', {})
            reff_id = deposit_data.get('reff_id')
            
            if reff_id in reff_id_map_instance:
                chat_id = reff_id_map_instance[reff_id]
                nominal_diterima = deposit_data.get('get_balance', deposit_data.get('nominal'))
                
                if nominal_diterima:
                    balance_service_instance.add_balance(chat_id, nominal_diterima)
                    success_message = f"✅ Top Up Otomatis Berhasil! Saldo sebesar *Rp {nominal_diterima:,}* telah ditambahkan."
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(bot_instance.send_message(chat_id=chat_id, text=success_message, parse_mode="Markdown"))
                    loop.close()

                    del reff_id_map_instance[reff_id]
        except Exception as e:
            print(f"Error processing webhook: {e}")

    return jsonify({"status": "received"}), 200

# PENTING: Fungsi run_webhook_server dan baris app.run() DIHAPUS.
# Gunicorn akan menangani servernya dari luar file ini.