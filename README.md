<div align="center">

# <img src="https://img.shields.io/badge/Dynamic_Island-Roc_Edition-black?style=for-the-badge&logo=apple&logoColor=white" alt="Dynamic Island" height="36" />

<p align="center">
  <img src="https://img.shields.io/badge/OS-Arch_Linux_BTW-1793d1?style=for-the-badge&logo=arch-linux&logoColor=white" alt="Arch Linux" />
  <img src="https://img.shields.io/badge/Language-Pure_Roc_Core-purple?style=for-the-badge" alt="Roc Language" />
  <img src="https://img.shields.io/badge/Compositor-Hyprland_/_Wayland-blueviolet?style=for-the-badge" alt="Wayland" />
  <img src="https://img.shields.io/badge/CPU-Ivy_Bridge_Approved-green?style=for-the-badge" alt="Ivy Bridge" />
  <img src="https://img.shields.io/badge/Zero-Stutter_Guaranteed-brightgreen?style=for-the-badge" alt="Smooth" />
</p>

</div>

> **TL;DR:** Остров в стиле iPhone у верхней кромки экрана, портированный на **Arch Linux (Wayland)**. Вся физика, капли и математика написаны на функциональном языке **[Roc](https://www.roc-lang.org/)**, графика рендерится через **Wayland Layer Shell (GTK4 / Cairo)**, а запуск обеспечивает тихий фоновый загрузчик без единого лишнего варнинга в консоли.

---

## <img src="https://img.shields.io/badge/Fork-Original_Project-blue?style=flat-square&logo=github" height="20" /> Батя проекта (Credits & Fork)

Этот проект — идейный и архитектурный форк легендарного **[DynamicIsland от @mihailkotovski](https://github.com/mihailkotovski/DynamicIsland)**.

Михаил создал эталонный остров под Windows на C# WPF. Мы посмотрели на это великолепие, сказали *«I use Arch btw»*, решительно выкинули .NET, DirectX и Win32 API и пересобрали остров для тру-линуксоидов:
* **Базе [mihailkotovski/DynamicIsland](https://github.com/mihailkotovski/DynamicIsland)** — бесконечный респект и лучи уважения за исходный дизайн, физику пружин и логику острова.
* **Наш порт:** чистый функциональный **Roc** + **Wayland Layer Shell**, адаптация под картофельные процессоры (Intel Ivy Bridge / HD Graphics), идеально отцентрированное караоке и глубокая интеграция с MPRIS и PipeWire.

---

## <img src="https://img.shields.io/badge/Features-Overview-orange?style=flat-square" height="20" /> Что тут есть (по красоте)

* <img src="https://img.shields.io/badge/MPRIS-Music-1DB954?style=flat-square&logo=spotify&logoColor=white" height="18" /> **Музыка без костылей:** Spotify, Яндекс Музыка, Firefox, Chromium, mpv, VLC — подхватывает любой медиаплеер. Обложка выталкивает предыдущую при переключении, живой эквалайзер танцует под реальный звук из PipeWire, а ободок острова окрашивается в доминантный цвет альбома.
* <img src="https://img.shields.io/badge/LRCLIB-Karaoke-FF5722?style=flat-square" height="18" /> **Караоке прямо в баре:** Синхронный построчный текст с lrclib.net. Поющаяся строка заливается светом слева направо. Текст отцентрирован строго по центру до субпикселя, а на паузе трека ничего не зависает и не показывает старый куплет.
* <img src="https://img.shields.io/badge/PipeWire-Volume-009688?style=flat-square" height="18" /> **Громкость со скоростью света:** Раньше скролл мыши спамил десятками процессов `wpctl` в секунду, вешая слабый CPU. Теперь уровень громкости меняется мгновенно в памяти (0.0001 мс), а команды в систему отправляются мягко в фоне. Крути колесо с любой скоростью — интерфейс не лагнёт.
* <img src="https://img.shields.io/badge/Metaballs-Goo_Physics-673AB7?style=flat-square" height="18" /> **Жидкая капля таймера:** Настоящая векторная гидродинамика Безье. Если играет трек и ты включил таймер — таймер с физическим натяжением вытягивается из острова в отдельный шарик, перемычка истончается и с хлопком рвётся.
* <img src="https://img.shields.io/badge/Debounce-Anti_Spam-E91E63?style=flat-square" height="18" /> **Защита от случайных нажатий («Задержка при анимации»):** Если ты быстро кликаешь по острову, во время анимации раскрытия (380 мс) случайные нажатия на кнопки плеера блокируются. Включается и выключается в настройках.
* <img src="https://img.shields.io/badge/Daemon-Silent_Run-37474F?style=flat-square" height="18" /> **Бесшумный загрузчик:** Никакого спама в терминал от Mesa Intel Vulkan, GTK CSS и Gsk. Всё стартует в абсолютной тишине.
* <img src="https://img.shields.io/badge/Hardware-Battery_&_Net-4CAF50?style=flat-square" height="18" /> **Системные индикаторы:** Заряд Bluetooth-наушников (BlueZ), индикатор батареи и зарядки, статус Wi-Fi/Ethernet/VPN и умное автоскрытие в полноэкранных приложениях.

---

## <img src="https://img.shields.io/badge/Core-15_Roc_Modules-blueviolet?style=flat-square" height="20" /> Архитектура на языке Roc

Вся математическая модель, геометрия и физика реализованы на **15 модулях языка Roc**:

| Модуль Roc | За что отвечает | Тесты |
|---|---|:---:|
| `Spring.roc` | Пружинная физика затухающих колебаний (Эйлер, 1/240 сек) | 8/8 passed |
| `Goo.roc` | Математика капли: касательные, углы отрыва и кубические кривые Безье перемычки | 9/9 passed |
| `Icon.roc` | Все 30 векторных иконок на сетке 24x24 (включая логотип Arch Linux) | 26/26 passed |
| `Equalizer.roc` | 5-полосный логарифмический эквалайзер с плавающим порогом в dB | 5/5 passed |
| `Aura.roc` | Мягкое блуждающее свечение снизу плеера в цветах обложки | 4/4 passed |
| `Timer.roc` | Отсчёт 1-99 мин, форматирование `mm:ss`, статус срочности и отрыв капли | 23/23 passed |
| `Views.roc` | Конечный автомат всех 14 состояний острова и размеры пилюли | 7/7 passed |
| `Settings.roc` | Настройки: тумблеры, масштаб 85-130%, отступ от кромки, блокировка кликов | 6/6 passed |
| `Lyrics.roc` | Парсер таймкодов `[mm:ss.xx]`, расчёт активной строки и караоке-свип | 32/32 passed |
| `Digits.roc` | Перелистывание цифр с блюром и кинематикой | 5/5 passed |
| `Ring.roc` | Векторная дуга кольца таймера с круглыми наконечниками | 3/3 passed |
| `Toggle.roc` | iOS-переключатели с перетеканием цветов (серый в зелёный) | 5/5 passed |
| `Cover.roc` | Кинематика смены обложек: выталкивание со сглаживанием 4-й степени | 6/6 passed |
| `RowList.roc` | Магнитная подсветка пунктов меню за курсором | 21/21 passed |
| `DynamicIsland.roc` | Главный стейт `AppState`, координирующий все анимации и таймеры | 59/59 passed |

> Все 15 модулей собираются компилятором `roc` за **~50 миллисекунд** без единой ошибки.

---

## <img src="https://img.shields.io/badge/Controls-Inputs-lightgrey?style=flat-square" height="20" /> Управление

| Действие | Что произойдёт |
|---|---|
| **Левый клик по острову** | Раскрыть плеер или таймер (повторный клик — свернуть обратно) |
| **Клик по обложке в плеере** | Фокусирует окно плеера (в Hyprland перенесёт прямо на него) |
| **Правый клик** | Меню: Таймер, Настройки, Оформление, Выход (из подменю — шаг назад) |
| **Средний клик (колёсико)** | Остров прячется на 5 секунд |
| **Колесо мыши над островом** | Регулирует общую громкость (с мгновенным откликом) |
| **Колесо над плеером** | Регулирует громкость *только играющего приложения* |
| **Ctrl + Колесо мыши** | Переключает музыкальные плееры по кругу (Spotify, браузер и т.д.) |
| **Клик по звонящему таймеру** | Выключить будильник |

---

## <img src="https://img.shields.io/badge/Run-Quickstart-green?style=flat-square" height="20" /> Запуск

Лаунчер уже скомпилирован, настроен и запускается в фоне без шума в консоли:

```bash
# Запустить остров (работает тихо в фоне):
/home/neokirilx/DynamicIsland-roc/dynamic-island &
```

### Запуск конкретных экранов для тестов:
```bash
# Раскрытый плеер
./dynamic-island --view MediaBig

# Меню настроек
./dynamic-island --view Settings

# Настройка таймера
./dynamic-island --view TimerSet

# Сразу запустить таймер на 90 секунд
./dynamic-island --timer 90
```

### Запустить проверку всех Roc-модулей:
```bash
/home/neokirilx/DynamicIsland-roc/test_all.sh
```

---

## <img src="https://img.shields.io/badge/Setup-Autostart-purple?style=flat-square" height="20" /> Автозапуск в Hyprland / Sway

Чтобы остров появлялся сам при входе в систему:

В `~/.config/hypr/hyprland.conf`:
```ini
exec-once = /home/neokirilx/DynamicIsland-roc/dynamic-island &
```

Либо скопируй готовый `.desktop`:
```bash
mkdir -p ~/.config/autostart
cp /home/neokirilx/DynamicIsland-roc/dynamic-island.desktop ~/.config/autostart/
```

---

*Специально для Arch Linux Wayland.*
