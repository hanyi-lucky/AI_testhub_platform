# -*- coding: utf-8 -*-
# -----------------------------
# @Author    : 影子
# @Time      : 2026/2/2 10:35
# @Software  : PyCharm
# @FileName  : demo_pyzbar.py
# -----------------------------
from pyzbar import pyzbar
from PIL import Image


def decode_qr_code(image_path):
    image = Image.open(image_path)
    decoded_objects = pyzbar.decode(image)

    for obj in decoded_objects:
        # 尝试不同的编码格式
        try:
            data = obj.data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                data = obj.data.decode('gbk')  # 中文常用编码
            except UnicodeDecodeError:
                data = obj.data.decode('latin-1', errors='ignore')

        return data

print(decode_qr_code('../static_files/img/qrcode_1770115855_0c756a08_300px.png'))