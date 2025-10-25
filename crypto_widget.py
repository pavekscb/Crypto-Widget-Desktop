import tkinter as tk
from tkinter import messagebox, ttk
import requests
import json
import os
import webbrowser

# --- Константы ---
CONFIG_FILE = 'config.json'
API_URL = "https://api.coingecko.com/api/v3/simple/price"
REFRESH_RATE_MS = 60000  # Обновление раз в минуту
COINGECKO_HOME_LINK = "https://www.coingecko.com/ru" 
HISTORY_SIZE = 5  # Размер истории трендов (5x)

# --- Управление Конфигурацией ---
def load_config():
    """Загружает конфигурацию из config.json или создает дефолтную."""
    default_config = {
        "base_currency": "usd", 
        "coins": {"bitcoin": "BTC", "ethereum": "ETH"},
        "font_size": 10,
        "window_x": None, 
        "window_y": None,
        "opacity": 0.95 
    }
    if not os.path.exists(CONFIG_FILE):
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Проверка на наличие новых полей
            for key, default_val in default_config.items():
                if key not in config:
                    config[key] = default_val
            return config
    except Exception:
        return default_config

def save_config(config):
    """Сохраняет текущую конфигурацию в config.json."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# --- Получение данных (API) ---
def get_crypto_prices(coin_ids, currency):
    """Получает курсы криптовалют с CoinGecko API."""
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

# --- GUI Виджет (Основное окно) ---
class CryptoWidget(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.prices_labels = {}
        
        self._x = 0
        self._y = 0
        
        # Хранение цен для сравнения
        self.prev_prices = {} 
        self.current_prices = {} 
        
        # История трендов (храним кортежи: (иконка, цвет))
        self.trend_history = {api_id: [] for api_id in self.config['coins']}
        
        self.progress_value = 0
        self.max_progress = REFRESH_RATE_MS // 1000 
        
        self.title("Курсы крипто монет CoinGeko") 
        
        self.attributes('-topmost', True) 
        self.resizable(False, False)
        self.configure(bg='SystemButtonFace')
        
        self.attributes('-alpha', self.config.get('opacity', 0.95)) 
        
        # Фрейм для монет (курсов)
        self.coins_frame = tk.Frame(self, bg='SystemButtonFace')
        self.coins_frame.pack(padx=10, pady=(5, 0), fill='both', expand=True) 
        
        # Фрейм для нижней части (статус и настройки)
        bottom_frame = tk.Frame(self, bg='SystemButtonFace')
        bottom_frame.pack(side=tk.BOTTOM, fill='x', padx=5, pady=(0, 5))
        
        # Индикатор прогресса (слева)
        self.progress_bar = ttk.Progressbar(
            bottom_frame, 
            orient='horizontal', 
            length=200, 
            mode='determinate',
            maximum=self.max_progress,
            value=self.progress_value
        )
        self.progress_bar.pack(side=tk.LEFT, fill='x', expand=True, padx=(5, 10))
        
        # Кнопка "Настройки" (только шестеренка, справа)
        self.settings_button = tk.Button(
            bottom_frame, text="⚙", command=self.open_settings, 
            font=('Arial', 10, 'bold'),
        )
        self.settings_button.pack(side=tk.RIGHT) 

        # Логика для перетаскивания
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self.settings_button.bind("<Button-1>", self.open_settings_and_break)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.update_widget()
        self.load_window_position()
        self.update_progress()
        
    def update_progress(self):
        """Обновляет значение прогресс-бара каждую секунду и вызывает обновление данных при завершении."""
        self.progress_value += 1
        if self.progress_value >= self.max_progress:
            self.update_widget()
        self.progress_bar['value'] = self.progress_value % self.max_progress 
        self.after(1000, self.update_progress) 

    def open_coin_link(self, api_id):
        """Открывает страницу CoinGecko для указанной монеты."""
        url = f"https://www.coingecko.com/coins/{api_id}" 
        webbrowser.open(url)
        
    def open_developer_link(self):
        """Открывает ссылку на разработчика."""
        webbrowser.open("https://github.com/pavekscb/Crypto-Widget-Desktop.git")

    def open_settings_and_break(self, event):
        self.open_settings()
        return "break"

    def on_close(self):
        self.save_window_position()
        self.destroy()

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
        """Форматирует цену."""
        if price is None:
             return "N/A"
        
        # Форматирование для очень маленьких цен
        if price < 0.01 and price != 0: 
            price_str = f"{price:.8f}".rstrip('0')
            if price_str.endswith('.'):
                price_str += '0'
            if '.' not in price_str:
                price_str = f"{price:.8f}"
        else:
            # Форматирование для стандартных цен
            price_str = f"{price:,.4f}" 
            
        return f"{price_str} {currency.upper()}"
        
    def calculate_change_percent(self, current_price, prev_price):
        """Рассчитывает процентное изменение."""
        if prev_price is None or prev_price == 0:
            return 0.0, "---", "gray" 
            
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
        except ZeroDivisionError:
            return 0.0, "---", "gray"
        except Exception:
            return 0.0, "---", "gray"
            
    def get_forecast_tuple(self, change_percent):
        """Возвращает кортеж (иконка, цвет) прогноза."""
        if change_percent > 0.01:
            return ("▲", "green") # Рост
        elif change_percent < -0.01:
            return ("▼", "red") # Падение
        else:
            return ("▬", "gray") # Стабильность / Нет данных

    def show_forecast_explanation(self, event):
        """Показывает всплывающее окно с объяснением логики прогноза."""
        explanation = (
            "ЛОГИКА ПРОГНОЗА И ИСТОРИИ ТРЕНДОВ:\n\n"
            "Эти значки отображают ПРЕДПОЛОЖЕНИЕ о продолжении тренда, "
            f"основанное на изменении курса за последние {REFRESH_RATE_MS // 1000} секунд (интервал обновления).\n\n"
            " • ▲ (Зеленый): Цена выросла более чем на 0.01% с последнего обновления.\n"
            " • ▼ (Красный): Цена упала более чем на 0.01% с последнего обновления.\n"
            " • ▬ (Серый): Цена осталась стабильной (изменение менее 0.01%).\n\n"
            "СТОЛБЕЦ ТРЕНДА:\n"
            f"Визуализация показывает **{HISTORY_SIZE} последних** трендов. Если вы видите '▲▲▼▬▼', это означает, что "
            "монета росла в двух последних циклах обновления, потом упала, была стабильна и снова упала.\n\n"
            "ВНИМАНИЕ: Это не финансовый совет и не точный прогноз, а лишь простая визуализация инерции."
        )
        self.unbind("<Button-1>")
        messagebox.showinfo("Что такое Тренд?", explanation)
        self.bind("<Button-1>", self.start_move)

    def show_coin_explanation(self, event):
        """Показывает всплывающее окно с объяснением, как добавлять монеты."""
        explanation = (
            "КАК ДОБАВЛЯТЬ МОНЕТЫ (API ID):\n\n"
            "Для добавления монеты в Настройках необходимо знать ее Идентификатор API (API ID) "
            "на CoinGecko. Это служебное имя, которое иногда отличается от имени в URL.\n\n"
            "➡️ ПРИМЕР: TON (The Open Network)\n"
            "   1. Идентификатор API: 'the-open-network'\n"
            "   2. В поле 'Имя' (Виджет) введите: 'TON'\n\n"
            "➡️ ПРИМЕР: DOGS (Dogs on Ton)\n"
            "   1. Страница монеты (URL): .../dogs\n"
            "   2. Идентификатор API: 'dogs-2'\n\n" 
            "   *Если ID монеты не работает (напр., 'dogs-2'), попробуйте найти точный ID через Google, "
            "    используя фразу 'CoinGecko API ID [Название монеты]'."
        )
        self.unbind("<Button-1>")
        messagebox.showinfo("Как добавить монету?", explanation)
        self.bind("<Button-1>", self.start_move)


    def update_widget(self):
        """Обновляет курсы и перерисовывает виджет в виде таблички."""
        
        # 1. Сброс прогресса
        self.progress_value = 0 
        self.progress_bar['value'] = self.progress_value
        
        font_size = self.config['font_size']
        coin_ids = list(self.config['coins'].keys())
        currency = self.config['base_currency']
        
        # 2. Сохраняем цены ПРЕДЫДУЩЕГО цикла
        self.prev_prices = self.current_prices.copy()
        
        # 3. Запрос НОВЫХ данных
        data = get_crypto_prices(coin_ids, currency)
        
        # 4. Очищаем текущие цены перед заполнением
        self.current_prices.clear()
        
        # 5. Обновляем trend_history для новых монет (если они появились)
        for api_id in coin_ids:
            if api_id not in self.trend_history:
                # Храним кортежи (иконка, цвет)
                self.trend_history[api_id] = [] 

        
        # 6. Перерисовка виджета
        for widget in self.coins_frame.winfo_children():
            widget.destroy()
        
        row_num = 0
        
        # --- Заголовки столбцов ---
        header_font = ('Arial', max(8, font_size - 4), 'bold')
        
        # Колонка 0: Монета (с привязкой к клику)
        coin_header_label = tk.Label(self.coins_frame, text="Монета:", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow")
        coin_header_label.grid(row=row_num, column=0, sticky='w', padx=(0, 5))
        coin_header_label.bind("<Button-1>", self.show_coin_explanation)
        
        # Колонка 1: Курс
        tk.Label(self.coins_frame, text="Курс:", font=header_font, bg='SystemButtonFace', fg='darkblue').grid(row=row_num, column=1, sticky='e', padx=(5, 10))
        
        # Колонка 2: Изм. %
        tk.Label(self.coins_frame, text="Изм. %:", font=header_font, bg='SystemButtonFace', fg='darkblue').grid(row=row_num, column=2, sticky='e', padx=(5, 10))
        
        # Колонка 3: Тренд (5x) (с привязкой к объяснению)
        forecast_header_label = tk.Label(self.coins_frame, text=f"Тренд ({HISTORY_SIZE}x):", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow") 
        forecast_header_label.grid(row=row_num, column=3, sticky='e', padx=(5, 0))
        forecast_header_label.bind("<Button-1>", self.show_forecast_explanation)
        
        row_num += 1

        # Разделитель
        tk.Frame(self.coins_frame, height=1, bg="gray").grid(row=row_num, columnspan=4, sticky='ew', pady=(2, 5))
        row_num += 1
        
        # --- Строки с курсами ---
        for api_id, display_name in self.config['coins'].items():
            
            # Колонка 0: Имя монеты
            name_label = tk.Label(
                self.coins_frame, 
                text=f"{display_name}:", 
                fg='blue', 
                bg='SystemButtonFace', 
                font=('Arial', font_size, 'bold'),
                cursor="hand2" 
            )
            name_label.grid(row=row_num, column=0, sticky='w', padx=(0, 5))

            name_label.bind("<Button-1>", lambda e, id=api_id: self.open_coin_link(id))
            name_label.bind("<Enter>", lambda e, l=name_label: l.config(fg='red'))
            name_label.bind("<Leave>", lambda e, l=name_label: l.config(fg='blue'))


            if api_id in data and currency in data[api_id]:
                price = data[api_id][currency]
                self.current_prices[api_id] = price # Сохранение текущей цены
                price_str = self.format_price(price, currency) 
                
                prev_price = self.prev_prices.get(api_id)
                
                change_percent, change_str, change_color = self.calculate_change_percent(price, prev_price)
                current_forecast_tuple = self.get_forecast_tuple(change_percent) # Получаем ТЕКУЩИЙ кортеж (иконка, цвет)

                # --- ЛОГИКА ИСТОРИИ ТРЕНДОВ ---
                if prev_price is not None:
                    # Добавляем текущий кортеж (иконка, цвет) в историю
                    self.trend_history[api_id].append(current_forecast_tuple) 
                    # Оставляем только HISTORY_SIZE последних
                    self.trend_history[api_id] = self.trend_history[api_id][-HISTORY_SIZE:] 
                
                # Колонка 1: Курс
                price_label = tk.Label(
                    self.coins_frame, 
                    text=price_str, 
                    fg='darkgreen', 
                    bg='SystemButtonFace', 
                    font=('Arial', font_size) 
                )
                price_label.grid(row=row_num, column=1, sticky='e', padx=(5, 10)) 
                
                # Колонка 2: Процентное изменение
                change_label = tk.Label(
                    self.coins_frame, 
                    text=change_str, 
                    fg=change_color, 
                    bg='SystemButtonFace', 
                    font=('Arial', max(8, font_size - 2)) 
                )
                change_label.grid(row=row_num, column=2, sticky='e', padx=(5, 10)) 
                
                # --- Колонка 3: История трендов (Новая логика) ---
                
                # Фрейм для вывода значков (нужен для выравнивания)
                forecast_frame = tk.Frame(self.coins_frame, bg='SystemButtonFace')
                forecast_frame.grid(row=row_num, column=3, sticky='e', padx=(5, 0)) 
                
                # Выводим значки по одному, индивидуально окрашивая
                for i, (icon, color) in enumerate(self.trend_history[api_id]):
                    # Создаем отдельную метку для каждого значка
                    icon_label = tk.Label(
                        forecast_frame, 
                        text=icon, 
                        fg=color, # <--- ИНДИВИДУАЛЬНАЯ ОКРАСКА!
                        bg='SystemButtonFace', 
                        font=('Arial', max(8, font_size - 2)) 
                    )
                    icon_label.pack(side=tk.LEFT, padx=0, pady=0) 
                    
                # Дополняем пробелами, если история неполная (для выравнивания)
                if len(self.trend_history[api_id]) < HISTORY_SIZE:
                    empty_count = HISTORY_SIZE - len(self.trend_history[api_id])
                    # Используем пустой значок "▬" серого цвета, чтобы место было занято
                    for _ in range(empty_count):
                         tk.Label(
                            forecast_frame, 
                            text=" ", # Используем пробел для пустоты
                            fg='gray', 
                            bg='SystemButtonFace', 
                            font=('Arial', max(8, font_size - 2)) 
                        ).pack(side=tk.LEFT, padx=0, pady=0)


            else:
                # Если нет данных (например, неверный ID или API ошибка)
                error_label = tk.Label(
                    self.coins_frame, 
                    text="---", 
                    fg='gray', bg='SystemButtonFace', 
                    font=('Arial', font_size)
                )
                error_label.grid(row=row_num, column=1, sticky='e', padx=(5, 10))
                
                tk.Label(self.coins_frame, text="---", fg='gray', bg='SystemButtonFace', font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=2, sticky='e', padx=(5, 10))
                
                # Если нет данных, выводим 5 знаков вопроса
                tk.Label(self.coins_frame, text="❓" * HISTORY_SIZE, fg='gray', bg='SystemButtonFace', font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=3, sticky='e', padx=(5, 0)) 

            row_num += 1

        self.coins_frame.grid_columnconfigure(1, weight=1)
        self.coins_frame.grid_columnconfigure(2, weight=1)
        # Колонка 3 должна содержать фрейм с пятью отдельными значками
        self.coins_frame.grid_columnconfigure(3, weight=0)
        self.coins_frame.update_idletasks() # Обновление для корректного расчета размера

    # --- Методы настроек (SettingsWindow) ---
    def open_settings(self):
        self.save_window_position()
        SettingsWindow(self, self.config)
        
    def apply_settings(self, new_config):
        self.config = new_config
        save_config(self.config)
        self.attributes('-alpha', self.config.get('opacity', 0.95))
        # Сброс истории трендов при изменении списка монет
        new_coin_ids = set(self.config['coins'].keys())
        # Обратите внимание: history теперь хранит (иконка, цвет)
        self.trend_history = {api_id: self.trend_history.get(api_id, []) for api_id in new_coin_ids}
        self.update_widget() 

# --- GUI Окно Настроек (без изменений) ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, master, config):
        super().__init__(master)
        self.master = master
        self.config = config.copy() 
        
        self.title("Настройки")
        self.grab_set() 
        self.state('normal') 
        self.geometry('') 
        
        self.update_idletasks() 
        min_width = 660
        min_height = 697
        self.minsize(width=min_width, height=min_height)
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = (screen_width // 2) - (min_width // 2)
        y = (screen_height // 2) - (min_height // 2)
        
        self.geometry(f'{min_width}x{min_height}+{x}+{y}')
        
        main_content_frame = tk.Frame(self)
        main_content_frame.pack(expand=True, padx=40, pady=20, fill='both') 
        
        tk.Label(main_content_frame, text="Размер шрифта курсов:", font=('Arial', 10, 'bold')).pack(pady=(10, 5)) 
        
        font_frame = tk.Frame(main_content_frame)
        font_frame.pack(fill='x', padx=10)
        
        self.font_var = tk.DoubleVar(value=self.config.get('font_size', 10))
        self.font_label = tk.Label(font_frame, text=f"Текущий размер: {int(self.font_var.get())}")
        self.font_label.pack(side=tk.RIGHT)
        
        ttk.Scale(
            font_frame, 
            from_=8, to=40,
            orient='horizontal', 
            variable=self.font_var,
            command=self.update_font_label
        ).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)

        tk.Label(main_content_frame, text="Прозрачность окна (0.1 - 1.0):", font=('Arial', 10, 'bold')).pack(pady=(10, 5)) 
        
        opacity_frame = tk.Frame(main_content_frame)
        opacity_frame.pack(fill='x', padx=10)
        
        self.opacity_var = tk.DoubleVar(value=self.config.get('opacity', 0.95))
        self.opacity_label = tk.Label(opacity_frame, text=f"Текущая: {self.opacity_var.get():.2f}")
        self.opacity_label.pack(side=tk.RIGHT)
        
        ttk.Scale(
            opacity_frame, 
            from_=0.1, to=1.0,
            orient='horizontal', 
            variable=self.opacity_var,
            command=self.update_opacity_label
        ).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))

        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)

        tk.Label(main_content_frame, text="Управление отслеживаемыми монетами:", font=('Arial', 10, 'bold')).pack(pady=(5, 0))
        
        tk.Label(main_content_frame, text="ID монеты берется из URL-адреса CoinGecko:").pack(pady=(5, 0))
        tk.Label(main_content_frame, text="Например, для Bitcoin ID = 'bitcoin' (URL: .../coins/bitcoin)").pack(pady=(0, 2))
        
        coingecko_search_label = tk.Label(
            main_content_frame, text="Найти ID монеты на CoinGecko", 
            fg='blue', cursor="hand2"
        )
        coingecko_search_label.pack(pady=(0, 10))
        coingecko_search_label.bind("<Button-1>", lambda e: webbrowser.open(COINGECKO_HOME_LINK)) 
        
        tk.Label(main_content_frame, text="Текущие монеты (API ID: Отображаемое имя):").pack(pady=5)
        
        self.current_coins_frame = tk.Frame(main_content_frame)
        self.current_coins_frame.pack(fill='x', padx=10)
        
        self.current_coins_frame.config(height=280) 
        self.current_coins_frame.pack_propagate(False) 
        
        self.update_coin_list()
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)

        add_frame = tk.Frame(main_content_frame)
        add_frame.pack(pady=5) 
        
        tk.Label(add_frame, text="ID монеты (CoinGecko):").pack(side=tk.LEFT)
        self.api_id_entry = tk.Entry(add_frame, width=20) 
        self.api_id_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(add_frame, text="Имя (Виджет):").pack(side=tk.LEFT)
        self.display_name_entry = tk.Entry(add_frame, width=10) 
        self.display_name_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(add_frame, text="Добавить", command=self.add_coin).pack(side=tk.LEFT)

        # Кнопки внизу
        tk.Button(main_content_frame, text="Применить и Закрыть", command=self.apply_and_close).pack(pady=(10, 5))
        
        # НОВАЯ КНОПКА: Связаться с разработчиком
        tk.Button(main_content_frame, 
                  text="Связаться с разработчиком! 🚀", 
                  command=self.master.open_developer_link,
                  fg='blue', 
                  cursor="hand2"
        ).pack(pady=(5, 10))
        
        self.current_coins_frame.pack_propagate(True)


    def update_font_label(self, value):
        self.font_label.config(text=f"Текущий размер: {int(float(value))}")
        
    def update_opacity_label(self, value):
        """Обновляет ярлык прозрачности и применяет значение к главному окну."""
        new_opacity = float(value)
        self.opacity_label.config(text=f"Текущая: {new_opacity:.2f}")
        self.master.attributes('-alpha', new_opacity)


    def update_coin_list(self):
        for widget in self.current_coins_frame.winfo_children():
            widget.destroy()
            
        for api_id, display_name in self.config['coins'].items():
            coin_row = tk.Frame(self.current_coins_frame)
            coin_row.pack(fill='x', pady=2)
            
            label = tk.Label(coin_row, text=f"{api_id}: {display_name}")
            label.pack(side=tk.LEFT, fill='x', expand=True)
            
            delete_btn = tk.Button(
                coin_row, text="Удалить", 
                command=lambda id=api_id: self.delete_coin(id),
                fg='red'
            )
            delete_btn.pack(side=tk.RIGHT)

        self.update_idletasks()
        self.geometry(self.geometry())


    def add_coin(self):
        api_id = self.api_id_entry.get().strip().lower()
        display_name = self.display_name_entry.get().strip().upper()
        
        if not api_id or not display_name:
            messagebox.showerror("Ошибка", "Оба поля должны быть заполнены.")
            return

        if api_id in self.config['coins']:
            messagebox.showwarning("Предупреждение", f"Монета '{api_id}' уже есть в списке.")
            return

        self.config['coins'][api_id] = display_name
        self.update_coin_list()
        self.api_id_entry.delete(0, tk.END)
        self.display_name_entry.delete(0, tk.END)
        messagebox.showinfo("Готово", f"Монета '{display_name}' добавлена в ожидании сохранения.")

    def delete_coin(self, api_id):
        if api_id in self.config['coins']:
            del self.config['coins'][api_id]
            self.update_coin_list()
            messagebox.showinfo("Готово", f"Монета с ID '{api_id}' удалена.")
            
    def apply_and_close(self):
        self.config['font_size'] = int(self.font_var.get())
        self.config['opacity'] = self.opacity_var.get()
        
        self.master.apply_settings(self.config)
        self.destroy()

if __name__ == '__main__':
    if not os.path.exists(CONFIG_FILE):
        save_config(load_config())
        
    app = CryptoWidget()
    app.mainloop()
