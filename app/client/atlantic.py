import requests
import json
from app.config import ATLANTIC_API_KEY, ATLANTIC_BASE_URL

def get_deposit_methods():
    if not ATLANTIC_API_KEY:
        return None

    url = f"{ATLANTIC_BASE_URL}/deposit/metode"
    payload = {'api_key': ATLANTIC_API_KEY}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        data = response.json()

        if data.get("status") is True and data.get("data"):
            return data.get("data")
        else:
            return [] # Kembalikan list kosong jika tidak ada data
            
    except Exception:
        return None

def create_deposit_request(amount: int, metode_kode: str, metode_type: str, reff_id: str):
    if not ATLANTIC_API_KEY:
        return None

    url = f"{ATLANTIC_BASE_URL}/deposit/create"
    payload = {
        'api_key': ATLANTIC_API_KEY,
        'nominal': amount,
        'type': metode_type,
        'metode': metode_kode,
        'reff_id': reff_id
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        data = response.json()
        if data.get("status") is True:
            return data.get("data")
        else:
            return None
    except Exception:
        return None

def request_instant_deposit(deposit_id: str):
    if not ATLANTIC_API_KEY:
        return None
        
    url = f"{ATLANTIC_BASE_URL}/deposit/instant"
    payload = {'api_key': ATLANTIC_API_KEY, 'id': deposit_id, 'action': 'true'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        data = response.json()
        if data.get("status") is True:
            return data.get("data")
        else:
            return None
    except Exception:
        return None

# --- FUNGSI BARU DITAMBAHKAN DI SINI ---
def check_deposit_status(deposit_id: str):
    """Memanggil endpoint /deposit/status untuk mendapatkan detail transaksi."""
    if not ATLANTIC_API_KEY:
        print("API Key tidak ditemukan")
        return None
        
    url = f"{ATLANTIC_BASE_URL}/deposit/status"
    payload = {'api_key': ATLANTIC_API_KEY, 'id': deposit_id}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        data = response.json()
        
        # Berdasarkan dokumentasi, kita langsung mengembalikan objek 'data' jika statusnya True
        if data.get("status") is True:
            return data.get("data")
        else:
            print(f"Gagal cek status, pesan: {data.get('message')}")
            return None
            
    except Exception as e:
        print(f"Error saat cek status deposit: {e}")
        return None