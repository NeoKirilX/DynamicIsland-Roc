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

> **TL;DR:** Остров в стиле iPhone у верхней кромки экрана, портированный на **Arch Linux (Wayland)**. Вся физика, капли и математика написаны на функциональном языке **[Roc](https://www.roc-lang.org/)**, графика рендерится через **Wayland Layer Shell (GTK4 / Cairo)**, а запуск обеспечивает тихий фоновый загрузчик с умным доктором и блекджеком.

---

## <img src="https://img.shields.io/badge/Fork-Original_Project-blue?style=flat-square&logo=github" height="20" /> Батя проекта (Credits & Fork)

Этот проект — идейный и архитектурный форк легендарного **[DynamicIsland от @mihailkotovski](https://github.com/mihailkotovski/DynamicIsland)**.

Михаил создал эталонный остров под Windows на C# WPF. Мы посмотрели на это великолепие, сказали *«I use Arch btw»*, решительно выкинули .NET, DirectX и Win32 API и пересобрали остров для тру-линуксоидов:
* **Базе [mihailkotovski/DynamicIsland](https://github.com/mihailkotovski/DynamicIsland)** — бесконечный респект и лучи уважения за исходный дизайн, физику пружин и логику острова.
* **Наш порт:** чистый функциональный **Roc** + **Wayland Layer Shell**, адаптация под картофельные процессоры (Intel Ivy Bridge / HD Graphics), идеально отцентрированное караоке, умная полка файлов и глубокая интеграция с MPRIS и PipeWire.

---

## <img src="https://img.shields.io/badge/Features-Overview-orange?style=flat-square" height="20" /> Что тут есть (по красоте)

* <img src="https://img.shields.io/badge/MPRIS-Music-1DB954?style=flat-square&logo=spotify&logoColor=white" height="18" /> **Музыка без костылей:** Spotify, Яндекс Музыка, Firefox, Chromium, mpv, VLC — подхватывает любой медиаплеер. Обложка выталкивает предыдущую при переключении, живой эквалайзер танцует под реальный звук из PipeWire, а ободок острова окрашивается в доминантный цвет альбома.
* <img src="https://img.shields.io/badge/Covers-All_Ears-E91E63?style=flat-square" height="18" /> **Всеядный ловец обложек:** Парсит `mpris:artUrl`, обращается напрямую к `playerctl metadata`, вытаскивает локальные картинки `cover.jpg` / `folder.jpg` и кэширует всё в системе. Обложка появится, даже если плеер ленится её отдавать.
* <img src="https://img.shields.io/badge/Filter-30s_Audio-795548?style=flat-square" height="18" /> **Фильтр звукового спама (< 30 сек):** Звуки уведомлений из Telegram, пищалки дискорда и системные пуки больше не перехватывают остров и не ломают отображение музыки. Всё, что короче 30 секунд — игнорируется на входе.
* <img src="https://img.shields.io/badge/Karaoke-Dual_Mode-FF5722?style=flat-square" height="18" /> **Двухрежимное караоке и паузы (LRCLIB + NetEase):** 
  * Если у трека есть таймкоды — слова загораются слева направо в такт пению.
  * Если пословных таймингов нет — включается альтернативная анимация: мягкое вертикальное заполнение светом **сверху вниз** для всей строки.
  * На проигрышах и паузах — три «дышащие» точки, которые плавно гаснут по одной к началу следующего куплета.
  * В свернутом режиме длинные строки плавно скользят (marquee) с 16-пиксельным затуханием краев (Soft Fade Mask) — никакого резкого обрезания текста об обложку!
* <img src="https://img.shields.io/badge/Bar-LineBar-00ACC1?style=flat-square" height="18" /> **Построчный бар трека (LineBar):** Полоса воспроизведения нарезается на сегменты по строкам песни с магнитным прилипанием при перемотке. В меню «Оформление» можно выбрать сплошную или построчную полосу.
* <img src="https://img.shields.io/badge/Equalizer-Matrix_Dots-8E24AA?style=flat-square" height="18" /> **Матричный эквалайзер из точек:** Режим эквалайзера в виде матрицы светящихся точек, зажигающихся снизу вверх от баса. Переключается в меню «Оформление» (Матрица / Полоски).
* <img src="https://img.shields.io/badge/Gestures-Pill_Physics-43A047?style=flat-square" height="18" /> **Интерактивные жесты:** Потяни компактную пилюлю вниз — она упруго натягивается и раскрывается; смахни влево или вправо — трек переключится с физическим отскоком.
* <img src="https://img.shields.io/badge/Controls-Kinematics-3949AB?style=flat-square" height="18" /> **Кинематика плеера и кнопок:** На паузе обложка отступает назад и упруго пружинит при возобновлении; треугольники кнопок «назад» и «вперёд» шагают на одно место вперед при каждом клике.
* <img src="https://img.shields.io/badge/Alarm-Pendulum_Shake-E53935?style=flat-square" height="18" /> **Живой будильник таймера:** Качающийся колокольчик-маятник, вибрирующий остров, пульсирующий ободок и кольцо остатка времени вокруг кнопки таймера.
* <img src="https://img.shields.io/badge/Updates-In_App-1E88E5?style=flat-square" height="18" /> **Страница обновлений:** Вкладка в настройках с проверкой релизов на GitHub, списком изменений и кнопкой обновления.
* <img src="https://img.shields.io/badge/Combo-Adlib_Proof-9C27B0?style=flat-square" height="18" /> **Бронебойные комбо повторяющихся строк:** Повторяющиеся строчки схлопываются в комбо (`х1`, `х2`, `х3`). А если между ними затесался эдлиб вроде `(у)`, `(yeah)` или `(эй)` — счётчик не собьётся и продолжит серию!
* <img src="https://img.shields.io/badge/Shelf-Drag_&_Drop-00BCD4?style=flat-square" height="18" /> **Полка файлов с полным Drag & Drop:**
  * Закидывай файлы прямо на остров из Dolphin, Krusader или Nautilus — полка раскроется сама.
  * Надо отправить файл в Telegram, Discord или браузер? Просто бери файл с полки мышиным хватом и тащи в нужное окно!
  * Превьюшки картинок генерируются на лету в фоне, а счётчик файлов уютно висит рядом с таймером.
* <img src="https://img.shields.io/badge/Position-Infinite_XY-3F51B5?style=flat-square" height="18" /> **Свободное перемещение по X и Y (Без границ):** Заходи в меню «Оформление» и таскай остров мышью хоть в угол экрана, хоть на второй монитор:
  * **Без клавиш:** шаг 1 px (для пиксель-пёрфект маньяков).
  * **С зажатым Shift:** шаг 10 px.
  * **С зажатым Ctrl:** шаг 50 px (для тех, кто ценит скорость).
  * Работает как перетаскиванием мыши, так и стрелками клавиатуры или колесом над меню.
* <img src="https://img.shields.io/badge/Fullscreen-Smart_Hyprland-4CAF50?style=flat-square" height="18" /> **Умный Fullscreen (Super+F friendly):** Остров отличает режим `Maximized` (`fullscreen 1`) от реального `Fullscreen` (`fullscreen 2`). Разворачивай окна по `Super + F` в Hyprland / end-4-dotfiles сколько душе угодно — остров не спрячется. Спрячется он только в реальных полноэкранных играх и видео.
* <img src="https://img.shields.io/badge/PipeWire-Volume-009688?style=flat-square" height="18" /> **Громкость со скоростью света:** Громкость меняется мгновенно в памяти (0.0001 мс), а команды в систему улетают мягко в фоне. Крути колесо с любой скоростью — интерфейс не лагнёт.
* <img src="https://img.shields.io/badge/Metaballs-Goo_Physics-673AB7?style=flat-square" height="18" /> **Жидкая капля таймера:** Векторная гидродинамика Безье. Таймер с физическим натяжением вытягивается из острова в отдельный шарик, перемычка истончается и с хлопком рвётся.
* <img src="https://img.shields.io/badge/Debounce-Anti_Spam-E91E63?style=flat-square" height="18" /> **Защита от мисскликов:** Во время анимации раскрытия (380 мс) случайные нажатия на кнопки плеера блокируются. При этом меню настроек кликается мгновенно и без задержек.
* <img src="https://img.shields.io/badge/Doctor-Diagnostics-607D8B?style=flat-square" height="18" /> **Системный Доктор (`island --doctor`):** Никаких падений в тишину! Команда проверит наличие Wayland, GTK4, LayerShell, Cairo и кодеков, а подробный лог пишется в `~/.local/state/dynamic-island/island.log`.

---

## <img src="https://img.shields.io/badge/Core-18_Roc_Modules-blueviolet?style=flat-square" height="20" /> Архитектура на языке Roc

Вся математическая модель, геометрия и физика реализованы на **18 модулях языка Roc**:

| Модуль Roc | За что отвечает | Тесты |
|---|---|:---:|
| `Spring.roc` | Пружинная физика затухающих колебаний (Эйлер, 1/240 сек) | 8/8 passed |
| `Goo.roc` | Математика капли: касательные, углы отрыва и кубические кривые Безье перемычки | 9/9 passed |
| `Icon.roc` | Все 33 векторные иконки на сетке 24x24 (включая Moon, Tray, Cross и Arch Linux) | 29/29 passed |
| `Equalizer.roc` | 5-полосный логарифмический эквалайзер с плавающим порогом в dB | 5/5 passed |
| `Aura.roc` | Мягкое блуждающее свечение снизу плеера в цветах обложки | 4/4 passed |
| `Timer.roc` | Отсчёт 1-99 мин, форматирование `mm:ss`, статус срочности и отрыв капли | 23/23 passed |
| `Views.roc` | Конечный автомат всех 16 состояний острова и размеры пилюли | 8/8 passed |
| `Settings.roc` | Настройки: тумблеры, масштаб 85-130%, отступ от кромки, блокировка кликов, заглавная буква | 6/6 passed |
| `Lyrics.roc` | Парсер таймкодов `[mm:ss.xx]`, расчёт активной строки и караоке-свип | 32/32 passed |
| `Digits.roc` | Перелистывание цифр с блюром и кинематикой, авто-определение `shrinks` | 8/8 passed |
| `Ring.roc` | Векторная дуга кольца таймера с круглыми наконечниками | 3/3 passed |
| `Toggle.roc` | iOS-переключатели с перетеканием цветов (серый в зелёный) | 5/5 passed |
| `Cover.roc` | Кинематика смены обложек: выталкивание со сглаживанием 4-й степени | 6/6 passed |
| `RowList.roc` | Магнитная подсветка пунктов меню за курсором | 21/21 passed |
| `Shelf.roc` | Полка файлов: сетка слотов 4x2, геометрия карточек и счетчик | 5/5 passed |
| `Shimmer.roc` | Мерцающий скелетон текста песни (фазовый расчет волны) | 6/6 passed |
| `Media.roc` | Фильтрация треков (порог 30 с), очистка тегов и капитализация названий | 18/18 passed |
| `DynamicIsland.roc` | Главный стейт `AppState`, координирующий все анимации и таймеры | 59/59 passed |

> Все 18 модулей собираются компилятором `roc` за **~50 миллисекунд** без единой ошибки.

---

## <img src="https://img.shields.io/badge/Controls-Inputs-lightgrey?style=flat-square" height="20" /> Управление

| Действие | Что произойдёт |
|---|---|
| **Левый клик по острову** | Раскрыть плеер или таймер (повторный клик — свернуть обратно) |
| **Потянуть компактный остров вниз** | Упругое натяжение и раскрытие плеера или таймера при отпускании |
| **Толкнуть остров влево или вправо** | Следующий или предыдущий трек с физическим отскоком |
| **Клик по обложке в плеере** | Фокусирует окно плеера (в Hyprland перенесёт прямо на него) |
| **Правый клик** | Главное меню: Таймер, Полка файлов, Настройки, Оформление, Выход |
| **Средний клик (колёсико)** | Остров прячется на 5 секунд |
| **Колесо мыши над островом** | Регулирует общую громкость (с мгновенным откликом) |
| **Колесо над плеером** | Регулирует громкость *только играющего приложения* |
| **Ctrl + Колесо мыши** | Переключает музыкальные плееры по кругу (Spotify, браузер и т.д.) |
| **Клик по звонящему таймеру** | Выключить будильник |
| **Перетаскивание файла на остров** | Автоматически раскрывает полку и сохраняет файл |
| **Перетаскивание файла из полки** | Хватай плитку файла и тащи в Telegram, Discord, Dolphin или браузер |
| **Клик по файлу на полке** | Открыть файл в системе (`xdg-open`) |
| **Клик по крестику на полке** | Удалить файл из полки |
| **В «Оформлении»: зажать и тащить остров** | Свободное позиционирование: без клавиш = 1 px, с `Shift` = 10 px, с `Ctrl` = 50 px |
| **В «Оформлении»: стрелки клавиатуры** | Двигать остров: без клавиш = 1 px, с `Shift` = 10 px, с `Ctrl` = 50 px |

---

## <img src="https://img.shields.io/badge/Run-Quickstart-green?style=flat-square" height="20" /> Запуск и Диагностика

```bash
# Запустить остров (работает тихо в фоне):
island &

# Проверить систему и зависимости (если что-то не стартует):
island --doctor

# Посмотреть свежие логи:
island --log

# Запустить с выводом в терминал (дебаг-режим):
island --verbose
```

Короткое имя `island` — симлинк на лаунчер:

```bash
ln -sfn "$PWD/dynamic_island.py" ~/.local/bin/island
```

### Запуск конкретных экранов для тестов:
```bash
# Раскрытый плеер
island --view MediaBig

# Полка файлов
island --view Shelf

# Меню оформления
island --view Look

# Сразу запустить таймер на 90 секунд
island --timer 90
```

### Запустить проверку всех Roc-модулей:
```bash
./test_all.sh
```

---

## <img src="https://img.shields.io/badge/Setup-Autostart-purple?style=flat-square" height="20" /> Автозапуск в Hyprland / Sway

В `~/.config/hypr/hyprland.conf`:
```ini
exec-once = island &
```

Либо скопируй готовый `.desktop`:
```bash
mkdir -p ~/.config/autostart
cp dynamic-island.desktop ~/.config/autostart/
```

---

*Специально для Arch Linux Wayland. I use Arch btw.*
