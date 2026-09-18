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
# АЛГОРИТМ ГЕНЕРАЦИИ EAN-13 (стандарт GS1)
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
                       left_margin: float, right_margin: float,
                       bg_color: str, fg_color: str, font_size: float, text_distance: float,
                       font_family: str = "Arial, Helvetica, sans-serif") -> str:
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
    margin_top = 1.0  # небольшой отступ сверху

    total_width = 95 * module_width + left_margin + right_margin
    total_height = long_height + margin_top + 1.0

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
            x = left_margin + idx * module_width
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

    # Базовая позиция текста по Y:
    # Чтобы верхний край цифр был на расстоянии text_distance от низа коротких полос,
    # нужно поднять Y на высоту шрифта (так как текст рисуется вверх от baseline)
    text_y = short_height + text_distance + font_size

    # Первая цифра (слева, выравнивание по центру левого поля)
    first_x = left_margin - (left_margin / 2)
    t1 = font_props.copy()
    t1.update({'x': f'{first_x:.2f}', 'y': f'{text_y:.2f}', 'text-anchor': 'middle'})
    ET.SubElement(svg, 'text', t1).text = full_code[0]

    # Левая группа (2-7) – центр между 3-м и 45-м модулем (3 + 42/2 = 24)
    left_center = left_margin + 24 * module_width
    t2 = font_props.copy()
    t2.update({'x': f'{left_center:.2f}', 'y': f'{text_y:.2f}', 'letter-spacing': '0.3'})
    ET.SubElement(svg, 'text', t2).text = full_code[1:7]

    # Правая группа (8-13) – центр между 50-м и 92-м модулем (50 + 42/2 = 71)
    right_center = left_margin + 71 * module_width
    t3 = font_props.copy()
    t3.update({'x': f'{right_center:.2f}', 'y': f'{text_y:.2f}', 'letter-spacing': '0.3'})
    ET.SubElement(svg, 'text', t3).text = full_code[7:13]

    return ET.tostring(svg, encoding='utf-8').decode('utf-8')


# ============================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС
# ============================================

class BarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("uCode – Генератор штрихкодов EAN-13")
        self.root.geometry("1020x900")
        self.root.minsize(800, 600)  # минимальный размер окна

        # Переменные настроек (по ГОСТу)
        self.output_format = tk.StringVar(value="pdf")
        self.module_width = tk.DoubleVar(value=0.330)
        self.short_height = tk.DoubleVar(value=22.85)
        self.long_height = tk.DoubleVar(value=24.50)
        self.left_margin = tk.DoubleVar(value=3.63)
        self.right_margin = tk.DoubleVar(value=2.31)
        self.font_size = tk.DoubleVar(value=2.75)
        self.text_distance = tk.DoubleVar(value=0.50)
        self.bg_color = tk.StringVar(value="#ffffff")
        self.fg_color = tk.StringVar(value="#000000")  # чёрный (CMYK 0,0,0,100)

        # Дополнительные переменные для CMYK
        self.cmyk_c = tk.IntVar(value=0)
        self.cmyk_m = tk.IntVar(value=0)
        self.cmyk_y = tk.IntVar(value=0)
        self.cmyk_k = tk.IntVar(value=100)

        self.font_family = tk.StringVar(value="Arial, Helvetica, sans-serif")
        self.font_path = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value=os.getcwd())

        # Создаём интерфейс
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Верхняя информационная панель (логотип)
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Label(info_frame, text="uCode Barcode Generator v1.0.1", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(info_frame, text="© 2025 Sunpole XCVE33, Anton Magomedov", font=("Arial", 9)).pack(side=tk.RIGHT)

        # Основной контейнер: левая часть (ввод) и правая (настройки с прокруткой)
        container = ttk.Frame(main_frame)
        container.pack(fill=tk.BOTH, expand=True)

        # Левая часть: ввод кодов
        left_frame = ttk.LabelFrame(container, text="Ввод кодов EAN-13 (по одному на строку)", padding="5")
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

        # Правая часть: настройки с прокруткой
        right_container = ttk.Frame(container)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0))

        # Создаём холст с прокруткой
        canvas = tk.Canvas(right_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Теперь все настройки размещаем внутри scrollable_frame
        right_frame = ttk.LabelFrame(scrollable_frame, text="Настройки генерации (ГОСТ по умолчанию)", padding="5")
        right_frame.pack(fill=tk.X, expand=True, pady=(0,10))

        # Формат вывода
        ttk.Label(right_frame, text="Формат:").grid(row=0, column=0, sticky=tk.W, pady=2)
        format_frame = ttk.Frame(right_frame)
        format_frame.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Radiobutton(format_frame, text="PDF (вектор)", variable=self.output_format, value="pdf").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="PNG (растр)", variable=self.output_format, value="png").pack(side=tk.LEFT, padx=(10,0))

        # Параметры с отображением значений
        params = [
            ("Ширина модуля (мм):", "module_width", 0.1, 0.5, 0.001),
            ("Высота коротких (мм):", "short_height", 10.0, 35.0, 0.01),
            ("Высота длинных (мм):", "long_height", 12.0, 40.0, 0.01),
            ("Левый отступ (мм):", "left_margin", 0.0, 10.0, 0.01),
            ("Правый отступ (мм):", "right_margin", 0.0, 10.0, 0.01),
            ("Размер шрифта (мм):", "font_size", 1.0, 6.0, 0.01),
            ("Отступ текста (мм):", "text_distance", 0.0, 5.0, 0.01),
        ]
        self.value_labels = {}
        row = 1
        for label, var_name, min_val, max_val, step in params:
            ttk.Label(right_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = getattr(self, var_name)
            spinbox = ttk.Spinbox(right_frame, from_=min_val, to=max_val, increment=step, textvariable=var, width=8)
            spinbox.grid(row=row, column=1, sticky=tk.W, pady=2, padx=(0,5))
            val_label = ttk.Label(right_frame, text=f"{var.get():.3f}")
            val_label.grid(row=row, column=2, sticky=tk.W, pady=2)
            self.value_labels[var_name] = val_label
            spinbox.bind("<KeyRelease>", lambda e, v=var, vl=val_label: self.update_value_label(v, vl))
            row += 1

        # Цвета (RGB + CMYK)
        ttk.Label(right_frame, text="Цвет фона:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("bg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        self.bg_color_preview = tk.Label(right_frame, bg=self.bg_color.get(), width=4, relief=tk.SUNKEN)
        self.bg_color_preview.grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1

        ttk.Label(right_frame, text="Цвет штрихов:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("fg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        self.fg_color_preview = tk.Label(right_frame, bg=self.fg_color.get(), width=4, relief=tk.SUNKEN)
        self.fg_color_preview.grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1

        # CMYK
        cmyk_frame = ttk.LabelFrame(right_frame, text="CMYK (для чёрного по умолчанию C=0 M=0 Y=0 K=100)")
        cmyk_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)
        ttk.Label(cmyk_frame, text="C:").pack(side=tk.LEFT)
        c_entry = ttk.Entry(cmyk_frame, textvariable=self.cmyk_c, width=4)
        c_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(cmyk_frame, text="M:").pack(side=tk.LEFT)
        m_entry = ttk.Entry(cmyk_frame, textvariable=self.cmyk_m, width=4)
        m_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(cmyk_frame, text="Y:").pack(side=tk.LEFT)
        y_entry = ttk.Entry(cmyk_frame, textvariable=self.cmyk_y, width=4)
        y_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(cmyk_frame, text="K:").pack(side=tk.LEFT)
        k_entry = ttk.Entry(cmyk_frame, textvariable=self.cmyk_k, width=4)
        k_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(cmyk_frame, text="Применить к штрихам", command=self.apply_cmyk).pack(side=tk.LEFT, padx=5)
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
        label.config(text=f"{val:.3f}")

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
        color = colorchooser.askcolor(title=f"Выберите цвет для {which}", initialcolor=self.fg_color.get() if which=="fg" else self.bg_color.get())
        if color:
            hex_color = color[1]
            if which == "bg":
                self.bg_color.set(hex_color)
                self.bg_color_preview.config(bg=hex_color)
                self.status_label.config(text=f"Цвет фона: {hex_color}", foreground="blue")
            else:
                self.fg_color.set(hex_color)
                self.fg_color_preview.config(bg=hex_color)
                self.status_label.config(text=f"Цвет штрихов: {hex_color}", foreground="blue")

    def apply_cmyk(self):
        """Переводит CMYK в RGB и устанавливает цвет штрихов"""
        c = self.cmyk_c.get() / 100.0
        m = self.cmyk_m.get() / 100.0
        y = self.cmyk_y.get() / 100.0
        k = self.cmyk_k.get() / 100.0
        r = int(255 * (1 - c) * (1 - k))
        g = int(255 * (1 - m) * (1 - k))
        b = int(255 * (1 - y) * (1 - k))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.fg_color.set(hex_color)
        self.fg_color_preview.config(bg=hex_color)
        self.status_label.config(text=f"Цвет штрихов: CMYK({self.cmyk_c.get()},{self.cmyk_m.get()},{self.cmyk_y.get()},{self.cmyk_k.get()}) -> {hex_color}", foreground="blue")

    def choose_font(self):
        font_path = filedialog.askopenfilename(filetypes=[("TrueType fonts", "*.ttf"), ("All files", "*.*")])
        if font_path:
            self.font_path.set(font_path)
            self.font_label.config(text=os.path.basename(font_path), foreground="black")
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
            # Для PNG используем стандартный ImageWriter (растр) – он не поддерживает правильные отбивки,
            # но для быстрой визуализации сойдёт.
            writer = ImageWriter()
            dpi = 300
            module_px = self.module_width.get() * dpi / 25.4
            writer.set_options({
                'module_width': module_px,
                'module_height': self.short_height.get() * dpi / 25.4,
                'font_size': int(self.font_size.get() * dpi / 25.4),
                'text_distance': self.text_distance.get() * dpi / 25.4,
                'quiet_zone': 0,
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
                left_margin=self.left_margin.get(),
                right_margin=self.right_margin.get(),
                bg_color=self.bg_color.get(),
                fg_color=self.fg_color.get(),
                font_size=self.font_size.get(),
                text_distance=self.text_distance.get(),
                font_family="Arial, Helvetica, sans-serif"
            )
            svg_path = base_name + "_temp.svg"
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_str)
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