# Builder Village Bot Logic

Этот документ описывает текущую логику деревни строителя по активному `config.json` и коду `coc_bot/main.py`, `coc_bot/builder_flow.py`, `coc_bot/vision.py`.

## 1. Запуск режима

Builder-режим запускается, когда `bot_mode = builder`.

Это можно сделать:

1. Через UI, выбрав `Builder base`.
2. Через CLI:

```powershell
.\.venv\Scripts\python.exe -m coc_bot.main --bot-mode builder
```

В `config.json` сейчас стоит `bot_mode = home`, поэтому без явного выбора запускается основная деревня.

При запуске `main()`:

1. Загружает активный `config.json`.
2. Создает `AdbDevice`, `VisionModule`, `BuilderBattleFlow`, `RecoveryModule`, `HealthChecker`.
3. Запускает LDPlayer.
4. Подключает ADB.
5. Запускает Clash of Clans.
6. Для builder-режима вызывает `run_builder_loop(...)`.

## 2. Главный цикл деревни строителя

`run_builder_loop(...)` работает бесконечно, пока оператор не остановит процесс или пока не достигнут `--max-attacks`.

Каждая итерация:

1. `health.check_before_cycle()`
   - Before `builder_flow.run_once()`, Telegram receives a pre-attack screenshot with caption `Before attack N`.
   - When the completed builder-attack counter reaches `60`, Telegram receives one one-time `60 attacks completed.` message.
2. `builder_flow.run_once()`
3. Увеличение счетчика завершенных builder-атак.
4. Если задан `max_attacks`, проверка лимита.
5. Пауза `cycle_delay_seconds = 2.0`.

Если возникает ошибка:

1. Бот пытается сохранить debug screenshot с причиной `builder-cycle-error`.
2. Ошибка передается в `recovery.recover(exc)`.
3. Recovery пытается восстановить LDPlayer, ADB и приложение.

## 3. Один builder-цикл

`BuilderBattleFlow.run_once()` выполняет шаги строго в таком порядке:

1. `dismiss_popups`
2. `wait_for_base`
3. `open_attack`
4. `wait_for_battle`
5. `deploy_slots`
6. `wait_and_return_home`
7. `dismiss_popups_after_return`

В начале каждого цикла сбрасывается счетчик builder overlay.

## 4. Закрытие попапов

`dismiss_popups()` использует один screenshot через `vision.frame()` и проверяет:

1. `vision.has_okay_button()`
2. если Okay не найден, `vision.has_configured_popup()`

Если найден Okay или popup, бот тапает:

- `okay_button_point = 50.32%,79.04%`

После тапа ждет:

- `tap_delay_seconds = 0.35`

Для builder это важно после star bonus и других окон, которые могут перекрыть кнопку атаки или возврат домой.

## 5. Ожидание builder-базы

`_wait_until_builder_base()` работает до тех пор, пока не увидит базу строителя.

В каждой итерации:

1. Сначала пробует закрыть попапы.
2. На одном screenshot проверяет `has_builder_attack_button()`.
3. Если attack не найден, проверяет `has_star_bonus_counter()`.
4. Если ни attack, ни star bonus не найдены, проверяет `has_builder_return_home_button()`.
5. Если найден attack-template, база считается найденной.
6. Если найден star bonus counter, база тоже считается найденной.
7. Если видна кнопка Return Home, бот тапает `builder_return_home_point`.
8. Если ничего не найдено, ждет `builder_state_poll_seconds = 1.0` и повторяет.

Шаблоны builder attack:

- `assets/templates/builder/attack_1.png`
- `assets/templates/builder/attack_2.png`
- `assets/templates/builder/base_attack_star_partial.png`
- `assets/templates/builder/base_attack_axes.png`
- `assets/templates/builder/base_attack_text.png`

Параметры поиска:

- threshold: `builder_attack_template_threshold = 0.78`
- area: `x 0..26`, `y 65..96`

## 6. Открытие атаки

`_open_attack()`:

1. Проверяет, что `builder_attack_taps` не пустой.
2. Тапает первую точку атаки:
   - `6.81%,88.78%`
3. Вызывает `_wait_and_tap_find_match()`.

`_wait_and_tap_find_match()`:

1. До `wait_attack_ready_seconds = 12.0` ищет кнопку Find Match.
2. Использует шаблон:
   - `assets/templates/builder/attack_2.png`
3. Параметры поиска:
   - threshold: `builder_find_match_template_threshold = 0.78`
   - area: `x 55..84`, `y 50..76`
4. Если шаблон найден, бот тапает реальные координаты найденного match.
5. Если не найден за 12 секунд, бот тапает fallback:
   - `74.50%,65.78%`
6. После тапа ждет `tap_delay_seconds = 0.35`.

## 7. Ожидание builder-боя

`_wait_until_builder_battle()`:

1. До `wait_battle_seconds = 14.0` проверяет `vision.has_builder_battle_marker()`.
2. Если battle marker найден, бой считается начатым.
3. Если marker не найден за 14 секунд, выбрасывается ошибка.

Шаблоны боя:

- `assets/templates/builder/battle_1.png`
- `assets/templates/builder/battle_2.png`
- `assets/templates/builder/battle_3.png`
- `assets/templates/builder/battle_4.png`

Параметры:

- threshold: `builder_battle_template_threshold = 0.78`
- area: весь экран

## 8. Быстрый деплой слотов

`_deploy_slots()` сначала вызывает `_rapid_deploy_slots_through_g()`.

Текущие builder troop slots:

1. `10.94%,88.89%`
2. `19.56%,89.44%`
3. `26.19%,89.22%`
4. `35.63%,88.67%`
5. `42.88%,88.44%`
6. `49.81%,88.33%`
7. `57.81%,88.67%`
8. `66.63%,88.56%`

Для каждого слота:

1. Бот тапает слот.
2. Потом тапает deploy/G-точку:
   - `builder_deploy_point = 9.69%,51.22%`
3. Между слотами ждет `rapid_deploy_tap_delay_seconds = 0.05`.

## 9. Соседние тапы вокруг builder deploy point

Включено:

- `deploy_neighbor_taps_enabled = true`
- `deploy_neighbor_offset_percent = 0.45`

Поэтому `builder_deploy_point` превращается в 5 точек:

1. `9.69%,51.22%`
2. `10.14%,51.22%`
3. `9.24%,51.22%`
4. `9.69%,51.67%`
5. `9.69%,50.77%`

Эти точки отправляются пачкой через `tap_many_percent`.

## 10. Проверка состояний слотов

После быстрого деплоя `_deploy_slots()` вызывает `_check_builder_slot_states()`.

Включено:

- `builder_slot_state_checks_enabled = true`
- `builder_slot_state_check_passes = 2`
- `builder_slot_state_check_delay_seconds = 0.25`

Для каждого прохода:

1. Бот берет screenshot.
2. Для каждого из 8 слотов вызывает `vision.detect_builder_slot_state(slot, screenshot)`.
3. Если после действия экран изменился, screenshot сбрасывается и берется новый.
4. Между слотами ждет `rapid_deploy_tap_delay_seconds = 0.05`.

Область проверки каждого слота строится от координаты слота:

- `x = slot.x - 4.5 .. slot.x + 4.5`
- `y = slot.y - 18.0 .. slot.y + 2.5`

Порядок определения состояния:

1. `ability_ready`
2. `not_deployed`
3. `deployed`
4. если ничего не найдено, `unknown`

Шаблоны:

- `assets/templates/builder/slots/ability_ready.png`
- `assets/templates/builder/slots/not_deployed.png`
- `assets/templates/builder/slots/deployed.png`
- `assets/templates/builder/slots/deployed_alt.png`

Threshold:

- `builder_slot_state_template_threshold = 0.78`

Действия по состояниям:

- `not_deployed`: бот снова тапает слот и deploy/G-точку.
- `ability_ready`: бот тапает слот, активируя способность.
- `deployed`: ничего не делает.
- `unknown`: ничего не делает, только логирует состояние.

## 11. Ожидание конца боя и возврат домой

После деплоя бот вызывает `_wait_and_return_home()`.

Общий лимит ожидания:

- `builder_battle_timeout_seconds = 240.0`

В цикле бот:

1. Проверяет `vision.has_builder_return_home_button()`.
2. Если кнопка Return Home найдена, тапает:
   - `builder_return_home_point = 50.38%,83.33%`
3. Ждет `tap_delay_seconds = 0.35`.
4. Завершает builder-цикл.

Шаблон Return Home:

- `assets/templates/builder/return_home.png`

Параметры:

- threshold: `builder_return_home_template_threshold = 0.78`
- area: `x 34..66`, `y 72..94`

Если Return Home не найден за 240 секунд, бот все равно тапает `builder_return_home_point`.

## 12. Повторный деплой во время боя

Включено:

- `builder_redeploy_slots_enabled = true`
- `builder_redeploy_slots_interval_seconds = 25.0`

Пока бот ждет Return Home, каждые 25 секунд он снова вызывает `_rapid_deploy_slots_through_g()`:

1. Проходит по всем 8 builder slots.
2. Тапает каждый слот.
3. Тапает deploy/G-точку с соседними точками.

Это нужно, чтобы добросить войска или активировать доступные слоты, если первая попытка не сработала.

## 13. Ретап первого слота

Настроено:

- `builder_first_slot_retap_interval_seconds = 7.0`
- `builder_first_slot_retap_enabled = false`

Код поддерживает ретап первого слота каждые 7 секунд, но сейчас эта функция выключена.

Если включить, во время ожидания конца боя бот будет периодически тапать:

- `builder_troop_slots[0] = 10.94%,88.89%`

## 14. Способность builder-героя

Включено:

- `builder_hero_ability_enabled = true`
- `builder_hero_ability_interval_seconds = 10.0`
- `builder_hero_ability_point = 5.70%,90.00%`

Во время ожидания Return Home каждые 10 секунд:

1. Бот проверяет `vision.has_builder_hero()`.
2. Использует шаблон:
   - `assets/templates/builder/slots/hero_present.png`
3. Параметры поиска:
   - threshold: `builder_hero_present_template_threshold = 0.72`
   - area: `x 0..12`, `y 66..100`
4. Если герой найден, бот тапает `5.70%,90.00%`.
5. Если герой не найден, бот пропускает тап и пишет это в лог.

## 15. Защита builder-тапов

В отличие от основной деревни, builder flow пропускает каждый тап через защиту:

1. `_calibrate_builder_tap(...)`
2. `_guard_builder_point(...)`
3. только потом ADB tap

Калибровка:

- `builder_calibration_enabled = true`
- `expected_screen_width = 1600`
- `expected_screen_height = 900`
- `builder_calibration_max_screen_drift_percent = 2.0`

Если размер screenshot отличается от ожидаемого больше чем на 2%, бот падает с ошибкой.

Overlay:

- `builder_tap_overlay_enabled = true`
- `builder_tap_overlay_dir = logs/calibration/builder`
- `builder_tap_overlay_max_per_cycle = 200`

Перед тапами бот может сохранять PNG overlay с активными точками, safe-area и forbidden-area.

## 16. Safe area и forbidden areas

Safe area:

- `x 0..100`
- `y 0..96`

Forbidden areas:

1. `x 72..100`, `y 78..100`
2. `x 82..100`, `y 58..78`
3. `x 0..8`, `y 0..18`

Если точка вне safe area или внутри forbidden area, бот выбрасывает `UnsafeBuilderTapError` и атака уходит в recovery.

## 17. После возврата домой

После нажатия Return Home бот снова вызывает `dismiss_popups()`.

Затем управление возвращается в `run_builder_loop(...)`:

1. Счетчик завершенных builder-атак увеличивается.
2. Если задан `--max-attacks`, проверяется лимит.
3. Бот ждет `cycle_delay_seconds = 2.0`.
4. Начинается следующий builder-цикл.

## 18. Что важно помнить

- Builder flow отдельный от основной деревни и находится в `coc_bot/builder_flow.py`.
- Он не использует обычный `deploy_plan`.
- Он использует 8 builder slots и одну deploy/G-точку.
- После стартового деплоя включена проверка состояния каждого слота.
- Во время боя включен redeploy всех 8 слотов каждые 25 секунд.
- Способность builder-героя проверяется и активируется каждые 10 секунд, если найден hero template.
- Builder taps защищены safe-area, forbidden-area и проверкой размера экрана.
