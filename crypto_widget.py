import tkinter as tk
from tkinter import messagebox, ttk
import requests
import json
import os
import webbrowser
import locale
import sys

# Модуль для работы с реестром Windows (для автозапуска)
try:
    import winreg
except ImportError:
    winreg = None 

# Установка локали для форматирования чисел (если не работает, можно использовать f-string форматирование)
try:
    # Пытаемся установить русскую локаль для разделителей (если доступна)
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except locale.Error:
    try:
        # Резервный вариант: стандартная локаль C
        locale.setlocale(locale.LC_ALL, 'C')
    except locale.Error:
        pass


# --- Константы ---
CONFIG_FILE = 'config.json'
API_URL = "https://api.coingecko.com/api/v3/simple/price"
REFRESH_RATE_MS = 60000 # Обновление раз в минуту
COINGECKO_HOME_LINK = "https://www.coingecko.com/ru" 
HISTORY_SIZE = 5 # Размер истории трендов (5x)
APP_NAME = "CryptoWidgetCoinGeko" # Имя приложения для реестра
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# --- Функции реестра (Только для Windows) ---
def get_app_path():
    """Определяет чистый путь к исполняемому файлу или скрипту."""
    if getattr(sys, 'frozen', False):
         # Если приложение скомпилировано (PyInstaller): "C:\...\crypto.exe"
        app_path = os.path.abspath(sys.executable)
    else:
         # Если запускается как скрипт Python: "python.exe" "C:\...\script.py"
        python_path = sys.executable.replace('\\', '/')
        script_path = os.path.abspath(sys.argv[0]).replace('\\', '/')
        # Важно: команда для .py должна быть в формате "python.exe" "script.py"
        app_path = f'"{python_path}" "{script_path}"' 
        
    return f'"{app_path.strip()}"' # Обязательно в кавычках

def set_startup(enable=True):
    """
    Устанавливает или удаляет автозапуск приложения в реестре Windows, 
    явно указывая рабочий каталог для нахождения config.json.
    """
    if winreg is None:
        print("Модуль winreg недоступен (не Windows OS).")
        return False
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            # 1. Получаем путь к исполняемому файлу/скрипту (без внешних кавычек)
            clean_app_path = get_app_path().strip('"') 
            
            # 2. Получаем каталог, где находится файл
            working_dir = os.path.dirname(clean_app_path)
            
            # 3. Получаем имя файла приложения (для команды start)
            app_filename = os.path.basename(clean_app_path)
            
            # 4. Формируем команду: cmd /c start /d "рабочий каталог" имя_файла -autostart
            # Флаг -autostart нужен для подавления ошибок сохранения при старте
            command = (
                f'cmd /c start /d "{working_dir}" {app_filename} -autostart'
            )
            print(f"Команда для реестра: {command}")

            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            print(f"Автозапуск '{APP_NAME}' добавлен в реестр.")
        else:
            # Удаление значения
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
        # Просто проверяем наличие нашего ключа
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
        "autostart_enabled": True 
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
                        new_coins[api_id] = {
                            "name": data.get("name", api_id.upper()),
                            "amount": data.get("amount", 0.0)
                        }
                    
                config['coins'] = new_coins
            
            # Добавление отсутствующих дефолтных настроек
            for key, default_val in default_config.items():
                if key not in config:
                    config[key] = default_val
            return config
            
    except Exception:
        return default_config

def save_config(config):
    """Сохраняет текущую конфигурацию в config.json."""
    
    # Проверка на флаг автозапуска: подавляем ошибку, если запущено Windows
    suppress_error = '-autostart' in sys.argv 
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except PermissionError as e:
        print(f"Ошибка прав доступа при сохранении конфига: {e}") 
        
        if not suppress_error:
            # Показываем ошибку, только если это не автоматический запуск
            messagebox.showerror(
                "Ошибка сохранения", 
                f"Не удалось сохранить файл настроек '{CONFIG_FILE}' из-за ошибки прав доступа.\n"
                f"Пожалуйста, убедитесь, что у текущего пользователя есть права на запись в папку, где находится приложение.\n\nОшибка: {e}"
            )
    except Exception as e:
        print(f"Неизвестная ошибка при сохранении конфига: {e}")


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
        
        self._x = 0
        self._y = 0
        
        self.prev_prices = {} 
        self.current_prices = {} 
        
        self.trend_history = {api_id: [] for api_id in self.config['coins']}
        
        self.progress_value = 0
        self.max_progress = REFRESH_RATE_MS // 1000 
        
        self.title("Курсы крипто монет CoinGeko") 
        
        self.attributes('-topmost', True) 
        self.resizable(False, False)
        self.configure(bg='SystemButtonFace')
        
        self.attributes('-alpha', self.config.get('opacity', 0.95)) 
        
        self.coins_frame = tk.Frame(self, bg='SystemButtonFace')
        self.coins_frame.pack(padx=10, pady=(5, 0), fill='both', expand=True) 
        
        self.portfolio_frame = tk.Frame(self, bg='SystemButtonFace')
        self.portfolio_frame.pack(side=tk.BOTTOM, fill='x', padx=10, pady=(0, 5)) 
        
        bottom_frame = tk.Frame(self, bg='SystemButtonFace')
        bottom_frame.pack(side=tk.BOTTOM, fill='x', padx=5, pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(
            bottom_frame, 
            orient='horizontal', 
            length=200, 
            mode='determinate',
            maximum=self.max_progress,
            value=self.progress_value
        )
        self.progress_bar.pack(side=tk.LEFT, fill='x', expand=True, padx=(5, 10))
        
        self.settings_button = tk.Button(
            bottom_frame, text="⚙", command=self.open_settings, 
            font=('Arial', 10, 'bold'),
        )
        self.settings_button.pack(side=tk.RIGHT) 

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
        
    def format_total_value(self, value, currency):
        """Форматирует общую стоимость."""
        if value is None:
            return "N/A"
        
        # Форматируем как целое или с двумя знаками после запятой для удобства
        if value >= 1000:
             value_str = f"{value:,.2f}"
        elif value > 0:
            value_str = f"{value:.4f}"
        else:
            value_str = "0.00"
            
        return f"{value_str} {currency.upper()}"
        
    def format_amount(self, amount):
        """Форматирует количество монет."""
        if amount is None:
            return "0.00"
            
        if amount >= 10:
             amount_str = f"{amount:,.8f}".rstrip('0').rstrip('.')
             if amount_str.endswith(','):
                 amount_str += '00'
             if '.' not in amount_str and ',' not in amount_str:
                 amount_str = f"{amount:.2f}"
             if amount_str.endswith('.'):
                 amount_str += '00'
             return amount_str
        elif amount > 0:
             return f"{amount:,.8f}".rstrip('0')
        else:
             return "0.00"

        
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

    def show_portfolio_explanation(self, event):
        """Показывает всплывающее окно с объяснением логики портфеля."""
        explanation = (
            "РАСЧЕТ ПОРТФЕЛЯ:\n\n"
            "• Количество (Amount): Вводится вами в 'Настройках' для каждой монеты. "
            "Это количество монет, которым вы владеете.\n"
            "• Стоимость (Value): Рассчитывается как (Курс * Количество) для каждой монеты.\n"
            "• Общий Портфель: Сумма стоимостей всех отслеживаемых монет.\n\n"
            "Отображается в базовой валюте, выбранной в 'Настройках' (по умолчанию USD)."
        )
        self.unbind("<Button-1>")
        messagebox.showinfo("Что такое Портфель?", explanation)
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
        
        # Инициализация общей стоимости портфеля
        total_portfolio_value = 0.0
        
        # 5. Обновляем trend_history для новых монет (если они появились)
        for api_id in coin_ids:
            if api_id not in self.trend_history:
                self.trend_history[api_id] = [] 

        
        # 6. Перерисовка виджета
        for widget in self.coins_frame.winfo_children():
            widget.destroy()
        
        # Очистка фрейма портфеля
        for widget in self.portfolio_frame.winfo_children():
             widget.destroy()
             
        row_num = 0
        
        # --- Заголовки столбцов ---
        header_font = ('Arial', max(8, font_size - 4), 'bold')
        
        # Колонка 0: Монета
        coin_header_label = tk.Label(self.coins_frame, text="Монета:", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow")
        coin_header_label.grid(row=row_num, column=0, sticky='w', padx=(0, 5))
        coin_header_label.bind("<Button-1>", self.show_coin_explanation)
        
        # Колонка 1: Количество
        portfolio_amount_header = tk.Label(self.coins_frame, text="Количество:", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow")
        portfolio_amount_header.grid(row=row_num, column=1, sticky='e', padx=(5, 10))
        portfolio_amount_header.bind("<Button-1>", self.show_portfolio_explanation)
        
        # Колонка 2: Курс
        tk.Label(self.coins_frame, text="Курс:", font=header_font, bg='SystemButtonFace', fg='darkblue').grid(row=row_num, column=2, sticky='e', padx=(5, 10))
        
        # Колонка 3: Стоимость (Value)
        portfolio_value_header = tk.Label(self.coins_frame, text="Стоимость:", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow")
        portfolio_value_header.grid(row=row_num, column=3, sticky='e', padx=(5, 10))
        portfolio_value_header.bind("<Button-1>", self.show_portfolio_explanation)
        
        # Колонка 4: Изм. %
        tk.Label(self.coins_frame, text="Изм. %:", font=header_font, bg='SystemButtonFace', fg='darkblue').grid(row=row_num, column=4, sticky='e', padx=(5, 10))
        
        # Колонка 5: Тренд (5x) (с привязкой к объяснению)
        forecast_header_label = tk.Label(self.coins_frame, text=f"Тренд ({HISTORY_SIZE}x):", font=header_font, bg='SystemButtonFace', fg='darkblue', cursor="question_arrow") 
        forecast_header_label.grid(row=row_num, column=5, sticky='e', padx=(5, 0))
        forecast_header_label.bind("<Button-1>", self.show_forecast_explanation)
        
        # Настройка весов столбцов
        self.coins_frame.grid_columnconfigure(0, weight=0) # Монета
        self.coins_frame.grid_columnconfigure(1, weight=1) # Количество
        self.coins_frame.grid_columnconfigure(2, weight=1) # Курс
        self.coins_frame.grid_columnconfigure(3, weight=1) # Стоимость
        self.coins_frame.grid_columnconfigure(4, weight=1) # Изм. %
        self.coins_frame.grid_columnconfigure(5, weight=0) # Тренд (5x)

        row_num += 1

        # Разделитель
        tk.Frame(self.coins_frame, height=1, bg="gray").grid(row=row_num, columnspan=6, sticky='ew', pady=(2, 5))
        row_num += 1
        
        # --- Строки с курсами ---
        for api_id, coin_data in self.config['coins'].items():
            
            display_name = coin_data.get('name', api_id.upper())
            amount = coin_data.get('amount', 0.0)
            current_value = 0.0 # Стоимость этой монеты в портфеле

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
            
            # Колонка 1: Количество монет (Amount)
            amount_label = tk.Label(
                self.coins_frame, 
                text=self.format_amount(amount), 
                fg='darkmagenta', 
                bg='SystemButtonFace', 
                font=('Arial', font_size) 
            )
            amount_label.grid(row=row_num, column=1, sticky='e', padx=(5, 10))


            if api_id in data and currency in data[api_id]:
                price = data[api_id][currency]
                self.current_prices[api_id] = price # Сохранение текущей цены
                
                # Расчет стоимости
                try:
                    current_value = amount * price
                    total_portfolio_value += current_value
                except Exception:
                    pass # При ошибке (например, None), стоимость остается 0.0
                    
                price_str = self.format_price(price, currency) 
                
                prev_price = self.prev_prices.get(api_id)
                
                change_percent, change_str, change_color = self.calculate_change_percent(price, prev_price)
                current_forecast_tuple = self.get_forecast_tuple(change_percent) 

                # --- ЛОГИКА ИСТОРИИ ТРЕНДОВ ---
                if prev_price is not None:
                    self.trend_history[api_id].append(current_forecast_tuple) 
                    self.trend_history[api_id] = self.trend_history[api_id][-HISTORY_SIZE:] 
                
                # Колонка 2: Курс
                price_label = tk.Label(
                    self.coins_frame, 
                    text=price_str, 
                    fg='darkgreen', 
                    bg='SystemButtonFace', 
                    font=('Arial', font_size) 
                )
                price_label.grid(row=row_num, column=2, sticky='e', padx=(5, 10)) 
                
                # Колонка 3: Стоимость (Value)
                value_label = tk.Label(
                    self.coins_frame, 
                    text=self.format_total_value(current_value, currency), 
                    fg='darkblue', 
                    bg='SystemButtonFace', 
                    font=('Arial', font_size, 'bold') 
                )
                value_label.grid(row=row_num, column=3, sticky='e', padx=(5, 10)) 
                
                # Колонка 4: Процентное изменение
                change_label = tk.Label(
                    self.coins_frame, 
                    text=change_str, 
                    fg=change_color, 
                    bg='SystemButtonFace', 
                    font=('Arial', max(8, font_size - 2)) 
                )
                change_label.grid(row=row_num, column=4, sticky='e', padx=(5, 10)) 
                
                # --- Колонка 5: История трендов ---
                forecast_frame = tk.Frame(self.coins_frame, bg='SystemButtonFace')
                forecast_frame.grid(row=row_num, column=5, sticky='e', padx=(5, 0)) 
                
                for i, (icon, color) in enumerate(self.trend_history[api_id]):
                    icon_label = tk.Label(
                        forecast_frame, 
                        text=icon, 
                        fg=color, 
                        bg='SystemButtonFace', 
                        font=('Arial', max(8, font_size - 2)) 
                    )
                    icon_label.pack(side=tk.LEFT, padx=0, pady=0) 
                    
                if len(self.trend_history[api_id]) < HISTORY_SIZE:
                    empty_count = HISTORY_SIZE - len(self.trend_history[api_id])
                    for _ in range(empty_count):
                         tk.Label(
                            forecast_frame, 
                            text=" ", 
                            fg='gray', 
                            bg='SystemButtonFace', 
                            font=('Arial', max(8, font_size - 2)) 
                        ).pack(side=tk.LEFT, padx=0, pady=0)


            else:
                # Если нет данных (API ошибка или неверный ID)
                tk.Label(self.coins_frame, text="---", fg='gray', bg='SystemButtonFace', font=('Arial', font_size)).grid(row=row_num, column=2, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="---", fg='gray', bg='SystemButtonFace', font=('Arial', font_size)).grid(row=row_num, column=3, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="---", fg='gray', bg='SystemButtonFace', font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=4, sticky='e', padx=(5, 10))
                tk.Label(self.coins_frame, text="❓" * HISTORY_SIZE, fg='gray', bg='SystemButtonFace', font=('Arial', max(8, font_size - 2))).grid(row=row_num, column=5, sticky='e', padx=(5, 0)) 

            row_num += 1

        # --- Общая стоимость портфеля ---
        tk.Frame(self.portfolio_frame, height=1, bg="darkgray").pack(fill='x', pady=2)

        total_label = tk.Label(
            self.portfolio_frame, 
            text="Общий Портфель:", 
            font=('Arial', font_size, 'bold'), 
            bg='SystemButtonFace', 
            fg='black'
        )
        total_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        value_label = tk.Label(
            self.portfolio_frame, 
            text=self.format_total_value(total_portfolio_value, currency), 
            font=('Arial', font_size, 'bold'), 
            bg='SystemButtonFace', 
            fg='darkblue'
        )
        value_label.pack(side=tk.RIGHT, padx=5, pady=2)


        self.coins_frame.update_idletasks() 

    # --- Методы настроек (SettingsWindow) ---
    def open_settings(self):
        self.save_window_position()
        SettingsWindow(self, self.config)
        
    def apply_settings(self, new_config):
        # 1. Применяем Autostart
        old_autostart = self.config.get('autostart_enabled', False)
        new_autostart = new_config.get('autostart_enabled', False)
        
        if new_autostart != old_autostart:
            set_startup(new_autostart)
            
        # 2. Сохраняем и обновляем
        self.config = new_config
        save_config(self.config)
        self.attributes('-alpha', self.config.get('opacity', 0.95))
        new_coin_ids = set(self.config['coins'].keys())
        self.trend_history = {api_id: self.trend_history.get(api_id, []) for api_id in new_coin_ids}
        self.update_widget() 

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
        
        # Размеры окна
        target_width = 640  
        target_height = 885 
        
        # Устанавливаем и минимальный, и фиксированный размер
        self.minsize(width=target_width, height=target_height)
        self.maxsize(width=target_width, height=target_height) 
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Центрирование окна
        x = (screen_width // 2) - (target_width // 2)
        y = (screen_height // 2) - (target_height // 2)
        self.geometry(f'{target_width}x{target_height}+{x}+{y}')
        
        # Общий фрейм
        main_content_frame = ttk.Frame(self)
        main_content_frame.pack(expand=True, padx=20, pady=10, fill='both')


        # --- Кнопка: Связаться с разработчиком (ВВЕРХУ) ---
        tk.Button(main_content_frame, 
                  text="Связаться с разработчиком! 🚀", 
                  command=self.master.open_developer_link,
                  fg='blue', 
                  cursor="hand2"
        ).pack(pady=(5, 15))
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=5)
        # ----------------------------------------------------------------

        
        # --- Настройки Автозапуска ---
        if winreg: 
            tk.Label(main_content_frame, text="Автозапуск Windows:", font=('Arial', 10, 'bold')).pack(pady=(10, 5))
            
            # 1. Получаем актуальный статус из реестра для отображения
            is_startup_active = check_startup()
            
            # 2. Устанавливаем переменную Checkbutton на основе конфига (для применения)
            self.autostart_var = tk.BooleanVar(value=self.config.get('autostart_enabled', True))
            
            # 3. Метка статуса из реестра
            status_text = "ВКЛЮЧЕН (в реестре)" if is_startup_active else "ОТКЛЮЧЕН (в реестре)"
            status_color = 'green' if is_startup_active else 'red'
            
            self.autostart_status_label = tk.Label(
                main_content_frame, 
                text=f"Текущий статус: {status_text}", 
                fg=status_color, 
                font=('Arial', 9)
            )
            self.autostart_status_label.pack(pady=(0, 5), anchor='w', padx=10)
            
            autostart_check = tk.Checkbutton(
                main_content_frame, 
                text="Настройка (применить): Включить автозапуск виджета при входе в Windows",
                variable=self.autostart_var,
                onvalue=True,
                offvalue=False
            )
            autostart_check.pack(pady=(0, 10), anchor='w', padx=10)
            tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)
        
        # --- Настройки шрифта и прозрачности ---
        tk.Label(main_content_frame, text="Размер шрифта курсов:", font=('Arial', 10, 'bold')).pack(pady=(10, 5)) 
        font_frame = tk.Frame(main_content_frame); font_frame.pack(fill='x', padx=10)
        self.font_var = tk.DoubleVar(value=self.config.get('font_size', 10))
        self.font_label = tk.Label(font_frame, text=f"Текущий размер: {int(self.font_var.get())}")
        self.font_label.pack(side=tk.RIGHT)
        ttk.Scale(font_frame, from_=8, to=40, orient='horizontal', variable=self.font_var, command=self.update_font_label).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)

        tk.Label(main_content_frame, text="Прозрачность окна (0.1 - 1.0):", font=('Arial', 10, 'bold')).pack(pady=(10, 5)) 
        opacity_frame = tk.Frame(main_content_frame); opacity_frame.pack(fill='x', padx=10)
        self.opacity_var = tk.DoubleVar(value=self.config.get('opacity', 0.95))
        self.opacity_label = tk.Label(opacity_frame, text=f"Текущая: {self.opacity_var.get():.2f}")
        self.opacity_label.pack(side=tk.RIGHT)
        ttk.Scale(opacity_frame, from_=0.1, to=1.0, orient='horizontal', variable=self.opacity_var, command=self.update_opacity_label).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)
        # --- Конец настроек шрифта и прозрачности ---

        
        # --- Управление монетами и портфелем ---
        tk.Label(main_content_frame, text="Управление отслеживаемыми монетами и портфелем:", font=('Arial', 10, 'bold')).pack(pady=(5, 0))
        
        inst_frame = tk.Frame(main_content_frame)
        inst_frame.pack(fill='x', padx=10)
        tk.Label(inst_frame, text="ID монеты (CoinGecko) | Имя в виджете | Количество монет в портфеле (Amount)").pack(pady=(5, 0))
        coingecko_search_label = tk.Label(inst_frame, text="Найти ID монеты на CoinGecko", fg='blue', cursor="hand2")
        coingecko_search_label.pack(pady=(0, 10))
        coingecko_search_label.bind("<Button-1>", lambda e: webbrowser.open(COINGECKO_HOME_LINK)) 
        
        list_frame = tk.Frame(main_content_frame, height=200) 
        list_frame.pack(fill='x', padx=10, pady=(0, 10))
        list_frame.pack_propagate(False) 
        
        canvas = tk.Canvas(list_frame)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.current_coins_frame = tk.Frame(canvas)

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
        
        tk.Frame(main_content_frame, height=1, bg="gray").pack(fill='x', padx=10, pady=10)

        add_frame = tk.Frame(main_content_frame)
        add_frame.pack(pady=5) 
        
        tk.Label(add_frame, text="ID монеты (CoinGecko):").pack(side=tk.LEFT)
        self.api_id_entry = tk.Entry(add_frame, width=20) 
        self.api_id_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(add_frame, text="Имя (Виджет):").pack(side=tk.LEFT)
        self.display_name_entry = tk.Entry(add_frame, width=10) 
        self.display_name_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(add_frame, text="Добавить", command=self.add_coin).pack(side=tk.LEFT, padx=10)
        
        # Кнопка "Применить и Закрыть"
        tk.Button(main_content_frame, text="Применить и Закрыть", command=self.apply_and_close).pack(pady=(15, 0), fill='x')
        # --- Конец управления монетами ---


    def update_font_label(self, value):
        self.font_label.config(text=f"Текущий размер: {int(float(value))}")
        
    def update_opacity_label(self, value):
        new_opacity = float(value)
        self.opacity_label.config(text=f"Текущая: {new_opacity:.2f}")
        self.master.attributes('-alpha', new_opacity)


    def update_coin_list(self):
        """Перерисовывает список монет, включая поля для ввода количества."""
        for widget in self.current_coins_frame.winfo_children():
            widget.destroy()
            
        self.coin_amount_entries = {}
            
        for api_id, coin_data in self.config['coins'].items():
            display_name = coin_data.get('name', api_id.upper())
            amount = coin_data.get('amount', 0.0)
            
            coin_row = tk.Frame(self.current_coins_frame)
            coin_row.pack(fill='x', pady=5)
            
            label = tk.Label(coin_row, text=f"{api_id} ({display_name}):", width=30, anchor='w')
            label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Поле для ввода количества (Amount)
            amount_var = tk.StringVar(value=str(amount))
            amount_entry = tk.Entry(coin_row, textvariable=amount_var, width=15)
            amount_entry.pack(side=tk.LEFT, padx=5)
            
            self.coin_amount_entries[api_id] = amount_var
            
            delete_btn = tk.Button(
                coin_row, text="Удалить", 
                command=lambda id=api_id: self.delete_coin(id),
                fg='red'
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
                # Заменяем запятую на точку для корректного преобразования в float
                amount = float(amount_var.get().replace(',', '.'))
                if api_id in self.config['coins']:
                    self.config['coins'][api_id]['amount'] = amount
            except ValueError:
                messagebox.showerror("Ошибка ввода", f"Неверное количество для монеты '{self.config['coins'][api_id]['name']}'. Используйте числа (напр., 0.5, 12.34).")
                return 
        
        # 2. Сбор данных автозапуска
        if winreg:
             self.config['autostart_enabled'] = self.autostart_var.get()
        else:
             self.config['autostart_enabled'] = False
        
        # 3. Сохранение общих настроек
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
        
        # Принудительно устанавливаем автозапуск, если он включен в конфиге, но отсутствует в реестре
        if config_enabled and not registry_active:
            set_startup(True)
            # После установки, проверяем, что установка прошла успешно, иначе корректируем конфиг
            if not check_startup():
                 config_data['autostart_enabled'] = False
                 print("Не удалось установить автозапуск, статус в конфиге скорректирован.")
        
        # Принудительно удаляем автозапуск, если он отключен в конфиге, но присутствует в реестре
        elif not config_enabled and registry_active:
            set_startup(False)
            if check_startup():
                 config_data['autostart_enabled'] = True
                 print("Не удалось удалить автозапуск, статус в конфиге скорректирован.")

    save_config(config_data) 
    # -------------------------------------------------------------
        
    app = CryptoWidget()
    app.mainloop()
