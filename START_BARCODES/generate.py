# BARCODE_GENERATOR_AUTOMANAGED_V3_EXACT_220X100
import os
import sys
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# Точный размер PDF из исходного генератора.
PDF_WIDTH_PT = 220
PDF_HEIGHT_PT = 100
PT_TO_MM = 25.4 / 72

script_dir = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(script_dir, "codes.txt")
OUTPUT_DIR = os.path.join(script_dir, "barcodes")

if not os.path.isfile(INPUT_FILE):
    print(f"Ошибка: файл {INPUT_FILE} не найден!")
    raise SystemExit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    codes = [line.strip() for line in f if line.strip()]

print(f"Найдено кодов в файле: {len(codes)}")
print(
    "Размер каждого PDF: "
    f"{PDF_WIDTH_PT} x {PDF_HEIGHT_PT} pt "
    f"({PDF_WIDTH_PT * PT_TO_MM:.2f} x {PDF_HEIGHT_PT * PT_TO_MM:.2f} mm)"
)

if not codes:
    print("Внимание: файл пуст. Ничего не создано.")
    raise SystemExit(0)

created = 0
for code in codes:
    if len(code) != 13 or not code.isdigit():
        print(f"Пропущен неверный код: {code}")
        continue

    # Сохраняем исходную логику и исходный масштаб без изменений.
    barcode = eanbc.Ean13BarcodeWidget(code)
    drawing = Drawing(PDF_WIDTH_PT, PDF_HEIGHT_PT)
    drawing.add(barcode)

    filename = os.path.join(OUTPUT_DIR, f"{code}.pdf")
    renderPDF.drawToFile(drawing, filename)
    print(f"Создан: {filename}")
    created += 1

print(f"Готово! Создано PDF: {created}")
raise SystemExit(0 if created else 2)
