import requests
import json

def get_hot_packages_data():
    """Mengambil data paket hot dari URL dan mengembalikannya sebagai JSON."""
    url = "https://me.mashu.lol/pg-hot.json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Ini akan menampilkan error jika status bukan 200
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil data hot package: {e}")
        return [] # Kembalikan list kosong jika gagal
    except json.JSONDecodeError:
        print("Error: Gagal mem-parsing JSON dari response hot package.")
        return []

def get_hot2_packages_data():
    """Mengambil data paket hot2 dari URL dan mengembalikannya sebagai JSON."""
    url = "https://me.mashu.lol/pg-hot2.json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil data hot2 package: {e}")
        return []
    except json.JSONDecodeError:
        print("Error: Gagal mem-parsing JSON dari response hot2 package.")
        return []