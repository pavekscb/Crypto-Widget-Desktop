import tkinter as tk
from tkinter import messagebox, ttk
import requests
import json
import os
import webbrowser
import locale
import sys
import threading
from PIL import Image, ImageDraw 
import pystray 
import time 

# Модуль для работы с реестром Windows (для автозапуска)
try:
    import winreg
except ImportError:
    winreg = None 

# Установка локали для форматирования чисел 
try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C')
    except locale.Error:
        pass


# --- Константы ---
CONFIG_FILE = 'config.json'
API_URL = "https://api.coingecko.com/api/v3/simple/price"
REFRESH_RATE_MS = 60000 # Обновление раз в минуту
COINGECKO_HOME_LINK = "https://www.coingecko.com/ru" 
HISTORY_SIZE = 5 # Размер истории трендов (5x)
APP_NAME = "CryptoWidgetCoinGecko" # Имя приложения для реестра
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


# Сообщения для уведомлений о трендах в зависимости от длины серии (>= 2)
TREND_MESSAGES = {
    2: {
        "BULLISH": "ПЕРВЫЙ ПРИЗНАК: Возможен восходящий импульс.",
        "BEARISH": "ПЕРВЫЙ ПРИЗНАК: Возможен нисходящий импульс."
    },
    3: {
        "BULLISH": "УСИЛЕНИЕ: Подтверждается краткосрочный восходящий тренд.",
        "BEARISH": "УСИЛЕНИЕ: Подтверждается краткосрочный нисходящий тренд."
    },
    4: {
        "BULLISH": "СИЛЬНЫЙ СИГНАЛ: Высокая вероятность продолжения роста.",
        "BEARISH": "СИЛЬНЫЙ СИГНАЛ: Высокая вероятность продолжения падения."
    },
    5: {
        "BULLISH": "МАКСИМАЛЬНЫЙ ТРЕНД: Устойчивый, сильный бычий сигнал.",
        "BEARISH": "МАКСИМАЛЬНЫЙ ТРЕНД: Устойчивый, сильный медвежий сигнал."
    }
}

# Ключи для сортировки
SORT_KEYS = {
    'name': (0, 'Монета:'),
    'amount': (1, 'Количество:'),
    'price': (2, 'Курс:')
}

# --- Цвета для тем ---
THEMES = {
    'light': {
        'bg': 'SystemButtonFace',
        'fg': 'black',
        'header_fg': 'darkblue',
        'link_fg': 'blue',
        'link_hover_fg': 'red',
        'price_fg': 'darkgreen',
        'amount_fg': 'darkmagenta',
        'total_value_fg': 'darkblue',
        'separator_bg': 'gray',
        'settings_fg': 'black',
        'select_color': 'white' # Цвет галочки/переключателя
    },
    'dark': {
        'bg': '#2e2e2e',
        'fg': '#e0e0e0',
        'header_fg': '#4ec9b0',
        'link_fg': '#569cd6',
        'link_hover_fg': '#c586c0',
        'price_fg': '#9cdcfe',
        'amount_fg': '#c586c0',
        'total_value_fg': '#ffd700',
        'separator_bg': '#444444',
        'settings_fg': '#e0e0e0',
        'select_color': '#4ec9b0' # Светло-бирюзовый для контраста в чекбоксах
    }
}


# --- Создание Иконки (для трея) ---
def create_icon_image(size=64):
    """Создает простое изображение голубого квадрата для иконки трея."""
    img = Image.new('RGB', (size, size), color='white')
    d = ImageDraw.Draw(img)
    # Рисуем голубой квадрат
    d.rectangle([size*0.1, size*0.1, size*0.9, size*0.9], fill='#00BFFF', outline='#0080FF')
    return img
# ------------------------


# --- Функции реестра (Только для Windows) ---
def get_app_path():
    """
    Определяет команду для запуска приложения с флагом -autostart.
    """
    if getattr(sys, 'frozen', False):
         # Если приложение скомпилировано (PyInstaller)
        app_path = os.path.abspath(sys.executable)
        command = f'"{app_path}" -autostart'
    else:
         # Если запускается как скрипт Python: python.exe script.py -autostart
        python_path = sys.executable.replace('\\', '/')
        script_path = os.path.abspath(sys.argv[0]).replace('\\', '/')
        command = f'"{python_path}" "{script_path}" -autostart' 
        
    return command

def set_startup(enable=True):
    """
    Устанавливает или удаляет автозапуск приложения в реестре Windows.
    """
    if winreg is None:
        print("Модуль winreg недоступен (не Windows OS).")
        return False
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            command = get_app_path()
            print(f"Команда для реестра: {command}")

            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            print(f"Автозапуск '{APP_NAME}' добавлен в реестре.")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                print(f"Автозапуск '{APP_NAME}' удален из реестра.")
            except FileNotFoundError:
                pass 
                
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Ошибка при работе с реестром: {e}")
        messagebox.showerror("Ошибка Реестра", f"Не удалось изменить настройку автозапуска.\n{e}")
        return False

def check_startup():
    """Проверяет наличие приложения в реестре автозапуска и возвращает True/False."""
    if winreg is None:
        return False
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


# --- Управление Конфигурацией ---
def load_config():
    """Загружает конфигурацию из config.json или создает дефолтную."""
    default_config = {
        "base_currency": "usd", 
        "coins": {
            "bitcoin": {"name": "BTC", "amount": 0.0}, 
            "ethereum": {"name": "ETH", "amount": 0.0}
        },
        "font_size": 10,
        "window_x": None, 
        "window_y": None,
        "opacity": 0.95,
        "autostart_enabled": True,
        "hide_on_close": True, 
        "theme": "light",
        "trend_notifications_enabled": True, # Оставлено для совместимости при миграции
        "notification_duration_sec": 10,  # НОВОЕ: Длительность уведомления в секундах
        "notification_mode": "always"     # НОВОЕ: "always", "tray_only", "disabled"
    }
    
    if not os.path.exists(CONFIG_FILE):
        return default_config
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # Обновление старого формата монет на новый
            if 'coins' in config:
                new_coins = {}
                for api_id, data in config['coins'].items():
                    if isinstance(data, str):
                        new_coins[api_id] = {"name": data, "amount": 0.0}
                    elif isinstance(data, dict):
                        # Игнорируем специфические поля DEX, если они есть
                        coin_data = {
                            "name": data.get("name", api_id.upper()),
                            "amount": data.get("amount", 0.0)
                        }
                        new_coins[api_id] = coin_data
                    
                config['coins'] = new_coins
            
            for key, default_val in default_config.items():
                if key not in config:
                    config[key] = default_val
                    
            # Миграция: если старая настройка отключена, устанавливаем режим "disabled"
            if not config['trend_notifications_enabled'] and config['notification_mode'] == default_config['notification_mode']:
                 config['notification_mode'] = 'disabled'
            # Удаляем старую настройку
            if 'trend_notifications_enabled' in config:
                del config['trend_notifications_enabled']
                
            return config
            
    except Exception:
        return default_config

def save_config(config):
    """Сохраняет текущую конфигурацию в config.json."""
    
    suppress_error = '-autostart' in sys.argv 
    
    # Удаляем старую настройку, если она еще осталась
    if 'trend_notifications_enabled' in config:
        del config['trend_notifications_enabled']
        
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except PermissionError as e:
        print(f"Ошибка прав доступа при сохранении конфига: {e}") 
        
        if not suppress_error:
            messagebox.showerror(
                "Ошибка сохранения", 
                f"Не удалось сохранить файл настроек '{CONFIG_FILE}' из-за ошибки прав доступа.\n"
                f"Ошибка: {e}"
            )
    except Exception as e:
        print(f"Неизвестная ошибка при сохранении конфига: {e}")


# --- Получение данных (API) ---
def get_crypto_prices(coin_ids, currency):
    """Получает курсы криптовалют с CoinGecko API (только CoinGecko)."""
    if not coin_ids:
        return {}
    
    ids_str = ",".join(coin_ids)
    
    try:
        response = requests.get(
            API_URL, 
            params={'ids': ids_str, 'vs_currencies': currency}, 
            timeout=10
        )
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
             print("Ошибка API: 429 Too Many Requests. Проверьте интервал обновлений (должен быть >= 60 секунд).")
        else:
            print(f"Ошибка HTTP: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети/API: {e}")
        return {}
        
# --- Всплывающее Окно Уведомлений ---
class NotificationWindow(tk.Toplevel):
    def __init__(self, master, active_signals, duration_sec): 
        super().__init__(master)
        
        # self.overrideredirect(True) # Убираем рамку окна
        self.attributes('-topmost', True) # Всегда сверху
        
        # Выбираем цвета и фон
        bg_color = '#000000' # Темный фон было #3C3C3C
        fg_color = '#FFFFFF' # Белый текст
        header_color = '#4EC9B0' # Бирюзовый для заголовка
        
        self.config(bg=bg_color)
        
        self.duration_sec = duration_sec # Длительность из настроек
        self.time_left = duration_sec 
        self.timer_id = None # Для after_cancel
        
        # Общий заголовок
        tk.Label(
            self, 
            text="🚨 Обнаружены тренды! 🚨", 
            font=('Arial', 14, 'bold'), 
            fg=header_color, 
            bg=bg_color
        ).pack(padx=15, pady=(10, 5), fill='x')

        # Фрейм для скроллинга, если сигналов много
        scrollable_frame = tk.Frame(self, bg=bg_color)
        scrollable_frame.pack(fill='both', expand=True, padx=15, pady=(0, 5))
        
        # Использование Canvas и Scrollbar для списка сигналов
        canvas = tk.Canvas(scrollable_frame, bg=bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(scrollable_frame, orient="vertical", command=canvas.yview)
        
        self.signals_frame = tk.Frame(canvas, bg=bg_color)
        
        self.signals_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.signals_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Отрисовка каждого сигнала
        for signal in active_signals:
            coin_name = signal['coin_name']
            trend_type = signal['trend_type']
            series_length = signal['series_length']
            change_percent = signal['change_percent']
            
            trend_color = 'green' if trend_type == "BULLISH" else 'red'  
            trend_icon = '▲' if trend_type == "BULLISH" else '▼'

            # Разделитель между монетами
            if signal != active_signals[0]:
                 tk.Frame(self.signals_frame, height=1, bg='#555555').pack(fill='x', pady=5)
            
            # Фрейм для одной монеты
            coin_frame = tk.Frame(self.signals_frame, bg=bg_color)
            coin_frame.pack(fill='x')
            
            # Повторение иконки (стрелочки) в количестве series_length
            importance_arrows = trend_icon * series_length 
            title_prefix = "📈 БЫЧИЙ" if trend_type == "BULLISH" else "📉 МЕДВЕЖИЙ"
            
            # Заголовок монеты (Стрелочки + Имя + Тип + Серия)
            tk.Label(
                coin_frame, 
                text=f"{importance_arrows} {coin_name} ({title_prefix}) ({series_length}/{HISTORY_SIZE})", 
                font=('Arial', 10, 'bold'), 
                fg=trend_color, 
                bg=bg_color
            ).pack(side=tk.LEFT, fill='x')
            
            # Процент изменения
            percent_str = f"+{change_percent:.2f}%" if change_percent > 0 else f"{change_percent:.2f}%"
            
            tk.Label(
                coin_frame, 
                text=f"{percent_str}", 
                font=('Arial', 10, 'bold'), 
                fg=trend_color, 
                bg=bg_color
            ).pack(side=tk.RIGHT)
            
            # Основное сообщение
            message = TREND_MESSAGES[series_length][trend_type]
            tk.Label(
                self.signals_frame, 
                text=message, 
                font=('Arial', 9), 
                fg=fg_color, 
                bg=bg_color,
                justify=tk.LEFT,
                wraplength=600 
            ).pack(fill='x', pady=(0, 5))
            
        # Фрейм для нижней части с кнопкой и таймером
        bottom_buttons_frame = tk.Frame(self, bg=bg_color)
        bottom_buttons_frame.pack(fill='x', padx=15, pady=(5, 10))

        # Кнопка закрытия
        tk.Button(
            bottom_buttons_frame, 
            text="Закрыть (ОК)", 
            command=self.close_window,
            font=('Arial', 9),
            bg='#444444', 
            fg=fg_color,
            bd=0,
            relief=tk.FLAT
        ).pack(side=tk.LEFT)
        
        # Обратный отсчет
        self.countdown_label = tk.Label(
            bottom_buttons_frame,
            text=f"Закрытие через {self.time_left} сек...",
            font=('Arial', 9),
            fg='#FFD700', # Желтый цвет
            bg=bg_color
        )
        self.countdown_label.pack(side=tk.RIGHT)


        # Центрирование окна (нужно обновить геометрию после создания всех виджетов)
        self.update_idletasks()
        self.center_window(min_width=400, max_width=600, max_height=600)
        
        # Автоматическое закрытие и отсчет
        self.timer_id = self.after(1000, self.update_countdown)
        
    def update_countdown(self):
        """Обновляет таймер обратного отсчета."""
        self.time_left -= 1
        
        if self.time_left <= 0:
            self.close_window()
            return

        self.countdown_label.config(text=f"Закрытие через {self.time_left} сек...")
        
        # Запускаем следующий отсчет
        self.timer_id = self.after(1000, self.update_countdown)
        
    def center_window(self, min_width=400, max_width=600, max_height=600):
        """Центрирует окно уведомления на экране с учетом динамического размера и ограничений."""
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        
        # Применяем ограничения размера
        width = max(min_width, min(width, max_width))
        height = min(height, max_height)
        
        # Принудительно устанавливаем размер
        self.geometry(f'{width}x{height}')
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        self.geometry(f'+{x}+{y}')
        
    def close_window(self):
        """Закрывает окно уведомления и отменяет таймер."""
        if hasattr(self, 'timer_id') and self.timer_id:
            self.after_cancel(self.timer_id)
        self.destroy()

# --- GUI Виджет (Основное окно) ---
class CryptoWidget(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        
        self._x = 0
        self._y = 0
        
        self.prev_prices = {} 
        self.current_prices = {} 
        
        # trend_history: {api_id: [('▲', 'green'), ('▬', 'gray'), ...]}
        self.trend_history = {api_id: [] for api_id in self.config['coins']}
        
        self.progress_value = 0
        self.max_progress = REFRESH_RATE_MS // 1000 
        
        # --- Трей: Инициализация ---
        self.tray_icon = None
        self.is_hidden = False # Флаг, скрыт ли виджет
        self.tray_thread = None # Поток для pystray
        # ---------------------------

        # --- СОРТИРОВКА: Инициализация ---
        self.initial_coin_order = list(self.config['coins'].keys())
        self.coin_order_list = self.initial_coin_order[:]
        self.sort_state = (None, None) 
        self.sort_button_labels = {} 
        # ---------------------------------
        
        self.title("Курсы крипто монет CoinGecko - Виджет CRYPTO") 
        
        self.attributes('-topmost', True) 
        self.resizable(False, False)
        # Настройка фона будет выполнена в apply_theme
        
        self.attributes('-alpha', self.config.get('opacity', 0.95)) 
        
        self.coins_frame = tk.Frame(self)
        self.coins_frame.pack(padx=10, pady=(5, 0), fill='both', expand=True) 
        
        self.portfolio_frame = tk.Frame(self)
        self.portfolio_frame.pack(side=tk.BOTTOM, fill='x', padx=10, pady=(0, 5)) 
        
        self.bottom_frame = tk.Frame(self) # Сделали self.bottom_frame для доступа к теме
        self.bottom_frame.pack(side=tk.BOTTOM, fill='x', padx=5, pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(
            self.bottom_frame, 
            orient='horizontal', 
            length=200, 
            mode='determinate',
            maximum=self.max_progress,
            value=self.progress_value
        )
        self.progress_bar.pack(side=tk.LEFT, fill='x', expand=True, padx=(5, 10))
        
        self.settings_button = tk.Button(
            self.bottom_frame, text="⚙", command=self.open_settings, 
            font=('Arial', 10, 'bold'),
        )
        self.settings_button.pack(side=tk.RIGHT) 

        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self.settings_button.bind("<Button-1>", self.open_settings_and_break)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.protocol("WM_ICONIFY", self.on_minimize) 
        
        # Первое обновление
        self.update_widget()
        self.load_window_position()
        self.update_progress()
        
        self.apply_theme() # ПРИМЕНЕНИЕ ТЕМЫ ПОСЛЕ СОЗДАНИЯ ВСЕХ ВИДЖЕТОВ

    # --- Методы Темы ---
    def apply_theme(self):
        """Применяет текущую тему ко всем виджетам."""
        theme_name = self.config.get('theme', 'light')
        colors = THEMES.get(theme_name, THEMES['light'])
        
        # 1. Основное окно
        self.configure(bg=colors['bg'])
        
        # 2. Перекрашивание виджетов
        self.recolorize_widgets(self, colors)
        
        # Обновление прогресс-бар (поскольку это ttk, фон не меняется, но это не критично)
        self.progress_bar.configure(style=f'TProgressbar')
        
    def recolorize_widgets(self, parent, colors):
        """Рекурсивно меняет цвета у всех виджетов внутри фрейма/окна."""
        for widget in parent.winfo_children():
            try:
                # Метки и кнопки: меняем фон
                if isinstance(widget, (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton)):
                    # Игнорируем специфичные цвета для трендов, изменений и т.д.
                    current_fg = widget.cget('fg')
                    
                    if current_fg in ['gray', 'green', 'red']:
                         # Это специфичная метка с данными, меняем только фон
                         widget.configure(bg=colors['bg'])
                    elif widget.cget('text').endswith(':') and widget.master in [self.coins_frame, self.portfolio_frame]: 
                         # Заголовки (напр., "Общий Портфель:") и заголовки таблицы
                         widget.configure(bg=colors['bg'], fg=colors['header_fg'])
                    elif current_fg in ['darkmagenta', 'darkgreen', 'darkblue', '#9cdcfe', '#c586c0', '#ffd700']:
                         # Это специфичная метка с данными, которые будут перерисованы в update_widget
                         widget.configure(bg=colors['bg'])
                    elif widget.cget('text') == '⚙':
                         widget.configure(bg=colors['bg'], fg=colors['fg'])
                    else:
                         # Обычный текст
                         widget.configure(bg=colors['bg'], fg=colors['fg'])
                    
                    if isinstance(widget, tk.Button):
                        widget.configure(bg=colors['bg'])

                # Фреймы
                elif isinstance(widget, (tk.Frame, ttk.Frame)):
                    widget.configure(bg=colors['bg'])
                    self.recolorize_widgets(widget, colors) # Рекурсия
                    
            except tk.TclError:
                # Некоторые виджеты не имеют bg/fg
                pass
                
        # Специальный случай для разделителей
        for sep in [w for w in parent.winfo_children() if isinstance(w, tk.Frame) and w.cget('height') == 1]:
            sep.configure(bg=colors['separator_bg'])

    # --- Методы трея ---
    
    def on_minimize(self):
        """
        Обработчик сворачивания (нажатие на '_'). 
        Возвращаем 'ignore', чтобы предотвратить стандартное сворачивание Windows, 
        и отправляем окно в трей.
        """
        self.hide_to_tray()
        return "ignore" 
    
    def setup_tray_icon(self):
        """Создает объект иконки трея и меню."""
        
        def show_window(icon, item):
            """Обработчик для показа окна (запускается в потоке трея)."""
            icon.stop()
            # Используем after для выполнения команды в основном потоке Tkinter
            self.after(0, self.deiconify) 
            self.is_hidden = False
            
        def open_settings_from_tray(icon, item):
             """Обработчик для открытия настроек."""
             self.after(0, self.open_settings)
            
        def quit_window(icon, item):
            """Обработчик для выхода из приложения."""
            icon.stop()
            self.after(0, self.destroy) # Выход из Tkinter в основном потоке
            
        # Создание иконки и меню
        icon_image = create_icon_image()
        
        menu = (
            pystray.MenuItem('Показать виджет', show_window),
            pystray.MenuItem('Настройки', open_settings_from_tray),
            pystray.MenuItem('Выход', quit_window)
        )
        
        self.tray_icon = pystray.Icon("crypto_widget", icon_image, "Крипто Виджет СRYPTO", menu)
        
        # Устанавливаем обработчик клика по иконке (show_window срабатывает на ЛКМ)
        self.tray_icon.action = show_window 
            
    def hide_to_tray(self):
        """Скрывает окно и отображает иконку в трее."""
        
        # Проверяем, что настройка включена
        if not self.config.get('hide_on_close', False):
            # Если сворачивание в трей отключено, просто сворачиваем окно
            self.iconify() 
            return

        if self.tray_icon is None:
            self.setup_tray_icon()
        
        self.withdraw() # Скрыть окно
        self.is_hidden = True
        
        # Запускаем pystray в отдельном потоке, если он еще не запущен
        if self.tray_thread is None or not self.tray_thread or not self.tray_thread.is_alive():
            def run_tray():
                self.tray_icon.run()

            self.tray_thread = threading.Thread(target=run_tray, daemon=True)
            self.tray_thread.start()
            
    def on_close(self):
        """
        Обработчик закрытия окна (нажатие на 'X').
        Если включено сворачивание в трей, то сворачиваем.
        Иначе - закрываем полностью, завершая поток трея.
        """
        self.save_window_position()
        
        if self.config.get('hide_on_close', False):
            # Если включено сворачивание, то просто вызываем скрытие окна
            self.withdraw()
            self.is_hidden = True
            
            # И запускаем трей, если он еще не запущен
            if self.tray_icon is None or not self.tray_thread or not self.tray_thread.is_alive():
                 self.setup_tray_icon()
                 def run_tray():
                    self.tray_icon.run()
                 self.tray_thread = threading.Thread(target=run_tray, daemon=True)
                 self.tray_thread.start()
        else:
            # Если сворачивание отключено, закрываем приложение и поток трея
            if self.tray_icon:
                self.tray_icon.stop() 
            self.destroy()

    # --- Методы сортировки ---
    def update_sort_button_labels(self):
        """Обновляет иконки на кнопках сортировки в соответствии с self.sort_state."""
        theme_name = self.config.get('theme', 'light')
        colors = THEMES.get(theme_name, THEMES['light'])
        
        column, direction = self.sort_state
        
        for key, button in self.sort_button_labels.items():
            if key == column:
                if direction == 'DESC':
                    button.config(text="▼")
                elif direction == 'ASC':
                    button.config(text="▲")
            else:
                button.config(text="↕")
            
            button.config(bg=colors['bg'], fg=colors['header_fg'])

    def sort_by_column(self, column_key):
        """Реализует тройную логику сортировки: DESC -> ASC -> Initial."""
        current_column, current_direction = self.sort_state

        if column_key != current_column:
            # 1. Сортировка по новому столбцу: Начинаем с DESC
            new_direction = 'DESC'
        elif current_direction == 'DESC':
            # 2. Клик на текущий столбец (DESC): Меняем на ASC
            new_direction = 'ASC'
        else: # current_direction == 'ASC' или None
            # 3. Клик на текущий столбец (ASC) или сброс: Возвращаемся к исходному порядку
            self.coin_order_list = self.initial_coin_order[:]
            self.sort_state = (None, None)
            self.update_widget(recalculate_order=False) # Перерисовываем, но не пересчитываем порядок
            return

        self.sort_state = (column_key, new_direction)
        
        # Определяем функцию-ключ для сортировки
        reverse = (new_direction == 'DESC')
        
        if column_key == 'name':
            # Сортировка по отображаемому имени (строка)
            def sort_key(api_id):
                return self.config['coins'][api_id].get('name', api_id.upper())
        elif column_key == 'amount':
            # Сортировка по количеству (число)
            def sort_key(api_id):
                return self.config['coins'][api_id].get('amount', 0.0)
        elif column_key == 'price':
            # Сортировка по текущему курсу (число)
            def sort_key(api_id):
                # Используем 0.0, если цена еще не загружена или API вернул ошибку
                return self.current_prices.get(api_id, 0.0)

        # Применяем сортировку к списку ключей
        try:
            self.coin_order_list.sort(key=sort_key, reverse=reverse)
            self.update_widget(recalculate_order=False)
        except Exception as e:
            print(f"Ошибка сортировки по {column_key}: {e}")
            messagebox.showerror("Ошибка Сортировки", f"Не удалось отсортировать по полю {column_key}.")

    # --- Остальные методы ---
    def update_progress(self):
        """Обновляет значение прогресс-бара каждую секунду и вызывает обновление данных при завершении."""
        self.progress_value += 1
        if self.progress_value >= self.max_progress:
            # При обновлении данных, всегда возвращаемся к исходному порядку, 
            # но сохраняем текущий режим сортировки для повторного применения
            self.update_widget(recalculate_order=True)
        self.progress_bar['value'] = self.progress_value % self.max_progress 
        self.after(1000, self.update_progress) 

    def open_coin_link(self, api_id):
        url = f"https://www.coingecko.com/coins/{api_id}" 
        webbrowser.open(url)
        
    def open_developer_link(self):
        webbrowser.open("https://github.com/pavekscb/Crypto-Widget-Desktop.git")

    def open_settings_and_break(self, event):
        self.open_settings()
        return "break"

    def save_window_position(self):
        self.update_idletasks()
        x = self.winfo_x()
        y = self.winfo_y()
        self.config['window_x'] = x
        self.config['window_y'] = y
        save_config(self.config)

    def load_window_position(self):
        x = self.config['window_x']
        y = self.config['window_y']
        
        if x is None or y is None:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
        
        self.geometry(f'+{x}+{y}')
        
    def start_move(self, event):
        x_root = event.x_root
        y_root = event.y_root
        self._x = x_root - self.winfo_rootx()
        self._y = y_root - self.winfo_rooty()
        if event.widget != self.settings_button and event.widget.cget("cursor") != "hand2" and event.widget != self.progress_bar:
            return "break"
        
    def do_move(self, event):
        x = self.winfo_x() + event.x_root - self.winfo_rootx() - self._x
        y = self.winfo_y() + event.y_root - self.winfo_rooty() - self._y
        self.geometry(f"+{x}+{y}")
        
    def format_price(self, price, currency):
        if price is None: return "N/A"
        if price < 0.01 and price != 0: 
            price_str = f"{price:.8f}".rstrip('0')
            if price_str.endswith('.'): price_str += '0'
        else:
            # Используем локаль для форматирования с запятыми (например, 1,000.00)
            try:
                price_str = locale.format_string("%.4f", price, grouping=True)
            except Exception:
                price_str = f"{price:,.4f}"
            
        return f"{price_str} {currency.upper()}"
        
    def format_total_value(self, value, currency):
        if value is None: return "N/A"
        try:
            if value >= 1000: 
                value_str = locale.format_string("%.2f", value, grouping=True)
            elif value > 0: 
                value_str = locale.format_string("%.4f", value, grouping=True)
            else: 
                value_str = "0.00"
        except Exception:
            if value >= 1000: value_str = f"{value:,.2f}"
            elif value > 0: value_str = f"{value:.4f}"
            else: value_str = "0.00"
            
        return f"{value_str} {currency.upper()}"
        
    def format_amount(self, amount):
        if amount is None: return "0.00"
        try:
            if amount >= 10:
                 amount_str = locale.format_string("%.8f", amount, grouping=True).rstrip('0').rstrip('.')
                 if '.' not in amount_str and ',' not in amount_str: amount_str = f"{amount:.2f}"
                 if amount_str.endswith('.') or amount_str.endswith(','): amount_str += '00'
                 return amount_str
            elif amount > 0:
                 return locale.format_string("%.8f", amount, grouping=True).rstrip('0')
            else:
                 return "0.00"
        except Exception:
             if amount >= 10:
                 amount_str = f"{amount:,.8f}".rstrip('0').rstrip('.')
                 if '.' not in amount_str and ',' not in amount_str: amount_str = f"{amount:.2f}"
                 if amount_str.endswith('.'): amount_str += '00'
                 return amount_str
             elif amount > 0:
                 return f"{amount:,.8f}".rstrip('0')
             else:
                 return "0.00"
        
    def calculate_change_percent(self, current_price, prev_price):
        if prev_price is None or prev_price == 0: return 0.0, "---", "gray" 
            
        try:
            change = ((current_price - prev_price) / prev_price) * 100
            if change > 0.01:
                color = 'green'
                prefix = '+'
            elif change < -0.01:
                color = 'red'
                prefix = ''
            else:
                color = 'gray'
                prefix = ''
                
            return change, f"({prefix}{change:.2f}%)", color
        except Exception:
            return 0.0, "---", "gray"
            
    def get_forecast_tuple(self, change_percent):
        if change_percent > 0.01: return ("▲", "green")
        elif change_percent < -0.01: return ("▼", "red")
        else: return ("▬", "gray") 

    def show_forecast_explanation(self, event):
        explanation = ("ЛОГИКА ПРОГНОЗА И ИСТОРИИ ТРЕНДОВ:\n\nЭти значки отображают ПРЕДПОЛОЖЕНИЕ о продолжении тренда, "
                       f"основанное на изменении курса за последние {REFRESH_RATE_MS // 1000} секунд (интервал обновления).\n\n"
                       " • ▲ (Зеленый): Цена выросла более чем на 0.01% с последнего обновления.\n • ▼ (Красный): Цена упала более чем на 0.01%.\n"
                       " • ▬ (Серый): Цена осталась стабильной (изменение менее 0.01%).\n\n"
                       "СТОЛБЕЦ ТРЕНДА:\n"
                       f"Визуализация показывает **{HISTORY_SIZE} последних** трендов. Инерция.\n\n"
                       "УВЕДОМЛЕНИЯ О ТРЕНДАХ:\n"
                       "Всплывающее ОКНО появляется, когда 2, 3, 4 или 5 индикаторов подряд одинаковые (по всем монетам в одном сообщении)."
                      )
        self.unbind("<Button-1>")
        messagebox.showinfo("Что такое Тренд?", explanation)
        self.bind("<Button-1>", self.start_move)

    def show_coin_explanation(self, event):
        explanation = ("КАК ДОБАВЛЯТЬ МОНЕТЫ (API ID):\n\n"
                       "Для добавления монеты в Настройках необходимо знать ее Идентификатор API (API ID) на CoinGecko.\n\n"
                       "➡️ ПРИМЕР: TON (The Open Network)\n 1. Идентификатор API: 'the-open-network'\n 2. В поле 'Имя' введите: 'TON'\n\n"
                       "*Если ID монеты не работает, попробуйте найти точный ID через Google, используя фразу 'CoinGecko API ID [Название монеты]'."
                      )
        self.unbind("<Button-1>")
        messagebox.showinfo("Как добавить монету?", explanation)
        self.bind("<Button-1>", self.start_move)

    def show_portfolio_explanation(self, event):
        explanation = ("РАСЧЕТ ПОРТФЕЛЯ:\n\n"
                       "• Количество (Amount): Вводится вами в 'Настройках'.\n"
                       "• Стоимость (Value): Рассчитывается как (Курс * Количество).\n"
                       "• Общий Портфель: Сумма стоимостей всех отслеживаемых монет."
                      )
        self.unbind("<Button-1>")
        messagebox.showinfo("Что такое Портфель?", explanation)
        self.bind("<Button-1>", self.start_move)
        
    
    def show_consolidated_notification(self, active_signals):
        """Создает и отображает ОДНО всплывающее окно уведомления для всех сигналов, учитывая режим."""
        
        if not active_signals:
            return
            
        mode = self.config.get('notification_mode', 'always')
        duration = self.config.get('notification_duration_sec', 10)
        
        if mode == 'disabled':
            return
            
        # Проверяем, нужно ли показывать
        if mode == 'tray_only' and not self.is_hidden:
            return # Окно открыто, а режим "только в трее"

        # Запускаем окно уведомления в основном потоке Tkinter
        NotificationWindow(self, active_signals, duration)


    def update_widget(self, recalculate_order=True):
        """Обновляет курсы и перерисовывает виджет в виде таблички."""
        
        font_size = self.config['font_size']
        coin_ids = list(self.config['coins'].keys())
        currency = self.config['base_currency']
        
        theme_name = self.config.get('theme', 'light')
        colors = THEMES.get(theme_name, THEMES['light'])
        
        active_trend_signals = [] # НОВАЯ ПЕРЕМЕННАЯ ДЛЯ СБОРА СИГНАЛОВ
        
        # 1. Если это первое или полное обновление, обновляем данные и порядок
        if recalculate_order:
            self.progress_value = 0 
            self.progress_bar['value'] = self.progress_value
            self.prev_prices = self.current_prices.copy()
            data = get_crypto_prices(coin_ids, currency)
            self.current_prices.clear()
            self.current_data = data 
            
            self.initial_coin_order = list(self.config['coins'].keys())
            self.coin_order_list = self.initial_coin_order[:]
            
            # Повторное применение сортировки, если она была активна
            if self.sort_state[0] is not None:
                temp_state = self.sort_state 
                self.sort_state = (None, None) 
                self.sort_by_column(temp_state[0])
        else:
            data = self.current_data 

        # 2. Очистка и отрисовка фреймов
        for widget in self.coins_frame.winfo_children(): widget.destroy()
        for widget in self.portfolio_frame.winfo_children(): widget.destroy()
             
        row_num = 0
        total_portfolio_value = 0.0

        # --- Заголовки столбцов с кнопками сортировки ---
        header_font = ('Arial', max(8, font_size - 4), 'bold')
        button_font = ('Arial', max(6, font_size - 6))
        self.sort_button_labels = {} 
        
        # Создание фрейма для заголовка и кнопки
        def create_header_with_sort(col_key, text, col_num, sticky='w'):
            frame = tk.Frame(self.coins_frame, bg=colors['bg'])
            frame.grid(row=row_num, column=col_num, sticky=sticky, padx=(0, 5) if sticky=='w' else (5, 0))
            
            header_label = tk.Label(frame, text=text, font=header_font, bg=colors['bg'], fg=colors['header_fg'], cursor="question_arrow")
            header_label.pack(side=tk.LEFT)
            
            sort_btn = tk.Button(
                frame, 
                text="↕", 
                command=lambda key=col_key: self.sort_by_column(key),
                font=button_font,
                padx=2,
                pady=0,
                cursor="hand2",
                relief=tk.FLAT,
                bd=0,
                bg=colors['bg'],
                fg=colors['header_fg']
            )
            sort_btn.pack(side=tk.LEFT, padx=(2, 0))
            self.sort_button_labels[col_key] = sort_btn
            
            if col_key == 'name':
                header_label.bind("<Button-1>", self.show_coin_explanation)
            elif col_key == 'amount':
                header_label.bind("<Button-1>", self.show_portfolio_explanation)

        create_header_with_sort('name', 'Монета:', 0, sticky='w')
        create_header_with_sort('amount', 'Количество:', 1, sticky='e')
        create_header_with_sort('price', 'Курс:', 2, sticky='e')

        # Остальные заголовки без сортировки
        tk.Label(self.coins_frame, text="Стоимость:", font=header_font, bg=colors['bg'], fg=colors['header_fg']).grid(row=row_num, column=3, sticky='e', padx=(5, 10))
        tk.Label(self.coins_frame, text="Изм. %:", font=header_font, bg=colors['bg'], fg=colors['header_fg']).grid(row=row_num, column=4, sticky='e', padx=(5, 10))
        forecast_header_label = tk.Label(self.coins_frame, text=f"Тренд ({HISTORY_SIZE}x):", font=header_font, bg=colors['bg'], fg=colors['header_fg'], cursor="question_arrow") 
        forecast_header_label.grid(row=row_num, column=5, sticky='e', padx=(5, 0))
        forecast_header_label.bind("<Button-1>", self.show_forecast_explanation)
        
        # Настройка весов столбцов
        self.coins_frame.grid_columnconfigure(0, weight=0)
        self.coins_frame.grid_columnconfigure(1, weight=1)
        self.coins_frame.grid_columnconfigure(2, weight=1)
        self.coins_frame.grid_columnconfigure(3, weight=1)
        self.coins_frame.grid_columnconfigure(4, weight=1)
        self.coins_frame.grid_columnconfigure(5, weight=0)

        row_num += 1
        tk.Frame(self.coins_frame, height=1, bg=colors['separator_bg']).grid(row=row_num, columnspan=6, sticky='ew', pady=(2, 5))
        row_num += 1
        
        self.update_sort_button_labels()
        
        # --- Строки с курсами (Используем self.coin_order_list для порядка) ---
        for api_id in self.coin_order_list:
            coin_data = self.config['coins'].get(api_id, {"name": api_id.upper(), "amount": 0.0})
            
            display_name = coin_data.get('name', api_id.upper())
            amount = coin_data.get('amount', 0.0)
            current_value = 0.0
            
            # Колонка 0: Имя монеты
            name_label = tk.Label(self.coins_frame, text=f"{display_name}:", fg=colors['link_fg'], bg=colors['bg'], font=('Arial', font_size, 'bold'), cursor="hand2")
            name_label.grid(row=row_num, column=0, sticky='w', padx=(0, 5))
            name_label.bind("<Button-1>", lambda e, id=api_id: self.open_coin_link(id))
            name_label.bind("<Enter>", lambda e, l=name_label: l.config(fg=colors['link_hover_fg']))
            name_label.bind("<Leave>", lambda e, l=name_label: l.config(fg=colors['link_fg']))
            
            # Колонка 1: Количество монет (Amount)
            tk.Label(self.coins_frame, text=self.format_amount(amount), fg=colors['amount_fg'], bg=colors['bg'], font=('Arial', font_size)).grid(row=row_num, column=1, sticky='e', padx=(5, 10))


            if api_id in data and currency in data[api_id]:
                price = data[api_id][currency]
                self.current_prices[api_id] = price 
                
                try:
                    current_value = amount * price
                    total_portfolio_value += current_value
                except Exception:
                    pass
                    
                price_str = self.format_price(price, currency) 
                prev_price = self.prev_prices.get(api_id)
                change_percent, change_str, change_color = self.calculate_change_percent(price, prev_price)
                current_forecast_tuple = self.get_forecast_tuple(change_percent) 

                if prev_price is not None and recalculate_order:
                    # 1. Обновляем историю
                    self.trend_history[api_id].append(current_forecast_tuple) 
                    self.trend_history[api_id] = self.trend_history[api_id][-HISTORY_SIZE:] 
                    
                    # 2. Проверяем самую длинную серию одинаковых индикаторов
                    history = self.trend_history[api_id]
                    
                    # Ищем самую длинную серию в конце истории (от 5 до 2)
                    max_series_length = 0
                    trend_icon = None
                    
                    # Проходим от самой длинной серии (5) до самой короткой (2)
                    for length in range(HISTORY_SIZE, 1, -1): # 5, 4, 3, 2
                        if len(history) >= length:
                            last_n_icons = [t[0] for t in history[-length:]]
                            
                            if all(icon == '▲' for icon in last_n_icons):
                                max_series_length = length
                                trend_icon = '▲'
                                break # Нашли самую длинную, выходим
                            elif all(icon == '▼' for icon in last_n_icons):
                                max_series_length = length
                                trend_icon = '▼'
                                break # Нашли самую длинную, выходим

                    # 3. СБОР СИГНАЛА вместо отправки уведомления
                    if max_series_length >= 2:
                        trend_type = "BULLISH" if trend_icon == '▲' else "BEARISH"
                        
                        active_trend_signals.append({
                            'coin_name': display_name,
                            'trend_type': trend_type,
                            'series_length': max_series_length,
                            'change_percent': change_percent
                        })
                
                
                # Колонка 2: Курс
                tk.Label(self.coins_frame, text=price_str, fg=colors['price_fg'], bg=colors['bg'], font=('Arial', font_size)).grid(row=row_num, column=2, sticky='e', padx=(5, 10)) 
                
                # Колонка 3: Стоимость (Value)
                tk.Label(self.coins_frame, text=self.format_total_value(current_value, currency), fg=colors['total_value_fg'], bg=colors['bg'], font=('Arial', font_size, 'bold')).grid(row=row_num, column=3, sticky='e', padx=(5, 10)) 
                
                # Колонка 4: Процентное изменение
                tk.Label(self.coins_frame, text=change_str, fg=change_color, bg=colors['bg'], font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=4, sticky='e', padx=(5, 10)) 
                
                # Колонка 5: История трендов
                forecast_frame = tk.Frame(self.coins_frame, bg=colors['bg'])
                forecast_frame.grid(row=row_num, column=5, sticky='e', padx=(5, 0)) 
                
                for i, (icon, color) in enumerate(self.trend_history.get(api_id, [])):
                    tk.Label(forecast_frame, text=icon, fg=color, bg=colors['bg'], font=('Arial', max(8, font_size - 2))).pack(side=tk.LEFT, padx=0, pady=0) 
                    
                if len(self.trend_history.get(api_id, [])) < HISTORY_SIZE:
                    for _ in range(HISTORY_SIZE - len(self.trend_history.get(api_id, []))):
                         tk.Label(forecast_frame, text=" ", fg='gray', bg=colors['bg'], font=('Arial', max(8, font_size - 2))).pack(side=tk.LEFT, padx=0, pady=0)


            else:
                # Если нет данных
                tk.Label(self.coins_frame, text="---", fg=colors['fg'], bg=colors['bg'], font=('Arial', font_size)).grid(row=row_num, column=2, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="---", fg=colors['fg'], bg=colors['bg'], font=('Arial', font_size)).grid(row=row_num, column=3, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="---", fg=colors['fg'], bg=colors['bg'], font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=4, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="❓" * HISTORY_SIZE, fg=colors['fg'], bg=colors['bg'], font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=5, sticky='e', padx=(5, 0)) 

            row_num += 1

        # --- Общая стоимость портфеля ---
        tk.Frame(self.portfolio_frame, height=1, bg=colors['separator_bg']).pack(fill='x', pady=2)

        total_label = tk.Label(self.portfolio_frame, text="Общий Портфель:", font=('Arial', font_size, 'bold'), bg=colors['bg'], fg=colors['fg'])
        total_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        value_label = tk.Label(self.portfolio_frame, text=self.format_total_value(total_portfolio_value, currency), font=('Arial', font_size, 'bold'), bg=colors['bg'], fg=colors['total_value_fg'])
        value_label.pack(side=tk.RIGHT, padx=5, pady=2)

        # 4. ВЫЗОВ КОНСОЛИДИРОВАННОГО ОКНА УВЕДОМЛЕНИЙ ПОСЛЕ ЗАВЕРШЕНИЯ ЦИКЛА
        if active_trend_signals:
            self.show_consolidated_notification(active_trend_signals)

        self.coins_frame.update_idletasks() 

    # --- Методы настроек (SettingsWindow) ---
    def open_settings(self):
        self.save_window_position()
        SettingsWindow(self, self.config)
        
    def apply_settings(self, new_config):
        
        old_autostart = self.config.get('autostart_enabled', False)
        new_autostart = new_config.get('autostart_enabled', False)
        
        if new_autostart != old_autostart:
            set_startup(new_autostart)
            
        self.config = new_config
        save_config(self.config)
        self.attributes('-alpha', self.config.get('opacity', 0.95))
        
        # Обновляем initial_coin_order, если были добавлены/удалены монеты
        self.initial_coin_order = list(self.config['coins'].keys())
        self.coin_order_list = self.initial_coin_order[:]
        self.sort_state = (None, None) 
        
        new_coin_ids = set(self.config['coins'].keys())
        self.trend_history = {api_id: self.trend_history.get(api_id, []) for api_id in new_coin_ids}
        
        self.update_widget()
        self.apply_theme() # Применяем новую тему

# --- GUI Окно Настроек (SettingsWindow) ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, master, config):
        super().__init__(master)
        self.master = master
        self.config = config.copy() 
        self.coin_amount_entries = {} 
        
        self.title("Настройки")
        self.grab_set() 
        self.state('normal') 
        
        target_width = 720  
        target_height = 1000 # УВЕЛИЧЕНА ВЫСОТА ОКНА
        
        self.minsize(width=target_width, height=target_height)
        self.maxsize(width=target_width, height=target_height) 
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = (screen_width // 2) - (target_width // 2)
        y = (screen_height // 2) - (target_height // 2)
        self.geometry(f'{target_width}x{target_height}+{x}+{y}')
        
        current_theme = self.master.config.get('theme', 'light')
        current_theme_colors = THEMES.get(current_theme, THEMES['light'])
        
        # Определяем цвет для галочки/переключателя (для темной темы)
        select_color = current_theme_colors.get('select_color', 'white')
        
        main_content_frame = tk.Frame(self, bg=current_theme_colors['bg']) 
        main_content_frame.pack(expand=True, padx=20, pady=10, fill='both')

        # --- Кнопка: Связаться с разработчиком (ВВЕРХУ) ---
        tk.Button(
            main_content_frame, 
            text="Связаться с разработчиком! GitHub 🚀", 
            command=self.master.open_developer_link,
            fg='blue', 
            cursor="hand2"
        ).pack(pady=(5, 10)) 
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5)
        
        # --- Настройки Темы --- 
        header_font = ('Arial', 9, 'bold') 
        
        tk.Label(main_content_frame, text="Настройки Темы:", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 

        self.theme_var = tk.StringVar(value=self.config.get('theme', 'light'))

        theme_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg'])
        theme_frame.pack(pady=(0, 5), anchor='w', padx=10) 

        tk.Radiobutton(
            theme_frame, 
            text="Светлая",
            variable=self.theme_var,
            value="light",
            selectcolor=select_color, # Устанавливаем selectcolor
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        ).pack(side=tk.LEFT, padx=10)

        tk.Radiobutton(
            theme_frame, 
            text="Темная",
            variable=self.theme_var,
            value="dark",
            selectcolor=select_color, # Устанавливаем selectcolor
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        ).pack(side=tk.LEFT, padx=10)

        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5) 
        
        # --- Настройки Автозапуска ---
        if winreg: 
            tk.Label(main_content_frame, text="Автозапуск Windows:", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 
            
            is_startup_active = check_startup()
            self.autostart_var = tk.BooleanVar(value=self.config.get('autostart_enabled', True))
            
            status_text = "ВКЛЮЧЕН (в реестре)" if is_startup_active else "ОТКЛЮЧЕН (в реестре)"
            status_color = 'green' if is_startup_active else 'red'
            
            self.autostart_status_label = tk.Label(
                main_content_frame, 
                text=f"Текущий статус: {status_text}", 
                fg=status_color, 
                font=('Arial', 8), 
                bg=current_theme_colors['bg']
            )
            self.autostart_status_label.pack(pady=(0, 3), anchor='w', padx=10) 
            
            autostart_check = tk.Checkbutton(
                main_content_frame, 
                text="Настройка (применить): Включить автозапуск виджета при входе в Windows",
                variable=self.autostart_var,
                onvalue=True,
                offvalue=False,
                selectcolor=select_color, # Устанавливаем selectcolor
                font=('Arial', 9),
                bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
            )
            autostart_check.pack(pady=(0, 5), anchor='w', padx=10) 
            tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5) 
        
        # --- Настройки Системного Трея и Уведомлений ---
        tk.Label(main_content_frame, text="Настройки Системного Трея и Уведомлений:", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 

        self.hide_var = tk.BooleanVar(value=self.config.get('hide_on_close', True))
        
        hide_check = tk.Checkbutton(
            main_content_frame, 
            text="Сворачивать в системный трей при нажатии 'X'",
            variable=self.hide_var,
            onvalue=True,
            offvalue=False,
            selectcolor=select_color, # Устанавливаем selectcolor
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        )
        hide_check.pack(pady=(0, 5), anchor='w', padx=10) 
        
        # НАСТРОЙКА: Режим уведомлений о трендах
        tk.Label(main_content_frame, text="Режим всплывающих окон уведомлений о трендах:", font=('Arial', 9, 'bold'), bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 0)) 
        
        self.notify_mode_var = tk.StringVar(value=self.config.get('notification_mode', 'always'))

        notify_mode_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg'])
        notify_mode_frame.pack(pady=(0, 5), anchor='w', padx=10) 

        tk.Radiobutton(
            notify_mode_frame, 
            text="Всегда (даже если окно открыто)",
            variable=self.notify_mode_var,
            value="always",
            selectcolor=select_color,
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Radiobutton(
            notify_mode_frame, 
            text="Только в трее (при свёрнутом окне)",
            variable=self.notify_mode_var,
            value="tray_only",
            selectcolor=select_color,
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Radiobutton(
            notify_mode_frame, 
            text="Отключить полностью",
            variable=self.notify_mode_var,
            value="disabled",
            selectcolor=select_color,
            font=('Arial', 9),
            bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']
        ).pack(side=tk.LEFT, padx=(0, 10))

        # НАСТРОЙКА: Длительность уведомлений
        tk.Label(main_content_frame, text="Длительность показа уведомления (сек):", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 
        
        duration_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg']); duration_frame.pack(fill='x', padx=10)
        self.duration_var = tk.DoubleVar(value=self.config.get('notification_duration_sec', 10))
        self.duration_label = tk.Label(duration_frame, text=f"Текущая: {int(self.duration_var.get())} сек", bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg'])
        self.duration_label.pack(side=tk.RIGHT)
        
        ttk.Scale(duration_frame, from_=5, to=60, orient='horizontal', variable=self.duration_var, command=self.update_duration_label).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))


        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5) 
        
        # --- Настройки шрифта и прозрачности ---
        tk.Label(main_content_frame, text="Размер шрифта курсов:", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 
        font_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg']); font_frame.pack(fill='x', padx=10)
        self.font_var = tk.DoubleVar(value=self.config.get('font_size', 10))
        self.font_label = tk.Label(font_frame, text=f"Текущий размер: {int(self.font_var.get())}", bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg'])
        self.font_label.pack(side=tk.RIGHT)
        
        # РЕАЛ-ТАЙМ ОБНОВЛЕНИЕ ШРИФТА
        ttk.Scale(font_frame, from_=8, to=40, orient='horizontal', variable=self.font_var, command=self.update_font_label).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5) 

        tk.Label(main_content_frame, text="Прозрачность окна (0.1 - 1.0):", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 5)) 
        opacity_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg']); opacity_frame.pack(fill='x', padx=10)
        self.opacity_var = tk.DoubleVar(value=self.config.get('opacity', 0.95))
        self.opacity_label = tk.Label(opacity_frame, text=f"Текущая: {self.opacity_var.get():.2f}", bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg'])
        self.opacity_label.pack(side=tk.RIGHT)
        
        # РЕАЛ-ТАЙМ ОБНОВЛЕНИЕ ПРОЗРАЧНОСТИ
        ttk.Scale(opacity_frame, from_=0.1, to=1.0, orient='horizontal', variable=self.opacity_var, command=self.update_opacity_label).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5) 
        
        # --- Управление монетами и портфелем ---
        tk.Label(main_content_frame, text="Управление отслеживаемыми монетами и портфелем:", font=header_font, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(3, 0)) 
        
        inst_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg'])
        inst_frame.pack(fill='x', padx=10)
        tk.Label(inst_frame, text="ID монеты (CoinGecko) | Имя в виджете | Количество монет (Amount)", font=('Arial', 8), bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(pady=(5, 0)) 
        coingecko_search_label = tk.Label(inst_frame, text="Найти ID монеты на CoinGecko", fg='blue', cursor="hand2", bg=current_theme_colors['bg'])
        coingecko_search_label.pack(pady=(0, 5)) 
        coingecko_search_label.bind("<Button-1>", lambda e: webbrowser.open(COINGECKO_HOME_LINK)) 
        
        # Увеличиваем высоту фрейма для списка монет (180 -> 240)
        list_frame = tk.Frame(main_content_frame, height=240, bg=current_theme_colors['bg']) 
        list_frame.pack(fill='x', padx=10, pady=(0, 5)) 
        list_frame.pack_propagate(False) 
        
        canvas = tk.Canvas(list_frame, bg=current_theme_colors['bg'])
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.current_coins_frame = tk.Frame(canvas, bg=current_theme_colors['bg'])

        self.current_coins_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.current_coins_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.update_coin_list()
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5)

        add_frame = tk.Frame(main_content_frame, bg=current_theme_colors['bg'])
        add_frame.pack(pady=5) 
        
        tk.Label(add_frame, text="ID монеты (CoinGecko):", bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(side=tk.LEFT)
        self.api_id_entry = tk.Entry(add_frame, width=20) 
        self.api_id_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(add_frame, text="Имя (Виджет):", bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(side=tk.LEFT)
        self.display_name_entry = tk.Entry(add_frame, width=10) 
        self.display_name_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(add_frame, text="Добавить", command=self.add_coin, bg=current_theme_colors['bg'], fg=current_theme_colors['settings_fg']).pack(side=tk.LEFT, padx=10)
        
        # Кнопка "Применить и Закрыть"
        tk.Button(
            main_content_frame, 
            text="Применить и Закрыть", 
            command=self.apply_and_close,
            bg=current_theme_colors['bg'], 
            fg=current_theme_colors['settings_fg']
        ).pack(pady=(10, 0), fill='x') 
        
    def update_font_label(self, value):
        new_font_size = int(float(value))
        self.font_label.config(text=f"Текущий размер: {new_font_size}")
        
        # ПРЕДПРОСМОТР: Временно обновляем конфиг мастера и перерисовываем виджет
        if self.master:
            self.master.config['font_size'] = new_font_size
            self.master.update_widget(recalculate_order=False)

        
    def update_opacity_label(self, value):
        new_opacity = float(value)
        self.opacity_label.config(text=f"Текущая: {new_opacity:.2f}")
        
        # ПРЕДПРОСМОТР: Немедленно применяем прозрачность к главному окну
        if self.master:
            self.master.attributes('-alpha', new_opacity)
            self.master.config['opacity'] = new_opacity # Временно обновляем конфиг мастера
            
    def update_duration_label(self, value):
        new_duration = int(float(value))
        self.duration_label.config(text=f"Текущая: {new_duration} сек")


    def update_coin_list(self):
        """Перерисовывает список монет, включая поля для ввода количества."""
        for widget in self.current_coins_frame.winfo_children():
            widget.destroy()
            
        self.coin_amount_entries = {}
        current_theme_colors = THEMES.get(self.master.config.get('theme', 'light'), THEMES['light'])
            
        for api_id, coin_data in self.config['coins'].items():
            display_name = coin_data.get('name', api_id.upper())
            amount = coin_data.get('amount', 0.0)
            
            coin_row = tk.Frame(self.current_coins_frame, bg=current_theme_colors['bg'])
            coin_row.pack(fill='x', pady=2) 
            
            label = tk.Label(
                coin_row, 
                text=f"{api_id} ({display_name}):", 
                width=25, 
                anchor='w', 
                font=('Arial', 9), 
                bg=current_theme_colors['bg'], 
                fg=current_theme_colors['settings_fg']
            )
            label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Поле для ввода количества (Amount)
            amount_var = tk.StringVar(value=str(amount))
            amount_entry = tk.Entry(coin_row, textvariable=amount_var, width=10) 
            amount_entry.pack(side=tk.LEFT, padx=5)
            
            self.coin_amount_entries[api_id] = amount_var
            
            delete_btn = tk.Button(
                coin_row, 
                text="Удалить", 
                command=lambda id=api_id: self.delete_coin(id),
                fg='red',
                font=('Arial', 9),
                bg=current_theme_colors['bg']
            )
            delete_btn.pack(side=tk.RIGHT)
        
        self.current_coins_frame.update_idletasks()


    def add_coin(self):
        """Добавляет новую монету в конфигурацию с нулевым количеством."""
        api_id = self.api_id_entry.get().strip().lower()
        display_name = self.display_name_entry.get().strip().upper()
        
        if not api_id or not display_name:
            messagebox.showerror("Ошибка", "Поля 'ID монеты' и 'Имя' должны быть заполнены.")
            return

        if api_id in self.config['coins']:
            messagebox.showwarning("Предупреждение", f"Монета '{api_id}' уже есть в списке.")
            return

        self.config['coins'][api_id] = {"name": display_name, "amount": 0.0}
        self.update_coin_list()
        self.api_id_entry.delete(0, tk.END)
        self.display_name_entry.delete(0, tk.END)
        messagebox.showinfo("Готово", f"Монета '{display_name}' добавлена.")

    def delete_coin(self, api_id):
        """Удаляет монету из конфигурации."""
        if api_id in self.config['coins']:
            del self.config['coins'][api_id]
            self.update_coin_list()
            messagebox.showinfo("Готово", f"Монета с ID '{api_id}' удалена.")
            
    def apply_and_close(self):
        """Сохраняет настройки и применяет их к главному виджету."""
        
        # 1. Сбор данных о количестве монет
        for api_id, amount_var in self.coin_amount_entries.items():
            try:
                amount = float(amount_var.get().replace(',', '.'))
                if api_id in self.config['coins']:
                    self.config['coins'][api_id]['amount'] = amount
            except ValueError:
                messagebox.showerror("Ошибка ввода", f"Неверное количество для монеты '{self.config['coins'][api_id]['name']}'. Используйте числа (напр., 0.5, 12.34).")
                return 
        
        # 2. Сбор данных автозапуска, трея, темы, режима и ДЛИТЕЛЬНОСТИ УВЕДОМЛЕНИЙ
        if winreg:
             self.config['autostart_enabled'] = self.autostart_var.get()
        else:
             self.config['autostart_enabled'] = False
             
        self.config['hide_on_close'] = self.hide_var.get()
        self.config['theme'] = self.theme_var.get() 
        self.config['notification_mode'] = self.notify_mode_var.get()
        self.config['notification_duration_sec'] = int(self.duration_var.get())

        # 3. Сохранение общих настроек (берем из временных значений, которые были в master.config)
        self.config['font_size'] = int(self.font_var.get())
        self.config['opacity'] = self.opacity_var.get()
        
        # 4. Применение и закрытие
        self.master.apply_settings(self.config)
        self.destroy()


if __name__ == '__main__':
    # Гарантируем, что файл конфигурации существует с правильной структурой
    config_data = load_config()
    
    # --- ЛОГИКА СИНХРОНИЗАЦИИ АВТОЗАПУСКА ПРИ СТАРТЕ ---
    if winreg:
        config_enabled = config_data.get('autostart_enabled', True)
        registry_active = check_startup()
        
        if config_enabled and not registry_active:
            set_startup(True)
            if not check_startup():
                 config_data['autostart_enabled'] = False
                 print("Не удалось установить автозапуск, статус в конфиге скорректирован.")
        
        elif not config_enabled and registry_active:
            set_startup(False)
            if check_startup():
                 config_data['autostart_enabled'] = True
                 print("Не удалось удалить автозапуск, статус в конфиге скорректирован.")

    save_config(config_data) 
    # -------------------------------------------------------------
        
    app = CryptoWidget()
    
    # --- БЛОК: СТАРТ В ТРЕЕ ---
    # Если запуск произошел через автозапуск Windows с флагом -autostart
    if '-autostart' in sys.argv and config_data.get('autostart_enabled', True):
        app.withdraw() # Скрыть основное окно
        app.is_hidden = True
        app.setup_tray_icon() # Инициализация иконки
        
        # Запуск трея в отдельном потоке, чтобы не блокировать Tkinter mainloop
        def run_tray():
            app.tray_icon.run()

        app.tray_thread = threading.Thread(target=run_tray, daemon=True)
        app.tray_thread.start()
        
    # --------------------------------
    
    app.mainloop()
