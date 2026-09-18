import os
import sys
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk, colorchooser
from barcode import EAN13
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageTk
import subprocess
import tempfile
import threading
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
import xml.etree.ElementTree as ET

# ============================================
# ВАШ АЛГОРИТМ ГЕНЕРАЦИИ EAN-13 (адаптирован)
# ============================================

L_CODE = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
G_CODE = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001011", "0010111"]
R_CODE = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]

FIRST_DIGIT_PARITY = [
    "LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLGLL",
    "LGGLGL", "LGGGLG", "LGLGLG", "LGLGGL", "LGGLGL"
]

def calculate_checksum(code12: str) -> int:
    digits = [int(x) for x in code12]
    odd_sum = sum(digits[0::2])
    even_sum = sum(digits[1::2])
    total = odd_sum + even_sum * 3
    return (10 - (total % 10)) % 10

def generate_ean13_svg(code12: str, module_width: float, short_height: float, long_height: float,
                       bg_color: str, fg_color: str, font_size: float, font_family: str = "Arial, Helvetica, sans-serif") -> str:
    """
    Генерирует SVG-строку EAN-13 с правильными отбивками.
    Все размеры в миллиметрах.
    """
    checksum = calculate_checksum(code12)
    full_code = code12 + str(checksum)

    first_digit = int(full_code[0])
    parity_pattern = FIRST_DIGIT_PARITY[first_digit]

    binary_string = ""
    long_bars = set()

    # Старт (101)
    long_bars.update(range(len(binary_string), len(binary_string) + 3))
    binary_string += "101"

    # Левая часть (цифры 2-7)
    for i in range(1, 7):
        digit = int(full_code[i])
        binary_string += L_CODE[digit] if parity_pattern[i-1] == 'L' else G_CODE[digit]

    # Центр (01010)
    long_bars.update(range(len(binary_string), len(binary_string) + 5))
    binary_string += "01010"

    # Правая часть (цифры 8-13)
    for i in range(7, 13):
        digit = int(full_code[i])
        binary_string += R_CODE[digit]

    # Стоп (101)
    long_bars.update(range(len(binary_string), len(binary_string) + 3))
    binary_string += "101"

    # Построение SVG
    margin_left = 3.0   # место для первой цифры
    margin_top = 1.0

    total_width = 95 * module_width + margin_left + 3.0
    total_height = long_height + margin_top + 1.0

    # Корневой элемент
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': f'{total_width:.3f}mm',
        'height': f'{total_height:.3f}mm',
        'viewBox': f'0 0 {total_width:.3f} {total_height:.3f}'
    })

    # Фон
    ET.SubElement(svg, 'rect', {
        'width': f'{total_width:.3f}',
        'height': f'{total_height:.3f}',
        'fill': bg_color
    })

    # Полосы
    for idx, bit in enumerate(binary_string):
        if bit == '1':
            x = margin_left + idx * module_width
            h = long_height if idx in long_bars else short_height
            ET.SubElement(svg, 'rect', {
                'x': f'{x:.3f}',
                'y': f'{margin_top:.3f}',
                'width': f'{module_width:.3f}',
                'height': f'{h:.3f}',
                'fill': fg_color
            })

    # Шрифт для текста
    font_props = {
        'font-family': font_family,
        'font-size': f'{font_size:.2f}',
        'fill': fg_color,
        'text-anchor': 'middle'
    }

    # Первая цифра (слева)
    t1 = font_props.copy()
    t1.update({'x': f'{margin_left - 1.0:.2f}', 'y': f'{short_height + 3.2:.2f}', 'text-anchor': 'end'})
    ET.SubElement(svg, 'text', t1).text = full_code[0]

    # Левая группа (2-7)
    left_x = margin_left + (24 * module_width)  # центр левой части
    t2 = font_props.copy()
    t2.update({'x': f'{left_x:.2f}', 'y': f'{short_height + 3.2:.2f}', 'letter-spacing': '0.3'})
    ET.SubElement(svg, 'text', t2).text = full_code[1:7]

    # Правая группа (8-13)
    right_x = margin_left + (71 * module_width)  # центр правой части
    t3 = font_props.copy()
    t3.update({'x': f'{right_x:.2f}', 'y': f'{short_height + 3.2:.2f}', 'letter-spacing': '0.3'})
    ET.SubElement(svg, 'text', t3).text = full_code[7:13]

    return ET.tostring(svg, encoding='utf-8').decode('utf-8')


# ============================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС
# ============================================

class BarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор штрихкодов EAN-13 (стандарт GS1)")
        self.root.geometry("950x850")
        self.root.resizable(True, True)

        # Переменные настроек
        self.output_format = tk.StringVar(value="pdf")
        self.module_width = tk.DoubleVar(value=0.33)
        self.short_height = tk.DoubleVar(value=22.85)
        self.long_height = tk.DoubleVar(value=25.5)
        self.font_size = tk.DoubleVar(value=2.8)
        self.text_distance = tk.DoubleVar(value=3.2)   # отступ текста от низа коротких полос
        self.bg_color = tk.StringVar(value="white")
        self.fg_color = tk.StringVar(value="black")
        self.font_family = tk.StringVar(value="Arial, Helvetica, sans-serif")
        self.font_path = tk.StringVar(value="")

        self.output_folder = tk.StringVar(value=os.getcwd())

        # Создаём интерфейс
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Левая часть: ввод кодов
        left_frame = ttk.LabelFrame(main_frame, text="Ввод кодов EAN-13 (по одному на строку)", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))

        self.text_area = scrolledtext.ScrolledText(left_frame, height=20, width=40, font=("Courier", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.text_area.bind("<KeyRelease>", self.update_counter)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Загрузить из файла", command=self.load_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Очистить", command=self.clear_text).pack(side=tk.LEFT, padx=2)

        self.counter_label = ttk.Label(left_frame, text="Кодов: 0")
        self.counter_label.pack(anchor=tk.W, pady=2)

        # Правая часть: настройки
        right_frame = ttk.LabelFrame(main_frame, text="Настройки генерации", padding="5")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0))

        # Формат вывода
        ttk.Label(right_frame, text="Формат:").grid(row=0, column=0, sticky=tk.W, pady=2)
        format_frame = ttk.Frame(right_frame)
        format_frame.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Radiobutton(format_frame, text="PDF (вектор)", variable=self.output_format, value="pdf").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="PNG (растр)", variable=self.output_format, value="png").pack(side=tk.LEFT, padx=(10,0))

        # Параметры с отображением значений
        params = [
            ("Ширина модуля (мм):", "module_width", 0.1, 1.0, 0.01),
            ("Высота коротких (мм):", "short_height", 10.0, 30.0, 0.1),
            ("Высота длинных (мм):", "long_height", 12.0, 35.0, 0.1),
            ("Размер шрифта (мм):", "font_size", 1.0, 5.0, 0.1),
            ("Отступ текста (мм):", "text_distance", 0.0, 10.0, 0.1),
        ]
        self.value_labels = {}
        row = 1
        for label, var_name, min_val, max_val, step in params:
            ttk.Label(right_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = getattr(self, var_name)
            spinbox = ttk.Spinbox(right_frame, from_=min_val, to=max_val, increment=step, textvariable=var, width=8)
            spinbox.grid(row=row, column=1, sticky=tk.W, pady=2, padx=(0,5))
            val_label = ttk.Label(right_frame, text=f"{var.get():.2f}")
            val_label.grid(row=row, column=2, sticky=tk.W, pady=2)
            self.value_labels[var_name] = val_label
            spinbox.bind("<KeyRelease>", lambda e, v=var, vl=val_label: self.update_value_label(v, vl))
            row += 1

        # Цвета
        ttk.Label(right_frame, text="Цвет фона:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("bg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1
        ttk.Label(right_frame, text="Цвет штрихов:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("fg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # Шрифт
        ttk.Label(right_frame, text="Шрифт (TTF):").grid(row=row, column=0, sticky=tk.W, pady=2)
        font_frame = ttk.Frame(right_frame)
        font_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Button(font_frame, text="Выбрать .ttf", command=self.choose_font).pack(side=tk.LEFT)
        self.font_label = ttk.Label(font_frame, text="не выбран (системный)", foreground="gray")
        self.font_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # Папка сохранения
        ttk.Label(right_frame, text="Папка сохранения:").grid(row=row, column=0, sticky=tk.W, pady=2)
        folder_frame = ttk.Frame(right_frame)
        folder_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=2)
        self.folder_path_label = ttk.Label(folder_frame, text=self.output_folder.get(), width=30, relief=tk.SUNKEN)
        self.folder_path_label.pack(side=tk.LEFT)
        ttk.Button(folder_frame, text="Обзор", command=self.choose_folder).pack(side=tk.LEFT, padx=5)
        row += 1

        # Кнопки действий
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=row, column=0, columnspan=3, pady=15)
        ttk.Button(action_frame, text="Предпросмотр первого кода", command=self.preview_first).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Сгенерировать все", command=self.generate_all).pack(side=tk.LEFT, padx=5)

        # Прогресс
        self.progress = ttk.Progressbar(right_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.grid(row=row+1, column=0, columnspan=3, pady=10)

        # Статус
        self.status_label = ttk.Label(right_frame, text="Готов", foreground="green")
        self.status_label.grid(row=row+2, column=0, columnspan=3, pady=5)

    # ===== Вспомогательные методы =====
    def update_value_label(self, var, label):
        val = var.get()
        label.config(text=f"{val:.2f}")

    def update_counter(self, event=None):
        text = self.text_area.get("1.0", tk.END).strip()
        if text:
            codes = [line.strip() for line in text.splitlines() if line.strip()]
            self.counter_label.config(text=f"Кодов: {len(codes)}")
        else:
            self.counter_label.config(text="Кодов: 0")

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", content)
            self.update_counter()
            self.status_label.config(text=f"Загружен файл: {os.path.basename(file_path)}", foreground="blue")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")

    def clear_text(self):
        self.text_area.delete("1.0", tk.END)
        self.update_counter()
        self.status_label.config(text="Поле очищено", foreground="gray")

    def choose_color(self, which):
        color = colorchooser.askcolor(title=f"Выберите цвет для {which}")[1]
        if color:
            if which == "bg":
                self.bg_color.set(color)
                self.status_label.config(text=f"Цвет фона: {color}", foreground="blue")
            else:
                self.fg_color.set(color)
                self.status_label.config(text=f"Цвет штрихов: {color}", foreground="blue")

    def choose_font(self):
        font_path = filedialog.askopenfilename(filetypes=[("TrueType fonts", "*.ttf"), ("All files", "*.*")])
        if font_path:
            self.font_path.set(font_path)
            self.font_label.config(text=os.path.basename(font_path), foreground="black")
            # Для SVG мы используем имя семейства, но можно указать путь через @font-face.
            # Упростим: будем использовать системное имя, если файл загружен.
            # Поскольку в SVG мы не можем встроить шрифт напрямую, мы просто запоминаем путь.
            # При конвертации в PDF через svglib шрифт может не подхватиться, поэтому лучше оставить системный.
            self.status_label.config(text=f"Выбран шрифт: {os.path.basename(font_path)} (будет использован для PNG)", foreground="blue")

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)
            self.folder_path_label.config(text=folder)

    def get_codes(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if not text:
            return []
        codes = [line.strip() for line in text.splitlines() if line.strip()]
        valid = []
        for code in codes:
            if len(code) == 13 and code.isdigit():
                valid.append(code)
            else:
                messagebox.showwarning("Предупреждение", f"Код '{code}' пропущен (должен быть ровно 13 цифр).")
        return valid

    # ===== Генерация одного штрихкода =====
    def generate_one(self, code, output_dir, fmt):
        base_name = os.path.join(output_dir, code)
        if fmt == "png":
            # Для PNG используем стандартный ImageWriter (растр)
            writer = ImageWriter()
            writer.set_options({
                'module_width': self.module_width.get() * 0.8,  # примерный коэффициент
                'module_height': self.short_height.get() * 0.8,
                'font_size': int(self.font_size.get() * 3),
                'text_distance': self.text_distance.get() * 0.8,
                'quiet_zone': 3.0,
                'background': self.bg_color.get(),
                'foreground': self.fg_color.get(),
            })
            ean = EAN13(code, writer=writer)
            return ean.save(base_name)
        else:
            # PDF: генерируем SVG через наш алгоритм
            svg_str = generate_ean13_svg(
                code12=code,
                module_width=self.module_width.get(),
                short_height=self.short_height.get(),
                long_height=self.long_height.get(),
                bg_color=self.bg_color.get(),
                fg_color=self.fg_color.get(),
                font_size=self.font_size.get(),
                font_family="Arial, Helvetica, sans-serif"  # можно заменить на self.font_family.get()
            )
            # Сохраняем SVG во временный файл
            svg_path = base_name + "_temp.svg"
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_str)
            # Конвертируем SVG в PDF через svglib
            pdf_path = base_name + ".pdf"
            try:
                drawing = svg2rlg(svg_path)
                renderPDF.drawToFile(drawing, pdf_path)
                os.remove(svg_path)
                return pdf_path
            except Exception as e:
                if os.path.exists(svg_path):
                    os.remove(svg_path)
                raise Exception(f"Ошибка конвертации SVG в PDF: {e}")

    # ===== Предпросмотр =====
    def preview_first(self):
        codes = self.get_codes()
        if not codes:
            messagebox.showinfo("Информация", "Нет валидных кодов для предпросмотра.")
            return
        code = codes[0]
        fmt = self.output_format.get()
        temp_dir = tempfile.gettempdir()
        ext = ".pdf" if fmt == "pdf" else ".png"
        preview_path = os.path.join(temp_dir, "preview" + ext)
        if os.path.exists(preview_path):
            try:
                os.remove(preview_path)
            except:
                pass
        try:
            file_path = self.generate_one(code, temp_dir, fmt)
            os.rename(file_path, preview_path)
            self.open_file(preview_path)
            self.status_label.config(text=f"Предпросмотр создан: preview{ext}", foreground="green")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать предпросмотр:\n{e}")

    def open_file(self, path):
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])

    # ===== Генерация всех =====
    def generate_all(self):
        codes = self.get_codes()
        if not codes:
            messagebox.showinfo("Информация", "Нет валидных кодов для генерации.")
            return

        output_dir = self.output_folder.get()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                messagebox.showerror("Ошибка", "Не удалось создать папку для сохранения.")
                return

        fmt = self.output_format.get()
        total = len(codes)
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.status_label.config(text="Генерация...", foreground="orange")
        self.root.update()

        def generate():
            try:
                for i, code in enumerate(codes):
                    self.generate_one(code, output_dir, fmt)
                    self.progress['value'] = i + 1
                    self.root.update_idletasks()
                self.root.after(0, lambda: self.status_label.config(text=f"Готово! Создано {total} файлов.", foreground="green"))
                self.root.after(0, lambda: messagebox.showinfo("Готово", f"Создано {total} файлов в папке:\n{output_dir}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка генерации:\n{e}"))
                self.root.after(0, lambda: self.status_label.config(text="Ошибка", foreground="red"))
            finally:
                self.progress['value'] = 0

        threading.Thread(target=generate, daemon=True).start()


# ===== Запуск =====
if __name__ == "__main__":
    root = tk.Tk()
    app = BarcodeApp(root)
    root.mainloop()