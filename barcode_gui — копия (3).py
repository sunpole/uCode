import os
import sys
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk, colorchooser
from barcode import EAN13
from barcode.writer import ImageWriter, SVGWriter
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

# ========== Класс приложения ==========
class BarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор штрихкодов EAN-13")
        self.root.geometry("900x800")
        self.root.resizable(True, True)

        # Переменные для настроек
        self.output_format = tk.StringVar(value="pdf")
        self.module_width = tk.DoubleVar(value=0.3)
        self.module_height = tk.DoubleVar(value=15.0)
        self.font_size = tk.IntVar(value=12)
        self.text_distance = tk.DoubleVar(value=6.0)
        self.quiet_zone = tk.DoubleVar(value=5.0)
        self.bg_color = tk.StringVar(value="white")
        self.fg_color = tk.StringVar(value="black")
        self.font_path = tk.StringVar(value="")  # путь к .ttf

        self.output_folder = tk.StringVar(value=os.getcwd())
        self.codes_text = ""
        self.codes_list = []

        # Создаём интерфейс
        self.create_widgets()

    def create_widgets(self):
        # Основной фрейм с прокруткой
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Левая часть: ввод кодов
        left_frame = ttk.LabelFrame(main_frame, text="Ввод кодов EAN-13", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))

        # Текстовое поле с прокруткой
        self.text_area = scrolledtext.ScrolledText(left_frame, height=20, width=40, font=("Courier", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.text_area.bind("<KeyRelease>", self.update_counter)

        # Кнопки управления текстом
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Загрузить из файла", command=self.load_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Очистить", command=self.clear_text).pack(side=tk.LEFT, padx=2)

        # Счётчик кодов
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

        # Параметры штрихкода
        params = [
            ("Ширина модуля (мм):", "module_width", 0.1, 1.0),
            ("Высота модуля (мм):", "module_height", 5.0, 30.0),
            ("Размер шрифта (пт):", "font_size", 6, 24),
            ("Отступ текста (мм):", "text_distance", 0, 15),
            ("Тихая зона (мм):", "quiet_zone", 0, 20),
        ]
        row = 1
        for label, var_name, min_val, max_val in params:
            ttk.Label(right_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = getattr(self, var_name)
            spinbox = ttk.Spinbox(right_frame, from_=min_val, to=max_val, increment=0.1, textvariable=var, width=10)
            spinbox.grid(row=row, column=1, sticky=tk.W, pady=2)
            row += 1

        # Выбор цвета
        ttk.Label(right_frame, text="Цвет фона:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("bg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1
        ttk.Label(right_frame, text="Цвет штрихов:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(right_frame, text="Выбрать", command=lambda: self.choose_color("fg")).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # Выбор шрифта (только для PDF, в PNG используется PIL)
        ttk.Label(right_frame, text="Шрифт (TTF):").grid(row=row, column=0, sticky=tk.W, pady=2)
        font_frame = ttk.Frame(right_frame)
        font_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Button(font_frame, text="Выбрать .ttf", command=self.choose_font).pack(side=tk.LEFT)
        self.font_label = ttk.Label(font_frame, text="не выбран", foreground="gray")
        self.font_label.pack(side=tk.LEFT, padx=5)
        row += 1

        # Папка сохранения
        ttk.Label(right_frame, text="Папка сохранения:").grid(row=row, column=0, sticky=tk.W, pady=2)
        folder_frame = ttk.Frame(right_frame)
        folder_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        self.folder_path_label = ttk.Label(folder_frame, text=self.output_folder.get(), width=25, relief=tk.SUNKEN)
        self.folder_path_label.pack(side=tk.LEFT)
        ttk.Button(folder_frame, text="Обзор", command=self.choose_folder).pack(side=tk.LEFT, padx=5)
        row += 1

        # Кнопки действий
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=row, column=0, columnspan=2, pady=15)
        ttk.Button(action_frame, text="Предпросмотр первого кода", command=self.preview_first).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Сгенерировать все", command=self.generate_all).pack(side=tk.LEFT, padx=5)

        # Прогресс-бар
        self.progress = ttk.Progressbar(right_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.grid(row=row+1, column=0, columnspan=2, pady=10)

        # Статус
        self.status_label = ttk.Label(right_frame, text="Готов", foreground="green")
        self.status_label.grid(row=row+2, column=0, columnspan=2, pady=5)

    # ===== Функции =====
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
            self.status_label.config(text=f"Выбран шрифт: {os.path.basename(font_path)}", foreground="blue")

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

    def generate_one(self, code, output_dir, fmt):
        """Генерирует один штрихкод в заданном формате и возвращает путь к файлу."""
        base_name = os.path.join(output_dir, code)
        if fmt == "png":
            writer = ImageWriter()
            writer.set_options({
                'module_width': self.module_width.get(),
                'module_height': self.module_height.get(),
                'font_size': self.font_size.get(),
                'text_distance': self.text_distance.get(),
                'quiet_zone': self.quiet_zone.get(),
                'background': self.bg_color.get(),
                'foreground': self.fg_color.get(),
            })
            ean = EAN13(code, writer=writer)
            return ean.save(base_name)  # возвращает путь с расширением .png
        else:  # pdf
            # 1. Генерируем SVG
            writer = SVGWriter()
            writer.set_options({
                'module_width': self.module_width.get(),
                'module_height': self.module_height.get(),
                'font_size': self.font_size.get(),
                'text_distance': self.text_distance.get(),
                'quiet_zone': self.quiet_zone.get(),
                'background': self.bg_color.get(),
                'foreground': self.fg_color.get(),
            })
            ean = EAN13(code, writer=writer)
            svg_path = ean.save(base_name + "_temp")  # сохранит как .svg
            # 2. Конвертируем SVG в PDF с помощью svglib
            pdf_path = base_name + ".pdf"
            try:
                drawing = svg2rlg(svg_path)
                renderPDF.drawToFile(drawing, pdf_path)
                os.remove(svg_path)  # удаляем временный SVG
                return pdf_path
            except Exception as e:
                # Если не удалось, удаляем временный SVG и поднимаем ошибку
                if os.path.exists(svg_path):
                    os.remove(svg_path)
                raise Exception(f"Не удалось конвертировать SVG в PDF: {e}")

    def preview_first(self):
        codes = self.get_codes()
        if not codes:
            messagebox.showinfo("Информация", "Нет валидных кодов для предпросмотра.")
            return
        code = codes[0]
        fmt = self.output_format.get()
        temp_dir = tempfile.gettempdir()
        try:
            file_path = self.generate_one(code, temp_dir, fmt)
            # Переименовываем для удобства
            preview_name = os.path.join(temp_dir, "preview" + os.path.splitext(file_path)[1])
            os.rename(file_path, preview_name)
            self.open_file(preview_name)
            self.status_label.config(text=f"Предпросмотр создан: {os.path.basename(preview_name)}", foreground="green")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать предпросмотр:\n{e}")

    def open_file(self, path):
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])

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

# ========== Запуск ==========
if __name__ == "__main__":
    root = tk.Tk()
    app = BarcodeApp(root)
    root.mainloop()