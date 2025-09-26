#!/usr/bin/env bash

# 1. Perbarui daftar paket dari repository
sudo apt update -y

# 2. Install Python 3 dan PIP (Python Package Installer)
sudo apt install python3 python3-pip -y

# 3. Install semua library Python yang dibutuhkan dari file requirements.txt
pip3 install -r requirements.txt
pip install qrcode[pil]

echo "Instalasi selesai!"