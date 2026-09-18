# +--------------------------------------------------------------------------------------+
# |                                     uCode_v_2.0                                      |
# |    Copyright (c) 2026 Anton Magomedov | @sunpole | @xcve33 | All rights reserved.    |
# +--------------------------------------------------------------------------------------+

import os
import math
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm

# === Настройки ===
MARGIN_MM = 3                 # белое поле со всех сторон
ROUND_PAGE_TO_WHOLE_MM = True # округлять размер страницы до целых мм

# === Определяем папку, где находится сам скрипт ===
script_dir = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(script_dir, "codes.txt")
OUTPUT_DIR = os.path.join(script_dir, "barcodes")

# === Проверка наличия входного файла ===
if not os.path.isfile(INPUT_FILE):
    print(f"Ошибка: файл {INPUT_FILE} не найден!")
    exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Чтение кодов ===
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    codes = [line.strip() for line in f if line.strip()]

print(f"Найдено кодов в файле: {len(codes)}")
if not codes:
    print("Внимание: файл пуст. Ничего не создано.")
    exit(0)

# === Генерация штрихкодов ===
for code in codes:
    if len(code) != 13 or not code.isdigit():
        print(f"Пропущен неверный код: {code}")
        continue

    barcode = eanbc.Ean13BarcodeWidget(code)

    # Границы реального штрихкода
    x1, y1, x2, y2 = barcode.getBounds()
    barcode_width = x2 - x1
    barcode_height = y2 - y1

    # Поля
    margin_pt = MARGIN_MM * mm

    raw_page_width = barcode_width + margin_pt * 2
    raw_page_height = barcode_height + margin_pt * 2

    # Если нужно — делаем размер страницы кратным целому мм
    if ROUND_PAGE_TO_WHOLE_MM:
        page_width_mm = math.ceil(raw_page_width / mm)
        page_height_mm = math.ceil(raw_page_height / mm)
        page_width = page_width_mm * mm
        page_height = page_height_mm * mm
    else:
        page_width = raw_page_width
        page_height = raw_page_height

    # Из-за округления до целых мм может появиться небольшой "лишний запас".
    # Распределяем его равномерно, чтобы штрихкод был по центру.
    extra_x = (page_width - raw_page_width) / 2
    extra_y = (page_height - raw_page_height) / 2

    # Смещаем штрихкод внутрь страницы
    barcode.x = margin_pt - x1 + extra_x
    barcode.y = margin_pt - y1 + extra_y

    drawing = Drawing(page_width, page_height)
    drawing.add(barcode)

    filename = os.path.join(OUTPUT_DIR, f"{code}.pdf")
    renderPDF.drawToFile(drawing, filename)

    print(
        f"Создан: {filename} | "
        f"Размер страницы: {page_width/mm:.2f} × {page_height/mm:.2f} мм"
    )

print("Готово!")