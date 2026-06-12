# Main Village Bot Logic

Этот документ описывает текущую логику основной деревни по активному `config.json` и коду `coc_bot/main.py`, `coc_bot/battle_flow.py`, `coc_bot/vision.py`.

## 1. Запуск режима

1. `coc_bot.main` загружает конфиг через `load_config()`.
2. Так как в корне есть `config.json`, активен именно он. `config.example.json` используется только если `config.json` отсутствует.
3. Создаются основные модули:
   - `AdbDevice`
   - `VisionModule`
   - `BattleFlow`
   - `BuilderBattleFlow`
   - `RecoveryModule`
   - `HealthChecker`
   - `EmulatorLauncher`
4. Запускается LDPlayer и ADB-подключение.
5. Выполняется `device.check()`.
6. Запускается Clash of Clans package `com.supercell.clashofclans`.
7. Если выбран `bot_mode = home`, запускается `run_home_loop(...)`.

Текущий `bot_mode` в `config.json`: `home`.

## 2. Главный цикл основной деревни

`run_home_loop(...)` работает бесконечно, пока оператор не остановит процесс или пока не достигнут `--max-attacks`.

Каждая итерация:

1. `battle_flow.dismiss_popups()`
2. `health.check_before_cycle()`
3. `battle_flow.run_once()`
4. Увеличение счетчика завершенных атак.
5. Если задан `max_attacks`, проверка лимита.
6. Пауза `cycle_delay_seconds = 2.0`.

Если возникает ошибка:

1. Бот пытается сохранить debug screenshot с причиной `cycle-error`.
2. Ошибка передается в `recovery.recover(exc)`.
3. Recovery пытается восстановить LDPlayer, ADB и приложение.

## 3. Один цикл атаки

`BattleFlow.run_once()` выполняет шаги строго в таком порядке:

1. `dismiss_popups`
2. `open_battle_from_base`
3. `wait_for_battle`
4. `prepare_battle_camera`
5. `deploy_army`
6. ожидание после деплоя
7. `finish_and_return_home`
8. `dismiss_popups_after_return`

## 4. Закрытие попапов

`dismiss_popups()` использует один screenshot через `vision.frame()` и проверяет:

1. `vision.has_okay_button()`
2. если Okay не найден, `vision.has_configured_popup()`

Если найден Okay или настроенный popup, бот тапает:

- `okay_button_point = 50.32%,79.04%`

После тапа ждет:

- `tap_delay_seconds = 0.35`

Шаблоны попапов берутся из `popup_templates`, включая star bonus, builder star bonus, green okay и hero skin popup.

## 5. Открытие поиска боя

`_open_battle_from_base()` теперь сначала делает ранний тап открытия и между точками `A` и `F` проверяет кнопку `FREE`.

Текущая схема:

1. Тапает первую точку из `base_attack_taps`:
   - `6.88%,87.33%`
2. Тапает вторую точку из `base_attack_taps`:
   - `16.75%,73.22%`
3. Проверяет `FREE` по шаблону:
   - `assets/templates/state/free_button.png`
   - threshold: `0.78`
   - область: `x 0..30`, `y 55..86`
4. Если `FREE` найден, выполняет сбор:
   - `home_free_open_point = 16.75%,73.22%`
   - `home_free_collect_point = 83.63%,80.22%`
   - `home_free_close_point = 62.81%,69.44%`
5. Если `FREE` не найден, сбор пропускается.
6. После этого стартует бой через:
   - `home_attack_start_point = 89.56%,88.67%`

Между тапами пауза:

- `base_search_tap_delay_seconds = 0.5`

Старое последовательное нажатие всех `base_attack_taps` используется только если выключить `home_free_check_enabled`.

## 6. Ожидание экрана боя

`_wait_until_acceptable_battle()` сначала вызывает `_wait_until_battle()`.

`_wait_until_battle()`:

1. До `wait_battle_seconds = 14.0` опрашивает `vision.detect_state()`.
2. Если состояние стало `battle`, бой найден.
3. Если за 14 секунд бой не найден, возвращает `False`, а `run_once()` падает с ошибкой.

`vision.detect_state()` определяет состояние так:

1. Ищет battle/end-battle template.
2. Ищет next template.
3. Ищет attack template.
4. Ищет star bonus counter.
5. Если шаблоны не помогли, читает OCR зоны боя и деревни.
6. Состояние подтверждается через `state_confirmations_required = 2`, чтобы не переключаться от одного случайного кадра.

## 7. Проверка лута

Сейчас в активном конфиге:

- `loot_check_enabled = false`

Поэтому после обнаружения боя бот сразу атакует.

Если включить `loot_check_enabled`, логика будет такая:

1. OCR читает лут до `loot_ocr_attempts = 2` попыток.
2. Минимумы:
   - `loot_min_gold = 500000`
   - `loot_min_elixir = 500000`
3. Если лут подходит, атака начинается.
4. Если лут не подходит, бот тапает `next_base_point = 92.27%,70.87%`.
5. Ждет `next_search_delay_seconds = 1.5`.
6. Повторяет ожидание следующего боя.

## 8. Подготовка камеры

`_prepare_battle_camera()` включен:

- `battle_camera_prepare_enabled = true`

Сейчас активен прямой ctrl+scroll (см. §11), поэтому путь с ADB pinch и pan пропускается ранним возвратом из `_prepare_battle_camera()`. Старый pinch-путь работает только если выключить `battle_camera_direct_ctrl_scroll_enabled`.

Если включен ctrl+scroll путь:

1. `device.ctrl_mouse_wheel_zoom_out(ticks)` — прямой Ctrl+wheel down.
2. После zoom-out ждет `battle_camera_center_settle_seconds = 0.25`.
3. Если `calibration_overlay_enabled = true` и `calibration_overlay_after_camera_prepare = true`, сохраняет overlay:
   - `logs/calibration/*-after-camera-prepare.png`

Если включен старый pinch-путь:

1. `battle_camera_zoom_out_attempts = 2` ADB pinch zoom-out.
2. Длительность каждого zoom-out: `battle_camera_zoom_out_seconds = 0.35`.
3. После каждого zoom-out ждет `battle_camera_pan_settle_seconds = 0.35`.
4. Pan выключен: `battle_camera_pan_enabled = false`.
5. После подготовки ждет `battle_camera_center_settle_seconds = 0.25`.
6. Overlay сохраняется при тех же условиях.

## 9. Режим деплоя

Текущий режим:

- `deploy_mode = hotkeys`

Это значит, что высадка в основной деревне идет прямым вводом в LDPlayer: цифровые клавиши выбора слотов плюс клавиша `G`.

Поддерживаемые режимы в коде:

- `coordinates`: текущий основной режим.
- `templates`: ищет `deploy_targets` в нижней панели и деплоит найденные слоты.
- `g_key`: для troop step нажимает emulator key `G`, потом усиливает ADB-точками.
- `hotkeys`: текущий новый режим для основной деревни.

## 10. Hotkey-деплой

В `hotkeys` режиме бот не идет по обычному coordinate `deploy_plan`, кроме шага спеллов. Порядок такой:

1. Нажимает `home_hotkey_troop_key = 1`.
2. Проходит все точки `G+1..G+8` подряд `home_hotkey_troop_g_point_passes = 3` раза.
3. Для каждой клавиши из `home_hotkey_all_point_keys = 2,3,4,5,6` (осадная машина и герои):
   - Нажимает клавишу.
   - Проходит все точки `G+1..G+8` подряд `home_hotkey_all_point_passes = 1` раз.
4. Нажимает `home_hotkey_spell_key = 7` и кидает спеллы (см. §17).
5. После спеллов вызывается `_activate_hotkey_hero_abilities()`:
   - Ждет `home_hotkey_hero_ability_delay_seconds = 2.0`.
   - Жмет каждую клавишу из `home_hotkey_hero_keys = 3,4,5,6` по одному разу.

Текущие параметры:

- `home_hotkey_troop_key = 1`
- `home_hotkey_troop_g_presses = 8`
- `home_hotkey_g_point_keys = 1, 2, 3, 4, 5, 6, 7, 8`
- `home_hotkey_troop_g_point_passes = 3`
- `home_hotkey_siege_key = 2`
- `home_hotkey_siege_g_presses = 4`
- `home_hotkey_all_point_keys = 2, 3, 4, 5, 6`
- `home_hotkey_all_point_passes = 1`
- `home_hotkey_hero_keys = 3, 4, 5, 6`
- `home_hotkey_hero_g_presses = 4`
- `home_hotkey_hero_ability_delay_seconds = 2.0`
- `home_hotkey_spell_key = 7`
- `g_key_deploy_key = G`
- `home_hotkey_key_delay_seconds = 0.05`
- `g_key_deploy_press_delay_seconds = 0.05`

## 11. Прямой zoom-out через Ctrl+scroll

Перед высадкой камера теперь может готовиться прямым вводом:

- `battle_camera_direct_ctrl_scroll_enabled = true`
- `battle_camera_direct_ctrl_scroll_ticks = 2`

Когда этот режим включен, `_prepare_battle_camera()` вызывает `AdbDevice.ctrl_mouse_wheel_zoom_out()` и не делает старый ADB pinch zoom-out.

## 12. Старый coordinate-план деплоя

`deploy_plan` остается в конфиге для совместимости и для спеллов. В `coordinates` режиме он работал так:

1. `new_troop_1`
   - слот: `6.44%,95.11%`
   - `deploy_taps = 1`
   - группа: `troops`
2. `battle_machine`
   - слот: `15.31%,85.89%`
   - `deploy_taps = 1`
   - группа: `default`
3. `hero_3`
   - слот: `23.31%,85.33%`
   - `deploy_taps = 1`
   - группа: `default`
4. `hero_4`
   - слот: `31.13%,85.11%`
   - `deploy_taps = 1`
   - группа: `default`
5. `hero_5`
   - слот: `38.44%,85.56%`
   - `deploy_taps = 1`
   - группа: `default`
6. `hero_6`
   - слот: `45.50%,85.33%`
   - `deploy_taps = 1`
   - группа: `default`
7. `spells`
   - слот: `54.19%,85.67%`
   - `deploy_taps = 0`
   - `random_deploy_area = spells`
   - случайные тапы: `11..13`

Перед каждым шагом бот проверяет, находится ли слот в `deploy_slot_detection_area`:

- `x = 0..100`
- `y = 67..100`

Если слот вне этой области, бот только пишет warning, но не останавливается.

## 13. Деплой войск и героев по точкам

Этот раздел относится к старому `coordinates` режиму. Для каждого обычного шага бот:

1. Тапает слот юнита/героя.
2. Ждет `deploy_step_delay_seconds = 0.15`.
3. Если это spells, переходит к логике спеллов.
4. Иначе вызывает `_deploy_step_to_primary_and_fallbacks(step)`.

В `_deploy_step_to_primary_and_fallbacks`:

1. Сначала тапает `primary_deploy_point = 28.56%,32.11%`.
2. Затем тапает набор deploy points для группы шага.

Группы:

- `troops` используют `troop_deploy_points`.
- `heroes` используют `hero_deploy_points`.
- все остальные используют `default_deploy_points`.

Текущие `troop_deploy_points`:

1. `28.56%,32.11%`
2. `39.44%,19.67%`
3. `60.44%,24.00%`
4. `75.81%,44.00%`
5. `86.31%,57.78%`
6. `17.63%,46.11%`
7. `77.44%,72.00%`
8. `12.56%,65.89%`

Текущие `default_deploy_points` и `hero_deploy_points`:

- `28.56%,32.11%`

## 14. Соседние тапы вокруг deploy points

Включено:

- `deploy_neighbor_taps_enabled = true`
- `deploy_neighbor_offset_percent = 0.45`

Каждая deploy point расширяется в 5 точек:

1. сама точка
2. `x + 0.45`
3. `x - 0.45`
4. `y + 0.45`
5. `y - 0.45`

Для troop-группы 8 точек превращаются в 40 ADB taps. Тапы отправляются батчами по 24 через `tap_many_percent`.

## 15. Маркер полного деплоя войск

Настроен template:

- `troops_deployed_template_path = assets/templates/state/troops_deployed_x0.png`
- область: `x 0..24`, `y 78..100`
- threshold: `0.78`

Но сейчас:

- `troop_marker_check_during_burst = false`

Значит во время burst бот не прерывает деплой по маркеру. После burst он может проверить маркер и записать в лог, что все войска задеплоены.

В `g_key` режиме есть отдельная `_verify_troops_deployed()` с retry:

- `troop_deploy_verify_retries = 2`

## 16. Способности героев (coordinate flow)

Этот механизм относится к старому `coordinates` режиму. В текущем `hotkeys` режиме `_activate_hero_abilities()` не вызывается; вместо него после спеллов отрабатывает `_activate_hotkey_hero_abilities()` (см. §10 шаг 5).

Coordinate flow:

1. Ждет `hero_ability_delay_seconds`.
2. Тапает координаты слотов из `hero_ability_slots = hero_3..hero_6`.
3. Между тапами ждет `hero_ability_tap_delay_seconds`.

`battle_machine` в `hero_ability_slots` не указан.

## 17. Спеллы

В текущем `hotkeys` режиме бот нажимает `home_hotkey_spell_key = 7`, затем кидает случайные спеллы. Hero abilities активируются ПОСЛЕ спеллов (см. §10 шаг 5), а не до.

1. Бот нажимает клавишу `7`.
2. Берет шаг `spells` из `deploy_plan`.
3. `_deploy_random_points(step)`:
   - Выбирает случайное количество тапов от `random_taps_min = 11` до `random_taps_max = 13`.
   - Каждый тап в случайную точку внутри `spell_deploy_area.x = 35..65`, `y = 35..65`.
   - Между тапами ждет `spell_tap_delay_seconds = 0.08`.

`pre_spell_delay_seconds` в hotkeys-пути не используется — он применяется только в coordinate flow перед `_activate_hero_abilities`.

## 18. Ожидание после деплоя

После полного деплоя бот ждет:

- `wait_after_deploy_seconds = 40.0`

Это фиксированное ожидание перед завершением боя.

## 19. Завершение боя и возврат домой

`_finish_and_return_home()`:

1. Тапает `end_battle_point = 6.88%,74.83%`.
2. Ждет `tap_delay_seconds = 0.35`.
3. Тапает `confirm_end_point = 60.80%,64.33%`.
4. Ждет `tap_delay_seconds = 0.35`.
5. Тапает `return_home_point = 49.95%,85.22%`.

После возврата снова вызывается `dismiss_popups()`.

## 20. Что важно помнить

- Основная деревня сейчас смешанная: навигация и спеллы остаются ADB percent coordinates, а высадка слотов идет прямыми LDPlayer hotkeys.
- Активный режим деплоя: `hotkeys`.
- До старта боя бот проверяет `FREE`; если найден, выполняет сбор и потом стартует бой.
- Лут-чек выключен, бот атакует первый найденный бой.
- Камера перед деплоем делает прямой `Ctrl+mouse wheel down`; pinch/pan-путь выполняется только если выключить direct ctrl-scroll.
- Войска деплоятся клавишами `1`, `2..6`, `7` и `G`. Способности героев (`3..6`) активируются ПОСЛЕ спеллов.
- Бой завершается принудительно через `wait_after_deploy_seconds` (текущий конфиг: 40) секунд после деплоя.
