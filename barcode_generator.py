import os
import subprocess
import sys
from barcode import EAN13
from barcode.writer import PDFWriter, ImageWriter

# ========== НАСТРОЙКИ ==========
INPUT_FILE = "codes.txt"          # файл со списком кодов (по одному на строку)
OUTPUT_FOLDER = "barcodes"        # папка для сохранения
OUTPUT_FORMAT = "pdf"             # "pdf" или "png" – выберите нужный
PREVIEW_FIRST = True              # показать предпросмотр первого кода

# Параметры штрихкода (для обоих форматов)
BARCODE_CONFIG = {
    'module_width': 0.3,      # мм
    'module_height': 15.0,    # мм
    'font_size': 12,          # пункты
    'text_distance': 6.0,     # мм
    'quiet_zone': 5.0,        # мм
    'background': 'white',
    'foreground': 'black',
}
# =================================

def generate_barcode(code, output_path, fmt='pdf'):
    """
    Генерирует штрихкод EAN-13 и сохраняет в векторный PDF или PNG.
    """
    if fmt == 'pdf':
        writer = PDFWriter()
    elif fmt == 'png':
        writer = ImageWriter()
    else:
        raise ValueError("Формат должен быть 'pdf' или 'png'")

    writer.set_options(BARCODE_CONFIG)
    ean = EAN13(code, writer=writer)
    # Метод save возвращает полный путь к сохранённому файлу (без расширения)
    # Для PDFWriter расширение .pdf, для ImageWriter .png
    saved_path = ean.save(output_path)
    return saved_path

def preview_file(file_path):
    """Открывает файл в стандартной программе просмотра."""
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден")
        return
    if sys.platform.startswith('win'):
        os.startfile(file_path)
    elif sys.platform.startswith('darwin'):  # macOS
        subprocess.run(['open', file_path])
    else:  # Linux
        subprocess.run(['xdg-open', file_path])

def main():
    # Создаём выходную папку
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Читаем коды
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            codes = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Ошибка: файл {INPUT_FILE} не найден.")
        return

    if not codes:
        print("Файл пуст.")
        return

    print(f"Найдено {len(codes)} кодов. Формат: {OUTPUT_FORMAT.upper()}")

    # Предпросмотр первого кода (если включён)
    if PREVIEW_FIRST and codes:
        first_code = codes[0]
        if len(first_code) == 13 and first_code.isdigit():
            temp_path = os.path.join(OUTPUT_FOLDER, f"preview_{first_code}")
            saved = generate_barcode(first_code, temp_path, OUTPUT_FORMAT)
            print(f"Предпросмотр: {saved}")
            preview_file(saved)
            input("Нажмите Enter, чтобы продолжить генерацию всех кодов...")
        else:
            print("Первый код невалидный, пропускаем предпросмотр.")

    # Генерация всех кодов
    for code in codes:
        if len(code) != 13 or not code.isdigit():
            print(f"Пропущен некорректный код: {code}")
            continue

        # Имя файла = код + расширение
        base_name = os.path.join(OUTPUT_FOLDER, code)
        saved_path = generate_barcode(code, base_name, OUTPUT_FORMAT)
        print(f"Создан: {saved_path}")

    print("Готово!")

if __name__ == "__main__":
    main()