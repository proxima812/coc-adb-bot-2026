# Code Review — COC Bot ADB

Полный разбор кода бота автоматизации Clash of Clans на LDPlayer (ADB-first).
Документ собран по модулям: что делает, ключевые наблюдения, замечания, рекомендации и советы по оптимизации.

---

## 0. Общая архитектура

```
main.py            ── точка входа, парсинг CLI, выбор петли (home / builder / account-cycle)
config.py          ── BotConfig (frozen dataclass) + загрузка/валидация JSON
adb_device.py      ── обёртка над adb.exe (tap, swipe, hold, screenshot, ключи Win32)
vision.py          ── OCR (EasyOCR) + cv2.matchTemplate + детекция состояний и UI-кнопок
battle_flow.py     ── полный цикл атаки на главной деревне
builder_flow.py    ── цикл атаки на деревне строителя (guard + калибровка)
calibration.py     ── PNG-оверлеи (сетка, точки, зоны) для визуальной отладки
recovery.py        ── перезапуск LDPlayer + переподключение ADB + перезапуск приложения
emulator.py        ── запуск dnplayer.exe (LDPlayer)
health.py          ── проверка размера экрана и состояния игры перед циклом
account.py         ── переключение аккаунтов через настройки игры (3 предустановленных)
chat.py            ── (заглушка) отправка сообщения в клан-чат
search.py          ── (старый/неиспользуемый) поиск базы по состояниям
telegram_notify.py ── уведомления в Telegram через urllib
ui.py              ── Tkinter-GUI: запуск/стоп бота, лог, переключение аккаунтов
```

### Архитектурные плюсы

- Чистое разделение слоёв: устройство → зрение → бизнес-логика → UI.
- Все координаты — **относительные** (`RelativePoint` x/y в процентах) → разрешение экрана не ломает конфиг.
- Конфиг загружается из JSON, валидируется, есть fallback на `config.example.json`.
- Двойной лог: `logs/bot.log` (runtime) и `logs/actions.log` (только действия с `record["extra"]["action"]`).
- `dry_run` режим — действия в ADB логируются, но не отправляются.
- Guard `_guard_builder_point` блокирует тапы в запретные зоны (магазин и т.п.) — отличная защита.

### Архитектурные минусы

- В `main.py` создаётся **два** `BattleFlow` и `BuilderBattleFlow` сразу, хотя используется один. EasyOCR и шаблоны живут в общем `VisionModule`, но всё равно лишние объекты.
- `VisionModule` смешивает три ответственности: захват скриншота, шаблонный матчинг, OCR. Лучше разнести на `ScreenCapture`, `TemplateMatcher`, `OcrReader`.
- `BotConfig` — гигантский monolithic dataclass (≈110 полей). Тяжело читать, легко промахнуться. Просится разделение на `AdbConfig`, `VisionConfig`, `BattleConfig`, `BuilderConfig`, `LootConfig` и т.д.
- Отсутствует общая абстракция «состояние игры» как FSM. Логика «дождись X, попробуй Y» рассыпана по флоу.

---

## 1. `main.py`

### Что делает
Парсит CLI (`--max-attacks`, `--account-cycle`, `--attacks-per-account`, `--accounts`, `--bot-mode`),
инициализирует loguru, создаёт все модули, запускает LDPlayer, подключает ADB, запускает приложение и
переходит в одну из трёх петель: `run_home_loop`, `run_account_cycle`, `run_builder_loop`.

### Замечания
- В `run_*_loop` обработка исключения общая (`except Exception`) — если падает recovery, ловится снаружи только `KeyboardInterrupt`, остальное всплывает наверх и валит процесс. Это нормально, но стоит залогировать стек на ERROR явно.
- В `run_account_cycle` `device` передаётся параметром, но **не используется** в теле функции (см. строки 142–196). Можно удалить.
- `run_builder_loop` НЕ вызывает `health.check_before_cycle()` — рассинхрон с `run_home_loop`. Если эмулятор просядет посередине, builder узнает об этом только при следующем падении.
- Импорт `account.AccountSwitcher` сделан **внутри** функции — анти-паттерн, ради избегания циклической зависимости (account импортирует main). Стоит вынести `setup_logging` в отдельный модуль `logging_setup.py`, чтобы account и main импортировали один общий низкоуровневый модуль.
- Логгер: `logger.add(lambda message: print(message, end=""), level=log_level)` — обходное решение, использующее loguru-stream. Это работает, но удобнее `logger.add(sys.stderr, ...)`.

### Рекомендации
1. Вынести «универсальную атакующую петлю» в одну функцию с параметрами `flow`, `on_after_cycle`, `health`, `max_attacks`. Сейчас 3 почти одинаковых блока try/except.
2. Передавать `dataclass RunOptions` вместо длинного списка позиционных аргументов.
3. Сохранять метрики (gold/elixir/успешные/неудачные атаки) в JSONL, не только лог.
4. На SIGTERM (а не только KeyboardInterrupt) — корректно завершать процесс, чтобы UI/PowerShell-скрипт не оставлял зомби.

### Оптимизация
- В `run_home_loop` после `recovery.recover(exc)` нет паузы. Если ошибки повторяются мгновенно, лог забивается. Добавить мелкий back-off (exponential).
- `vision.save_debug_screenshot("cycle-error")` делает повторный `screenshot()`. У тебя только что был `screenshot()` внутри `detect_state()` — можно прокинуть последний кадр в исключение и переиспользовать его. Сэкономит 1 ADB-вызов на каждый сбой.

---

## 2. `config.py`

### Что делает
Определяет три dataclass — `RelativePoint`, `RelativeArea`, `BotConfig`, разбирает JSON в эти структуры,
жёстко валидирует диапазоны координат (0..100%), наличие шаблонов, длины списков
(`fallback_deploy_points` == 19), допустимые значения `deploy_mode`, `bot_mode`, `emulator_type`.

### Замечания
- Очень хорошо: `validate_config` падает с подробным списком ошибок. Это лучше, чем ловить опечатку в рантайме.
- Минус: жёсткое требование `len(fallback_deploy_points) == 19` хардкодит число G-точек кейкарты. Если будут изменения keymap, ломается конфиг.
- `_config_from_dict` копирует словарь и **мутирует** копию (`data = dict(raw)`). Если в `raw` встретится неизвестный ключ — `BotConfig(**data)` упадёт с TypeError, но без подсказки «какой ключ лишний». Лучше явно отфильтровать `data` по `BotConfig.__dataclass_fields__` или сообщить пользователю.
- `_point` принимает `dict | RelativePoint`, но не валидирует тип x/y до `float(...)`. Тестов нет.
- Поля типа `attack_template_path: str = ""` и `attack_template_paths: list[str] = []` — лишнее дублирование. Уже всё суммируется в `[path, *paths]` в `vision.py`. Можно оставить только списочную форму и упростить логику.
- Дефолты пути ADB прибиты к Windows (`D:\LDPlayer\...`) — это норм для целевого окружения, но плохо переносится на CI / тесты.
- Поля `okay_button_enabled`, `builder_first_slot_retap_enabled` и т.д. — много feature-flag'ов. Их следует группировать в подсекции конфига.

### Рекомендации
1. **Разбить `BotConfig` на подгруппы**:
   ```python
   @dataclass(frozen=True)
   class AdbConfig: ...
   @dataclass(frozen=True)
   class EmulatorConfig: ...
   @dataclass(frozen=True)
   class VisionConfig: ...
   @dataclass(frozen=True)
   class BattleConfig: ...
   @dataclass(frozen=True)
   class BuilderConfig: ...
   ```
   Это драматически уменьшит когнитивную нагрузку и позволит проще писать юнит-тесты.
2. Добавить поддержку **переопределения через ENV**, например `COC_DEVICE_SERIAL=...`. Для CI и переключения инстансов LDPlayer.
3. Сделать **JSON Schema** для конфига и автогенерацию из dataclass — отлично подружит `config.example.json` и код.
4. Заменить хардкод `19` на вычисляемый от настроек слот.
5. Подключить `pydantic` или `attrs` — улучшит валидацию и позволит описать union/optional.

### Оптимизация
- `validate_config` каждый раз обходит список путей и стучится в файловую систему (`Path(...).exists()`). На SSD недорого, но если шаблонов будет много, кеш через `lru_cache` ускорит запуск UI/тестов.

---

## 3. `adb_device.py`

### Что делает
- Обёртка над `adb.exe -s <serial>` (`run`, `run_bytes`, `host_run`).
- Tap/Swipe/Hold/TapPercent/TapMany/HoldMany (с пересчётом % в пиксели по `screen_size()`).
- Скриншот через `exec-out screencap -p` с тремя попытками.
- ParallelTap/Hold через `ThreadPoolExecutor` — несколько ADB-вызовов одновременно.
- Windows-only: pinch zoom через `ctrl + mouse wheel`, нажатия клавиш через `user32.keybd_event`,
  `EnumWindows` + `QueryFullProcessImageNameW` для поиска `dnplayer.exe`.

### Замечания
- **Огромная цена ADB**: каждый `adb shell input tap X Y` запускает новый процесс — ~30–80 мс на Win.
  При rapid-deploy с 24-точечным батчем это легко 1–2 секунды на ничто. ThreadPoolExecutor параллелит,
  но всё равно создаёт по процессу на тап.
- Скриншот через `screencap -p` отдаёт PNG в stdout. На 1920x1080 это ~5–8 МБ → передача ADB + декодирование PNG. На каждом цикле 3–10 скриншотов = очень дорого.
- `_screen_size` кешируется, но сбрасывается при `connect()` и `kill_server()` — корректно, +.
- `text(value)` использует `escape = value.replace(" ", "%s")` — некорректно для `#`, `$`, кавычек, юникода. Сейчас используется только для клан-чата (заглушка), но стоит починить.
- `connect()` ловит «unable» или «failed» в выводе, но adb пишет «already connected to ...» — это норм случай, и сейчас он проходит. Однако `adb connect` может вернуть код 0 даже при отказе. Стоит проверить `_screen_size` после connect через `getprop` и считать это финальным критерием успеха.
- `_action_log` дублирован между `adb_device.py` и `emulator.py` — мелочь, но лучше вынести в общий `logging_helpers`.

### Рекомендации
1. **Использовать persistent shell** через `adb shell` без `-c`, либо через `scrcpy`-подобный демон, чтобы не запускать процесс на каждый тап. Самое радикальное ускорение — поднять `adb shell sh` в фоновом subprocess и слать туда команды через stdin/stdout. Это превращает 50 мс/тап → 2–3 мс.
2. **Скриншоты через `minicap`** или `scrcpy --no-display` — десятки FPS вместо 2–5. Или хотя бы `screencap -p /sdcard/x.png && exec-out cat` тоже не лучше, поэтому идеален minicap.
3. **Альтернатива**: `uiautomator2`/`adbutils` через persistent connection (TCP к adb-серверу) — выгоднее, чем запуск adb.exe на каждое действие.
4. `screenshot()` сейчас ретраит при пустом ответе, но не отличает «эмулятор спит» от «ADB упал». Добавить distinction.
5. `pinch_zoom_out_percent` и `ctrl_mouse_wheel_zoom_out` — два разных способа зума. Оставить один (через ADB-свайп, потому что Win32-зум привязан к фокусу окна).
6. Кодировку команд для `input text` стоит писать через base64 → `am broadcast` или через `input text "$(echo ...)"` — текущая реализация поломается для русского.

### Оптимизация
- **Бакетирование тапов**: `input tap` можно заменить на `getevent`/`sendevent`, но проще — `input swipe X Y X Y 1` или массовый `input` через скрипт `sh -c "input tap ...; input tap ..."` за один запуск процесса. Один subprocess вместо 24 — экономия 1.5 секунды на батч.
- Кэшировать `_base_cmd()` (`Path(self.adb_path)` строится каждый раз). Не критично, но лишний syscall.
- При параллельных тапах `max_workers=len(pixel_points)` — на батче 24 это 24 потока. Лимитировать `min(24, 8)`.
- `screen_size()` — `adb shell wm size` тоже процесс. Достаточно одного вызова за сессию, кэш есть, ОК.

---

## 4. `vision.py`

### Что делает
- Делает скриншот через `device.screenshot()` → decode PNG → RGB ndarray.
- `detect_state()` определяет VILLAGE / BATTLE / UNKNOWN: ищет 4 шаблона (battle/next/attack/star_bonus),
  затем OCR'ит две зоны экрана.
- `_confirm_state` — счётчик подтверждений (`state_confirmations_required`) для устойчивого FSM.
- `find_template` / `_find_template_in_image` — `cv2.matchTemplate` с TM_CCOEFF_NORMED и threshold,
  с кропом по `RelativeArea`.
- `read_battle_loot` — OCR верхней-левой 42×34% зоны через EasyOCR (allowlist=цифры).
- `detect_deploy_boundary_points` — HSV+маски красного+белого+Canny+HoughLinesP, чтобы найти красную «границу деплоя».
- `_template_cache` — словарь {path: ndarray | None}, шаблон грузится один раз.
- `BuilderSlotState` — детекция состояния каждого слота (deployed / not_deployed / ability_ready) по шаблонам.

### Замечания
- **Очень много скриншотов на цикл**. `detect_state()` делает 1 скриншот, но потом `dismiss_popups()` → `has_okay_button()` → `find_template()` → новый скриншот. И так несколько раз подряд. Можно кратно сократить.
- В `dismiss_popups` сначала ищется okay-кнопка (по шаблонам с «okay» в имени), потом OCR `okay_button_detection_area`, потом отдельный проход `has_configured_popup` — ещё несколько скриншотов.
- Каждый `find_template()` грузит скриншот, **переводит RGB→BGR**, потом BGR→GRAY, **внутри** делает то же самое с шаблоном. На больших шаблонах это вычислительно дорого.
- `_load_template` хранит цветной BGR-шаблон, но `_best_template_match` приводит его к gray. Эффективнее хранить уже gray-версию.
- `state_confirmations_required` хорошая идея, но если состояние не подтвердилось — возвращается `_stable_state`. Это означает: первый запуск возвращает `UNKNOWN`, а после переходов «прилипает». В `health.check_before_cycle()` это потенциально маскирует свежий unknown.
- EasyOCR (`gpu=False`) — медленный (~200–500 мс на регион на CPU). Используется в `_read_screen_text` и `read_battle_loot`.
- `read_battle_loot` ищет минимум 2 числа > 100, иначе возвращает (0,0). Если OCR схватил мусор «12 345» → распознается как одно число «12345» (после `re.sub(r"\D", "", value)`), но изначально регекс `\d[\d\s,.]*` мог захватить пробелы и точки — fragile.
- `auto_deploy_boundary_points` — большой объём работы для функции, которая по умолчанию отключена (`auto_deploy_boundaries_enabled=False`). Если она не используется в проде, можно вынести в отдельный модуль `vision_boundary.py`.
- `_has_attack_button` пути ищется через `[attack_template_path, *attack_template_paths]` — пустые строки фильтруются позже. ОК, но дублирование.

### Рекомендации
1. **Single-shot screenshot per cycle step**: добавить метод `capture()` → ndarray + контекст-менеджер, и передавать одну «фрешку» во все детекторы.
   ```python
   with vision.fresh() as frame:
       if frame.has_battle_button(): ...
       if frame.has_next_button(): ...
   ```
   Сейчас каждый `has_*` делает отдельный скриншот. Это даёт **3–10x ускорение** цикла детекции.
2. **Кэш gray-шаблонов**:
   ```python
   self._template_cache[path] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
   ```
   и в `_best_template_match` принимать уже gray, экономя 2 cvtColor на каждый матч.
3. **OCR как последний рубеж**. Если шаблон сматчился — OCR не нужен. Сейчас в `detect_state` логика уже такая, но `is_attack_ready`, `has_okay_button` и др. идут через OCR в обход. Шаблоны кнопок «Find a Match», «Okay» давно есть в `assets/templates/popups/` — переключаться на них всегда быстрее.
4. **Подключить ROI-pyramid**: понизить разрешение скриншота вдвое (cv2.pyrDown), искать шаблон в пирамиде. На 1920x1080 это даст ×3 ускорение и устойчивость к небольшим сдвигам.
5. `read_battle_loot`: использовать **tesseract** через `pytesseract` с режимом `--psm 6 -c tessedit_char_whitelist=0123456789` — быстрее EasyOCR в разы для цифр. Или подключить compiled `cv2.dnn`-модель.
6. **Не запускать EasyOCR при cold start, если он не нужен** — сейчас `self.reader` ленивая, ок. Но `easyocr.Reader([...])` грузит ~600 МБ моделей. Если бот никогда не делает OCR, грузить не надо. Перевести `state_ocr_*_area` в опциональный режим: `prefer_templates_only=True` → не подключать easyocr.
7. **`_confirm_state` багфикс**: при первом запуске `_stable_state == UNKNOWN`, если приходит чистый `VILLAGE`, candidate увеличивается, и до подтверждения возвращается `UNKNOWN`. Это нормально, но health-проверка может несколько секунд видеть UNKNOWN. Сделать первый VILLAGE/BATTLE сразу stable (без подтверждения), пока не было ни одного перехода.
8. Шаблоны хранить в **assets** вместе с мета-файлом порога (json sidecar), а не сыпать `threshold` в конфиг.

### Оптимизация
- **Перейти на TM_SQDIFF_NORMED** для шаблонов одинакового размера — иногда устойчивее к освещению, обратите внимание на min/max инверсию.
- **Перейти на uint8-маску `cv2.matchTemplate`** с RGB и mask, если требуется альфа на шаблоне.
- Объединить детекторы попапов в одну функцию: вызывать `cv2.matchTemplate` для одного скриншота против всех шаблонов в одном цикле, переиспользуя gray-кадр.

---

## 5. `battle_flow.py`

### Что делает
Цикл атаки на главной деревне:
1. `dismiss_popups` — закрыть Okay/попапы.
2. `_open_battle_from_base` — последовательные тапы по `base_attack_taps`.
3. `_wait_until_acceptable_battle` — ждать состояния BATTLE, опционально OCR loot и сравнить с порогом.
4. `_prepare_battle_camera` — Ctrl+колесо для zoom-out, затем калибровочный оверлей (опционально).
5. `_deploy_army` — два режима:
   - `templates`: ищет каждый `DeployTarget` по шаблону и тапает.
   - `coordinates` (по умолчанию): идёт по `deploy_plan`, для каждого шага выбирает слот, потом «выливает» по primary point + параллельные «соседние» точки (G-points + ±offset).
6. `_activate_hero_abilities` — тапы по слотам героев перед заклинаниями.
7. `_deploy_random_points` — случайные точки в `spell_deploy_area` для спеллов.
8. `_finish_and_return_home` — End Battle → Confirm → Return Home.

### Замечания
- Логика умная: «расширение соседями» (`_with_neighbor_points`) и «батчи по 24» (`_tap_neighbor_batches`) — оптимизация для быстрой раскидки.
- Hold-режим (`deploy_hold_seconds > 0`) — для героев и боевой машины (длительный «свайп» в одну точку).
- `_wait_until_battle` ждёт BATTLE до `wait_battle_seconds` (14 с) с шагом 1 с. Это блокирующий poll.
- `troop_marker_check_during_burst` — ищет маркер «всё развёрнуто» во время burst, но `has_troops_deployed_marker()` делает новый скриншот → тормозит каждую итерацию burst. По дефолту выключено — правильно.
- `_read_loot_with_retries` возвращает `best`, но в редких случаях `best is None` — сейчас гарантировано не None (loop запускается хотя бы раз), но проверка типизатора не пройдёт.
- `_open_battle_from_base` — тапы по 3 точкам подряд с `base_search_tap_delay_seconds=0.5`. Лишний скриншот не делается — ОК.
- `_deploy_step_to_primary_and_fallbacks` имеет неоднозначную ветку:
  - Если `step.deploy_hold_seconds > 0` и `step.deploy_point_group == "primary"` — выход без burst (это первый «слив»).
  - Иначе делает hold + всё равно идёт в burst через `_tap_neighbor_batches`. Точно так задумано?
- `burst_duration_seconds = 1.0 if step.deploy_point_group == "troops" else 0.0` — для не-троопов burst идёт без задержки между батчами, что хорошо для скорости.
- `_finish_and_return_home` — 3 фиксированных тапа. Если поп-ап Star Bonus вылез между ними — он не закрывается. Опасное место.
- Логи на каждом шаге **очень многословные**. На обычном цикле выходит ~50 INFO-строк. Хорошо для отладки, плохо для long-run.

### Рекомендации
1. **Сделать FSM**: явно описать состояния (`Idle → InVillage → SearchingBase → AcceptedBattle → Deploying → WaitingResult → ReturningHome`). Сейчас «дождись X, потом сделай Y, потом тапни Z» — императивно и хрупко. FSM позволит лучше восстанавливаться после сбоев.
2. **Закрытие попапов между ключевыми шагами**. После `_finish_and_return_home` уже вызывается `dismiss_popups`, но между Confirm и Return Home надо тоже. Можно добавить retry-обёртку «попробуй тапнуть → если экран не сменился через N сек → попробуй снова».
3. `_deploy_army_by_templates` использует те же `tap` API, что и mode coordinates, но не вызывает `_tap`, а напрямую `device.tap()` для одного pixel-tap. Сделать единый интерфейс.
4. Loot retry: вместо `time.sleep(0.5)` между OCR-попытками — сделать первый OCR немедленно, а второй после кропа другого региона/масштаба, чтобы повысить разнообразие гипотез.
5. **Параметризовать `wait_until_battle`** не фиксированным `time.sleep(1)`, а коротким опросом 200 мс с экспоненциальным back-off, чтобы быстрее реагировать на быстрые экраны.
6. Если `loot_check_enabled=False` (по дефолту) — `_wait_until_acceptable_battle` всё равно сразу возвращает True. Имеет смысл также проверять, что это не PvE/обучение.
7. Логи: завести `logger.bind(cycle_id=...)` чтобы группировать сообщения одной атаки.

### Оптимизация
- `_deploy_step_to_primary_and_fallbacks`: при `step.deploy_hold_seconds > 0` происходит ещё `_tap_neighbor_batches` после hold (если не primary). Уточнить — если на самом деле нужно только для троопов с heroes-группой? Лишние тапы по 19 точкам ускоряют всё, но в логах действительно мусор.
- `_with_neighbor_points` строит до 19×5=95 точек на каждый burst → батчей 4 по 24. Это много `input swipe`/`input tap`. Если перенести на «persistent adb shell» (см. рекомендацию по `adb_device.py`), время burst упадёт в 3–4 раза.
- Кэшировать `self.config.fallback_deploy_points` → `tuple` чтобы не пересчитывать список соседей каждый раз (или закешировать `_with_neighbor_points` через `functools.lru_cache(maxsize=1)` по id-listу).
- `_hold_neighbor_batches` — `batch_size=12` (меньше из-за длительности hold). На стороне эмулятора параллельных гестур ограничено числом тач-указателей (обычно 10). 12 уже на пределе. Лучше 8.

---

## 6. `builder_flow.py`

### Что делает
Цикл деревни строителя:
1. `dismiss_popups` → `_wait_until_builder_base` (атака/star_bonus/return_home).
2. `_open_attack`: тап «Attack», затем ждать Find Match (шаблон) и тапнуть его центр.
3. `_wait_until_builder_battle` — ждать билдер-маркер боя.
4. `_deploy_slots` = `_rapid_deploy_slots_through_g` + `_check_builder_slot_states` (несколько проходов).
5. `_wait_and_return_home`: пока не появилась Return Home, периодически повторно деплоить + активировать ability героя.
6. Везде гарды: `_calibrate_builder_tap` (создаёт PNG оверлей) и `_guard_builder_point` (бросает `UnsafeBuilderTapError` если попадаем в `builder_forbidden_tap_areas`).

### Замечания
- Гарды — **отличный паттерн** для дебага и защиты от вылета случайных тапов в магазин. Это спасало бы аккаунты.
- `_check_builder_screen_size` падает, если экран дрейфанул >2%. Жёстко, но правильно для билдера, где случайный тап опасен.
- `_calibrate_builder_tap` сохраняет PNG **на каждый tap** при `builder_tap_overlay_enabled=True`. Это съест диск на длительной сессии. Лимит `builder_tap_overlay_max_per_cycle` (200) защищает, но 200 PNG за цикл — ~200 МБ.
- Дублирование `_with_neighbor_points` — точная копия из `battle_flow.py`. Просится `vision/deploy_utils.py`.
- `_rapid_deploy_slots_through_g` тапает слот, затем тапает Builder Deploy Point (с соседями). Между ними `time.sleep(rapid_deploy_tap_delay_seconds)`. ОК.
- В `_wait_and_return_home` логика «таймеров» вручную через `time.monotonic()`. Хорошо. Но если все 3 опции выключены — цикл крутится впустую до таймаута. Не страшно (1 секунда poll).
- `_open_attack` ждёт Find Match в `wait_attack_ready_seconds`, не нашёл → fallback тап во вторую точку. ОК.

### Рекомендации
1. **Снести дубликат** `_with_neighbor_points` в общую утилиту.
2. Сделать `_calibrate_builder_tap` опциональным с **семплингом** — сохранять 1 PNG на N тапов, либо только при первом тапе нового слота. Сейчас при `max_per_cycle=200` всё равно много.
3. `_check_builder_slot_states` делает скриншот **для каждого** слота (8 раз за проход) — крайне дорого. Сделать один скриншот и проверить все 8 областей по нему.
   ```python
   frame = self.vision.screenshot_array()
   for slot in slots:
       state = self.vision._detect_slot_state_in(frame, slot)
   ```
4. Поднять `builder_battle_timeout_seconds=240` до runtime-проверки: если игра подсказывает 3 минуты — нет смысла ждать 4.
5. `_wait_until_builder_base` — бесконечный цикл без таймаута. Если состояние «зависло» — будет крутиться вечно. Добавить watchdog (max 2 мин) → бросить и дать recovery шанс.
6. `_open_attack` использует `builder_attack_taps[0]` напрямую, без `_calibrate_builder_tap`? Нет, `_tap()` вызывается → калибровка делается. ОК.

### Оптимизация
- **Один скриншот вместо 8 для slot-state**: даст 8× ускорение state-проверки.
- `screenshot_array()` дорогая операция; в `_calibrate_builder_tap` она вызывается **до** каждого тапа (для оверлея и проверки размера). При `overlay_enabled=False` и `calibration_enabled=False` ранний return — ОК. Но при `overlay_enabled=True` — 200 скриншотов и 200 PNG на цикл. Это сожрёт время сильнее, чем сама атака.

---

## 7. `vision.py` — детали по детекциям билдера

(перекрытие с разделом 4, но специфично для builder)

- `detect_builder_slot_state(slot)` делает `screenshot_array()` каждый вызов → 8 за проход × N проходов.
- `_builder_slot_state_area` вычисляется от `slot.x ± radius_x` и `slot.y + offset`. Хорошая параметризация.
- `has_builder_*` — все через `_find_any_template` (отдельный скриншот на каждый шаблон).

→ Рекомендация: единый метод `detect_builder_screen()` возвращает namedtuple/dict со всеми флагами разом, из одного кадра.

---

## 8. `calibration.py`

### Что делает
Рисует на скриншоте: сетку %, область заклинаний, G-точки, slot-точки, builder-зоны (safe, forbidden, attack, slots, deploy, home, active). Использует PIL+`ImageDraw`.

### Замечания
- Чисто, хорошо именованные приватные методы.
- `_label` использует `ImageFont.load_default()` — на каждом рендере. Можно один раз закэшировать.
- `_draw_grid` с шагом `calibration_overlay_grid_step_percent` идёт `while value <= 100.0` через `+= step` (float-арифметика). Возможны накопления ошибок. Лучше `range(int(100/step)+1)`.
- В builder-оверлее имя файла включает `%f` (микросекунды) — хорошо, не будет коллизий при быстром потоке.
- В builder-оверлее **зеленая ACTIVE-метка перекрывает всё остальное** — хорошо, видимо.

### Рекомендации
1. Опционально сохранять оверлей в **JPEG q=85** или WebP — PNG скриншот 1080p ~5 МБ, оверлей будет ~2 МБ. JPEG сократит на порядок. Качество для дебага достаточно.
2. Шрифт `load_default()` мелкий и трудночитаемый. Загружать TTF из ассетов: `ImageFont.truetype("assets/fonts/Inter.ttf", 14)`. Опционально.
3. Добавить «легенду» в углу: что означает каждый цвет.

### Оптимизация
- Если на цикл рисуется до 200 оверлеев (builder), стоит **переиспользовать базовый кадр** (с уже нарисованной сеткой и зонами) и только добавлять active-точку. Сейчас всё перерисовывается с нуля.

---

## 9. `recovery.py`

### Что делает
При сбое: до `max_recovery_attempts` (3) раз — запустить LDPlayer, переподключить ADB (5 попыток),
force-stop приложение, перезапустить, проверить ADB. При неудаче — `RuntimeError`.

### Замечания
- Чистый, простой. Хорошо логируется.
- `recover` пишет полный traceback (`logger.exception`) — отлично.
- Создаёт **новый** `EmulatorLauncher` в конструкторе — дублирование с main.py. Лучше принимать готовый объект через DI.
- Если первая попытка восстановления съела все 3 ретрая — на следующий тик в `run_home_loop` мы упадём, recovery бросит, и цикл рухнёт. Стоит уведомлять Telegram о фатальной ошибке.
- `_connect_with_retries` — 5 ретраев. Если ADB действительно сдох, это 5 × 8 с = 40 с простоя. Допустимо.

### Рекомендации
1. **Уведомление в Telegram** при `RuntimeError("Recovery failed after max attempts")`.
2. **Adaptive backoff**: если первый recovery быстро дал результат — можно ускорить второй; если падает регулярно — увеличить delay.
3. **Журналирование причин**: сохранять стек последних N сбоев в JSON, чтобы видеть тренды.
4. **Health-чек после recovery**: вызывать `health.check_before_cycle()` сразу, чтобы убедиться, что игра ожила, а не просто ADB.

---

## 10. `emulator.py`

### Что делает
Стартует `dnplayer.exe` (LDPlayer) с опциональным `--index`. Ждёт `restart_delay_seconds`. `start_and_connect` — start + `device.connect()`.

### Замечания
- DI через `popen`/`sleep` — приятно, проверено тестами.
- `start()` возвращает `False` если бинарь не найден — нормально.
- На macOS/Linux это не работает (LDPlayer Windows-only). Согласовано с AGENTS.md.

### Рекомендации
1. **Не стартовать заново, если эмулятор уже запущен** — проверять процесс по имени до запуска. Сейчас `Popen` создаст дубликат, если уже запущено. LDPlayer обычно сам перехватит, но это бажный момент.
2. Логировать PID запущенного процесса.
3. После старта — опрашивать ADB до появления устройства (active wait < `restart_delay_seconds`), а не глухой `sleep`. Сэкономит время холодного старта.

---

## 11. `health.py`

### Что делает
Перед циклом: ADB-чек, размер экрана, не пустой ли скриншот, состояние не UNKNOWN.

### Замечания
- Простая и нужная защита.
- `_check_screen_size` строго: `!=` от `expected_*`. Один пиксель различия → исключение. Лучше использовать ту же логику дрейфа, что в builder (`builder_calibration_max_screen_drift_percent`).
- Падает в RuntimeError при unknown state. В `run_home_loop` это попадёт в recovery — хорошо. В `run_builder_loop` `health` вообще не вызывается — несоответствие.

### Рекомендации
1. Применить health-чек и в builder.
2. Допустить `screen_size` дрейф в %.
3. Добавить проверку **уровня заряда батареи** эмулятора (бывает, что эмулятор показывает заряд, который влияет на UI). На самом деле для COC не критично, но полезно для мониторинга.

---

## 12. `account.py`

### Что делает
CLI `python -m coc_bot.account proxima` — последовательность тапов: settings → change account → конкретный аккаунт.

### Замечания
- `ACCOUNT_POINTS` — хардкод 3 имён. Если добавить 4-й аккаунт, нужно править код И конфиг.
- Вызывает `from .main import setup_logging` — циклика, см. замечание к `main.py`.
- Использует ADB напрямую без вызовов `vision` — рискует переключиться «вслепую» (если игра показала попап).

### Рекомендации
1. Сделать **список аккаунтов в конфиге** как `list[AccountSlot(name, point)]`, а не три отдельных поля.
2. **Дожидаться экрана настроек** (по шаблону) перед нажатием Change Account.
3. Перед switch — `dismiss_popups`.
4. Логировать результат смены (можно через `vision.detect_state()`).

---

## 13. `chat.py`

### Что делает
Заглушка отправки сообщения в клан-чат (`tap → tap → text → keyevent 66 (Enter)`).

### Замечания
- **Не используется** в main/UI — мёртвый код.
- Координаты `(55, 365)` и `(310, 705)` — пиксельные, не относительные. На разных разрешениях не сработает.

### Рекомендации
1. Либо доделать (привязать к `RelativePoint`, протестировать, подключить в UI), либо удалить.
2. Если оставлять — переписать на `tap_percent` и шаблонный поиск иконки чата.

---

## 14. `search.py`

### Что делает
Старый поиск базы: переключает по состояниям VILLAGE/BATTLE, тапает фиксированные пиксельные точки.

### Замечания
- **Не используется** в `main.py` (нет импорта). Мёртвый код.
- Координаты тоже пиксельные, устаревшие.

### Рекомендации
1. Удалить или переписать под актуальный `BattleFlow`-поток.

---

## 15. `telegram_notify.py`

### Что делает
Загрузка `.env`, отправка сообщения через Telegram Bot API (`urllib`). Если `chat_id` не задан — пробует получить из `getUpdates`.

### Замечания
- Хорошо: stdlib only, никаких зависимостей `python-telegram-bot`.
- `_latest_chat_id` берёт последнее сообщение из `getUpdates` — это разово, но если у бота много чатов, пойдёт не туда. Стоит указать в README, что лучше задать `TELEGRAM_CHAT_ID` явно.
- Текст сообщения не экранируется. Для plain text ОК. Для Markdown — упадёт на скобках.
- Длинные сообщения (>4096) обрежутся API. В `run_account_cycle` финальное письмо может стать длинным.

### Рекомендации
1. Перевести на `requests` или `httpx` — единообразнее с возможным расширением (timeouts, retries).
2. Добавить **retry с экспоненциальным back-off** на сетевые ошибки.
3. Чанковать длинные сообщения (>4000 символов).
4. Поддержать MarkdownV2 (полезно для статистики).
5. Логировать `chat_id` после успешной отправки для self-doc.

---

## 16. `ui.py` (Tkinter)

### Что делает
Локальное GUI:
- Тёмная тема (color tokens в `UiTheme`).
- Кнопки: 25x3 accounts, Start, Stop, Restart, Clear log.
- Радио-выбор режима (Home / Builder).
- 3 кнопки переключения аккаунта.
- Лог-вьювер с цветными тегами (info/error/warn/...).
- `BotProcessController` — subprocess.Popen бота, terminate/wait/kill.

### Замечания
- Удобный, аккуратный код. Стили вынесены в `_configure_styles`.
- `_log_tag_for_line` — наивный маркер «есть слово warning → красить». Работает, но «started» и «running» оба info, а «attack» тоже info — много шума.
- `read_new_log` — tail-like (через size + seek). Если лог ротейтится (loguru делает rotation на 5 МБ) — `size < self._last_log_size` сработает, сбросит позицию. Это норм, но **потеряет** последние ~5 МБ старого файла.
- `BotProcessController.switch_account` стартует subprocess account.py отдельно — нет ждущего поведения, нет проверки результата.
- Кнопка 25x3 жёстко вызывает `account_cycle=True, bot_mode="home"`. Если оператор выбрал «Builder» — будет конфликт. Стоит дизейблить кнопку при `bot_mode=builder`.

### Рекомендации
1. Перевести UI на **PySide6 / Qt** — больше плюшек (тулбары, статусбар, тосты), лучше темизация.
2. Добавить **dashboard**: счётчик атак, среднее время цикла, последний loot — берётся из `actions.log` или JSONL-метрик.
3. Кнопка «Open logs folder» / «Open screenshots folder».
4. Возможность редактировать `config.json` из UI (или хотя бы открыть в редакторе).
5. **Сохранять выбор `bot_mode` между сессиями** в `~/.coc_bot_ui.json`.

### Оптимизация
- `read_new_log` каждые 1000 мс открывает файл, читает чанк. На 5 МБ это нормально. Если лог растёт быстрее — увеличить интервал или переключиться на watcher (`watchdog`).
- `_insert_log_text` итерирует по `splitlines(keepends=True)` и вызывает `insert` на каждую строку — много операций Tkinter. Лучше копить, вставлять одним `insert`, потом применять теги по диапазонам.

---

## 17. Тесты (`tests/`)

### Что есть
- `test_builder_flow_guard.py` — много тестов на builder: гарды, slot states, retry, hero ability, calibration.
- `test_calibration_overlay.py` — оверлеи рисуются и сохраняются.
- `test_emulator_launcher.py` — старт LDPlayer с DI.
- `test_ui_controller.py` — start/stop/restart процесса.

### Замечания
- Тесты компактные, используют FakeDevice/FakeVision/FakeProcess — отлично.
- Покрытие очень **узкое**: нет тестов на:
  - `vision.py` (template matching, state confirmation, OCR, slot state detection).
  - `battle_flow.py` (deploy plan, hero abilities, spells, loot retry).
  - `config.py` (`validate_config` ошибки, `_config_from_dict` парсинг).
  - `recovery.py`.
  - `telegram_notify.py`.

### Рекомендации
1. Добавить **тест-карты** для template matching: подавать собранные real-скриншоты как fixture и проверять, что шаблон ищется в нужной зоне.
2. Тесты на `_confirm_state`: задать последовательность raw состояний и проверить, что `_stable_state` корректно меняется.
3. Тест на `validate_config` для каждой проверяемой ошибки.
4. Property-based тесты для `RelativeArea.contains` и `random_point` (Hypothesis).
5. Подключить `pytest` + coverage (`pytest-cov`), отдельную команду `dev.ps1 test`.
6. CI на GitHub Actions: lint + tests на push.

---

## 18. Инструментарий и инфраструктура

### `tools/dev.ps1`
- Хорошо параметризован, валидирует команды.
- `Ensure-Python` ставит зависимости каждый раз (`pip install -r requirements.txt`) — медленно. Заменить на `pip install --upgrade-strategy only-if-needed` или кешировать markerом `.venv/.installed`.
- Доктор-команда хороша. Добавил бы `tools/dev.ps1 metrics` для агрегата по `actions.log`.

### `requirements.txt`
- Без пиннинга версий → недетерминированный билд. Минимум — `==` или `>=,<` для opencv/easyocr/numpy.
- EasyOCR тянет torch (~2 ГБ) → утилизация диска. Если нужен только OCR цифр — подумать о tesseract/pytesseract (~100 МБ).

### `config.example.json` (14 КБ)
- Не читал содержимое, но судя по дефолтам в `BotConfig` — там должно быть `loot_check_enabled: false`, `bot_mode: home`. Стоит держать в README таблицу «какие поля в config.example.json меняют поведение бота сильнее всего».

### `start.bat` / `start-ui.bat`
- Стандартные виндовые лаунчеры. ОК.

---

## 19. Безопасность и устойчивость

- **Тайминги жёстко в коде/конфиге**. Если игра обновится и сместит UI, бот не адаптируется. Шаблонный подход + калибровка помогают, но retry-логика всё равно слабая.
- **Random в координатах** (`spell_deploy_area.random_point()`, random_taps_min..max) — хорошо для антибота. Стоит добавить **jitter** ко всем тапам (±0.3% от точки), чтобы движения не были механически идентичными. Это снижает риск детекции и повышает устойчивость к смещениям UI.
- **Защита от блокировки аккаунта**: бот сейчас работает 24/7 без перерывов в конфиге. Добавить «спать N часов в M часов» расписание для имитации сна.
- Telegram-токен/chat_id в `.env` — нормально, но `.env` хорошо бы заигнорить в `.gitignore` (надо проверить).

---

## 20. Сводный TOP-список рекомендаций

### Что даст наибольший эффект (по убыванию)

1. **Persistent ADB shell** (один процесс `adb.exe` с stdin/stdout) → 5–10× ускорение тапов и серий burst. Это самое большое узкое место.
2. **Один скриншот на шаг детекции** (метод `vision.capture()` + переиспользование кадра во всех проверках) → 3–5× ускорение цикла детекции попапов и слотов билдера.
3. **Кэш gray-шаблонов** + ROI-пирамида в `_best_template_match` → 2–3× ускорение `matchTemplate`.
4. **Снизить нагрузку на OCR**: переключиться на шаблоны для Okay/Find a Match/состояний, оставить OCR только для loot. Освобождает CPU и время холодного старта.
5. **FSM-обёртка** для битвы + builder. Меньше «надежды на тайминги», быстрее восстановление.
6. **Разделить `BotConfig`** на тематические dataclass'ы → читать, поддерживать и валидировать проще.
7. **Антибан-меры**: jitter на координаты, сон по расписанию, рандомные паузы.
8. **Один screenshot для 8 слотов билдера** в `_check_builder_slot_states` → 8× ускорение проверки.
9. **Telegram alert** на recovery-failure, превышение N подряд ошибок.
10. **Пиннинг версий** в `requirements.txt`. Иначе очередной релиз opencv положит бота.

### Что даст качество кода

1. Удалить мёртвый код (`chat.py`, `search.py`).
2. Вынести общие хелперы (`_with_neighbor_points`, `_action_log`) в общий модуль.
3. Тесты на `vision`, `battle_flow`, `config.validate_config`.
4. CI (GitHub Actions) с линтером (`ruff`/`black`/`mypy`) и `pytest`.
5. Заменить EasyOCR на pytesseract для цифр (меньше диск, быстрее).

### Что закроет операционные риски

1. Watchdog/таймауты в `_wait_until_builder_base` и других «infinite poll».
2. Adaptive backoff в recovery.
3. JSONL-метрики (атаки/loot/ошибки) для дашборда.
4. Уведомления в Telegram о фатальных событиях.
5. Health-чек после recovery (а не только до цикла).

---

## 21. Карта потенциальных узких мест (perf hotspots)

| Где | Что тормозит | Сколько примерно | Лечится |
|-----|--------------|------------------|---------|
| Каждый `device.tap()` | запуск `adb.exe` | 30–80 мс | persistent shell |
| `screenshot()` | `screencap -p` + PNG decode | 150–400 мс | minicap / уменьшение разрешения |
| `_best_template_match` | `matchTemplate` на 1080p | 30–80 мс на шаблон | gray кэш + pyrDown |
| `easyocr.Reader` cold start | загрузка моделей | 3–8 с | ленивая, OK; убрать если не нужно |
| `_check_builder_slot_states` | 8 скриншотов × N проходов | 1.5–3 с | один скриншот для всех слотов |
| `_calibrate_builder_tap` при overlay=True | PIL render + PNG save | 100–250 мс | сэмплинг, переиспользовать base canvas, JPEG |
| `dismiss_popups` | 2–3 шаблона + OCR | 0.5–1.5 с | пере-юз кадра, выкинуть OCR |

---

## 22. Минимальный план миграции (если делать всё сразу нельзя)

**Спринт 1** (1–2 дня): persistent ADB shell + single-screenshot detection. Даст 5–10× ускорения практически бесплатно.

**Спринт 2** (1 день): кэш gray-шаблонов + объединённая проверка builder slots по одному кадру.

**Спринт 3** (1 день): jitter координат + расписание сна + Telegram-алерты на фатал.

**Спринт 4** (2 дня): декомпозиция `BotConfig` + расширение тестов на vision/battle_flow.

**Спринт 5** (по необходимости): FSM-рефакторинг, UI на Qt, дашборд.

---

## 23. Итог

Проект **зрелый и продуманный**: ADB-first, относительные координаты, ленивые модели, гарды,
многоуровневые логи, калибровочные оверлеи, аккаунт-цикл, Telegram — всё это редко встречается в любительских ботах.

Главные системные слабости:
- ADB на каждый тап = главный perf-потолок.
- Слишком много скриншотов «на всякий случай».
- Гигантский `BotConfig`.
- OCR используется там, где хватило бы шаблонов.
- Recovery без эскалации.

Эти пять пунктов закроют 80% потенциала ускорения и стабильности.
