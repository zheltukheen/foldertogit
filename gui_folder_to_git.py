#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import logging
import threading
import os
import sys
import traceback

# Настройка отладочного логирования в файл
logging.basicConfig(
    filename="gui_debug.log",
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Попытка импорта из folder_to_git
try:
    from folder_to_git import migrate_folders_to_git, find_versioned_folders
    logging.debug("Успешно импортированы функции из folder_to_git")
except Exception as e:
    logging.error(f"Ошибка импорта из folder_to_git: {e}")
    traceback.print_exc(file=open("gui_debug.log", "a"))
    
    # Создаем заглушки для функций, чтобы GUI мог запуститься даже без основного модуля
    def find_versioned_folders(source_dir, pattern, extract_pattern, verbose=False):
        logging.warning("Используется заглушка для find_versioned_folders")
        return []
        
    def migrate_folders_to_git(*args, **kwargs):
        logging.warning("Используется заглушка для migrate_folders_to_git")
        return False

# Проверка наличия tkinter
try:
    root_test = tk.Tk()
    root_test.destroy()
    logging.debug("Tkinter проверка успешна")
except Exception as e:
    logging.error(f"Проблема с Tkinter: {e}")
    print(f"ОШИБКА: Не удалось инициализировать Tkinter: {e}")
    sys.exit(1)

# Создаем класс для подсказок (tooltips)
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Создаем окно подсказки
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(self.tooltip, text=self.text, justify='left',
                          background="#ffffe0", relief="solid", borderwidth=1,
                          padding=(5, 5))
        label.pack(ipadx=1)
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

# Класс для создания текстовых полей с плейсхолдерами
class PlaceholderEntry(ttk.Entry):
    def __init__(self, master=None, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        
        self.placeholder = placeholder
        self.placeholder_color = 'grey'
        self.default_fg_color = self['foreground']
        
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        
        self._focus_out()
    
    def _focus_in(self, event):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.config(foreground=self.default_fg_color)
    
    def _focus_out(self, event=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self.config(foreground=self.placeholder_color)
    
    def get_text(self):
        """Получить текст без плейсхолдера"""
        if self.get() == self.placeholder:
            return ""
        return self.get()

class FolderToGitGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Folder to Git Converter")
        self.root.geometry("900x750")
        self.root.minsize(800, 600)  # Минимальный размер окна
        
        # Настройка возможности изменения размера окна
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        
        # Настройка стилей и темы
        self.setup_styles()
        
        # Создаем канвас с прокруткой
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        
        # Создание основного контейнера
        main_frame = ttk.Frame(canvas, padding="20")
        
        # Настройка прокрутки
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Размещаем элементы
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        canvas.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Создаем окно в канвасе для основного фрейма
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Настраиваем изменение размера канваса
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def configure_canvas_window(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        main_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_window)
        
        main_frame.columnconfigure(1, weight=1)  # Разрешаем второму столбцу растягиваться
        main_frame.rowconfigure(8, weight=1)  # Разрешаем строке с логом растягиваться
        
        # Заголовок
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=3, pady=15, sticky=(tk.W, tk.E))
        
        title = ttk.Label(title_frame, text="Конвертер папок в Git-репозиторий", style="Title.TLabel")
        title.pack(side=tk.LEFT, padx=5)
        
        subtitle = ttk.Label(title_frame, text="Преобразование истории версий в Git-коммиты", 
                             style="Subtitle.TLabel")
        subtitle.pack(side=tk.LEFT, padx=20)
        
        # Создаем рамку для полей ввода
        input_frame = ttk.LabelFrame(main_frame, text="Параметры конвертации", padding="10")
        input_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        input_frame.columnconfigure(1, weight=1)
        
        # Источник
        ttk.Label(input_frame, text="Исходная директория:").grid(row=0, column=0, sticky=tk.W, pady=8)
        self.source_var = tk.StringVar()
        source_entry = PlaceholderEntry(input_frame, textvariable=self.source_var, width=50,
                                        placeholder="Например: ./versions или /путь/к/папкам/с/версиями")
        source_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        source_button = ttk.Button(input_frame, text="Обзор...", command=self.browse_source, style="Accent.TButton")
        source_button.grid(row=0, column=2, padx=5)
        ToolTip(source_entry, "Укажите директорию, содержащую папки с разными версиями проекта")
        
        # Целевой репозиторий
        ttk.Label(input_frame, text="Целевой репозиторий:").grid(row=1, column=0, sticky=tk.W, pady=8)
        self.target_var = tk.StringVar()
        target_entry = PlaceholderEntry(input_frame, textvariable=self.target_var, width=50, 
                                        placeholder="Например: ./git_repo или /путь/к/репозиторию")
        target_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        target_button = ttk.Button(input_frame, text="Обзор...", command=self.browse_target, style="Accent.TButton")
        target_button.grid(row=1, column=2, padx=5)
        ToolTip(target_entry, "Укажите директорию, в которой будет создан Git-репозиторий")
        
        # Шаблон поиска
        ttk.Label(input_frame, text="Шаблон поиска:").grid(row=2, column=0, sticky=tk.W, pady=8)
        self.pattern_var = tk.StringVar(value="*")
        pattern_entry = PlaceholderEntry(input_frame, textvariable=self.pattern_var, 
                                        placeholder="Например: version_* или project_v*")
        pattern_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        ToolTip(pattern_entry, "Шаблон glob для поиска папок с версиями. Например: version_* или project_v*")
        
        # Шаблон извлечения версии
        ttk.Label(input_frame, text="Шаблон версии:").grid(row=3, column=0, sticky=tk.W, pady=8)
        self.extract_pattern_var = tk.StringVar(value="[0-9]+(\\.[0-9]+)?")
        extract_entry = PlaceholderEntry(input_frame, textvariable=self.extract_pattern_var, 
                                        placeholder="Например: [0-9]+ или v([0-9]+)")
        extract_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        ToolTip(extract_entry, "Регулярное выражение для извлечения номера версии из имени папки")
        
        # Автор
        ttk.Label(input_frame, text="Имя автора:").grid(row=4, column=0, sticky=tk.W, pady=8)
        self.author_var = tk.StringVar(value="Developer")
        author_entry = PlaceholderEntry(input_frame, textvariable=self.author_var, 
                                       placeholder="Например: Иван Иванов")
        author_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        ToolTip(author_entry, "Имя автора, которое будет указано в коммитах")
        
        # Email
        ttk.Label(input_frame, text="Email автора:").grid(row=5, column=0, sticky=tk.W, pady=8)
        self.email_var = tk.StringVar(value="dev@example.com")
        email_entry = PlaceholderEntry(input_frame, textvariable=self.email_var, 
                                      placeholder="Например: ivan@example.com")
        email_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=8, padx=5)
        ToolTip(email_entry, "Email автора, который будет указан в коммитах")
        
        # Дополнительные опции
        options_frame = ttk.LabelFrame(main_frame, text="Дополнительные опции", padding="10")
        options_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(3, weight=1)
        
        self.dry_run_var = tk.BooleanVar()
        dry_run_check = ttk.Checkbutton(options_frame, text="Тестовый режим", variable=self.dry_run_var)
        dry_run_check.grid(row=0, column=0, padx=8, pady=5, sticky=tk.W)
        ToolTip(dry_run_check, "Выполнить поиск папок без создания Git-репозитория")
        
        self.verbose_var = tk.BooleanVar()
        verbose_check = ttk.Checkbutton(options_frame, text="Подробный вывод", variable=self.verbose_var)
        verbose_check.grid(row=0, column=1, padx=8, pady=5, sticky=tk.W)
        ToolTip(verbose_check, "Выводить подробную информацию о процессе выполнения")
        
        self.append_var = tk.BooleanVar()
        append_check = ttk.Checkbutton(options_frame, text="Добавить к существующему", variable=self.append_var)
        append_check.grid(row=0, column=2, padx=8, pady=5, sticky=tk.W)
        ToolTip(append_check, "Добавить новые версии в существующий репозиторий")
        
        # Лог операций
        log_frame = ttk.LabelFrame(main_frame, text="Лог операций", padding="10")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        
        # Создаем текстовое поле с рамкой и стилизацией
        self.log_text = tk.Text(log_frame, height=12, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.log_text.tag_configure("info", foreground="blue")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("warning", foreground="orange")
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        # Кнопки управления
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=3, pady=15)  # Уменьшаем отступ
        
        self.start_button = ttk.Button(buttons_frame, text="Начать конвертацию", 
                                      command=self.start_conversion, style="Action.TButton")
        self.start_button.grid(row=0, column=0, padx=10)
        
        clear_button = ttk.Button(buttons_frame, text="Очистить лог", 
                                 command=self.clear_log, style="Secondary.TButton")
        clear_button.grid(row=0, column=1, padx=10)
        
        exit_button = ttk.Button(buttons_frame, text="Выход", 
                                command=root.quit, style="Secondary.TButton")
        exit_button.grid(row=0, column=2, padx=10)
        
        # Настройка прокрутки для macOS
        def on_mousewheel(event):
            # Определяем направление прокрутки
            if event.state == 0:  # без модификаторов
                if event.delta > 0:
                    canvas.yview_scroll(-1, "units")
                else:
                    canvas.yview_scroll(1, "units")
            
            # Для тачпада macOS (с учетом инерции)
            elif event.state == 8:  # Command/Meta
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Привязываем события прокрутки
        if sys.platform == "darwin":  # macOS
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        else:  # Windows/Linux
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        
        # Настройка логирования в GUI (перемещено в конец)
        self.setup_logging()
    
    def setup_styles(self):
        """Настройка стилей для виджетов"""
        self.style = ttk.Style()
        
        # Настройка стилей без пользовательских цветов
        self.style.configure("TLabelframe.Label", font=("", 10, "bold"))
        
        # Стиль заголовка
        self.style.configure("Title.TLabel", font=("", 18, "bold"))
        self.style.configure("Subtitle.TLabel", font=("", 10))
        
        # Стиль кнопок
        self.style.configure("TButton", font=("", 10))
        self.style.configure("Action.TButton", font=("", 11, "bold"), padding=5)
        self.style.configure("Secondary.TButton", font=("", 10))
    
    def setup_logging(self):
        """Настройка логирования в GUI"""
        class TextHandler(logging.Handler):
            def __init__(self, text_widget, gui):
                super().__init__()
                self.text_widget = text_widget
                self.gui = gui
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    # Определяем тег на основе уровня сообщения
                    tag = "info"
                    if record.levelno >= logging.ERROR:
                        tag = "error"
                    elif record.levelno >= logging.WARNING:
                        tag = "warning"
                    elif "успе" in msg.lower() or "готов" in msg.lower():
                        tag = "success"
                    
                    self.text_widget.insert(tk.END, msg + '\n', tag)
                    self.text_widget.see(tk.END)
                
                self.text_widget.after(0, append)
        
        # Настройка обработчика для вывода в текстовое поле
        handler = TextHandler(self.log_text, self)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Добавляем приветственное сообщение
        logging.info("Добро пожаловать в Folder to Git Converter!")
        logging.info("Заполните необходимые поля и нажмите 'Начать конвертацию'")
    
    def browse_source(self):
        """Выбор исходной директории"""
        directory = filedialog.askdirectory(title="Выберите исходную директорию")
        if directory:
            self.source_var.set(directory)
            logging.info(f"Выбрана исходная директория: {directory}")
    
    def browse_target(self):
        """Выбор целевой директории"""
        directory = filedialog.askdirectory(title="Выберите целевую директорию")
        if directory:
            self.target_var.set(directory)
            logging.info(f"Выбрана целевая директория: {directory}")
    
    def clear_log(self):
        """Очистка лога"""
        self.log_text.delete(1.0, tk.END)
        logging.info("Лог очищен")
    
    def validate_inputs(self):
        """Проверка введенных данных"""
        if not self.source_var.get() or self.source_var.get().startswith("Например:"):
            messagebox.showerror("Ошибка", "Укажите исходную директорию")
            return False
        
        if not self.target_var.get() or self.target_var.get().startswith("Например:"):
            messagebox.showerror("Ошибка", "Укажите целевую директорию")
            return False
        
        if not os.path.exists(self.source_var.get()):
            messagebox.showerror("Ошибка", "Исходная директория не существует")
            return False
        
        return True
    
    def start_conversion(self):
        """Запуск процесса конвертации"""
        if not self.validate_inputs():
            return
        
        # Изменяем текст кнопки и делаем её неактивной
        self.start_button.configure(text="Выполняется...", state="disabled")
        
        # Запускаем конвертацию в отдельном потоке
        thread = threading.Thread(target=self.run_conversion)
        thread.daemon = True
        thread.start()
    
    def run_conversion(self):
        """Выполнение конвертации"""
        try:
            source_dir = self.source_var.get()
            target_dir = self.target_var.get()
            pattern = self.pattern_var.get()
            extract_pattern = self.extract_pattern_var.get()
            
            # Проверяем, если поля содержат плейсхолдеры
            if pattern.startswith("Например:"):
                pattern = "*"  # Используем значение по умолчанию
            
            if extract_pattern.startswith("Например:"):
                extract_pattern = "[0-9]+(\\.[0-9]+)?"  # Используем значение по умолчанию
            
            logging.info("Начинаем поиск папок с версиями...")
            folders_info = find_versioned_folders(
                source_dir,
                pattern,
                extract_pattern,
                self.verbose_var.get()
            )
            
            if not folders_info:
                logging.error("Не найдены папки с версиями проекта")
                messagebox.showerror("Ошибка", "Не найдены папки с версиями проекта")
                return
            
            if not self.dry_run_var.get():
                logging.info("Начинаем миграцию в Git...")
                success = migrate_folders_to_git(
                    source_dir,
                    target_dir,
                    folders_info,
                    self.dry_run_var.get(),
                    self.author_var.get(),
                    self.email_var.get(),
                    None,  # message template
                    self.append_var.get()
                )
                
                if success:
                    logging.info(f"Git-репозиторий успешно создан в: {target_dir}")
                    messagebox.showinfo("Успех", f"Git-репозиторий успешно создан в:\n{target_dir}")
                else:
                    logging.error("Произошли ошибки при создании репозитория")
                    messagebox.showerror("Ошибка", "Произошли ошибки при создании репозитория")
            else:
                logging.info("Тестовый режим завершен")
        
        except Exception as e:
            logging.error(f"Ошибка: {str(e)}")
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}")
        
        finally:
            # Восстанавливаем состояние кнопки
            def reset_button():
                self.start_button.configure(text="Начать конвертацию", state="normal")
            
            self.root.after(0, reset_button)

def main():
    root = tk.Tk()
    app = FolderToGitGUI(root)
    
    # Настройка иконки (если доступна)
    try:
        # Можно добавить иконку, если она есть
        # root.iconbitmap("icon.ico") 
        pass
    except:
        pass
    
    # Настройка корневого окна для масштабирования
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    
    root.mainloop()

if __name__ == "__main__":
    main() 