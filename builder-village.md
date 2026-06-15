# Builder Village Bot Logic

Документ описывает текущий builder-flow по активному `config.json` и коду
`coc_bot/builder_flow.py`.

## Запуск

Builder-режим запускается, когда выбран `bot_mode = builder` или передан аргумент:

```powershell
.\.venv\Scripts\python.exe -m coc_bot.main --bot-mode builder
```

## Один Цикл

`BuilderBattleFlow.run_once()` выполняет шаги:

1. `dismiss_popups`
2. `wait_for_base`
3. `open_attack`
4. `wait_for_battle`
5. `deploy_slots`
6. `wait_and_return_home`
7. `dismiss_popups_after_return`

После успешного цикла основной loop ждет `cycle_delay_seconds = 1.5` секунды.

## Открытие Атаки

Перед нажатием attack бот готовит вид builder-базы:

1. Делает полный zoom-out через прямой `Ctrl+mouse wheel down`.
2. Не нажимает дополнительные клавиши камеры: `builder_base_camera_key_sequence = []`.
3. Нажимает первую точку attack: `builder_attack_taps[0] = 6.81%,88.78%`.

После открытия окна `Start Attack` бот до `wait_attack_ready_seconds = 10.0` секунд ищет:

- прямой шаблон кнопки `Find Now`;
- дополнительные маркеры окна `Start Attack`: топоры, заголовок, блок troops, `All defenses ready`, полный экран.

Если найдена сама кнопка, бот нажимает найденные пиксельные координаты. Если найден только маркер окна,
бот нажимает настроенную точку кнопки: `builder_attack_taps[1] = 74.50%,65.78%`.

## Ожидание Боя

После `Find Now` бот до `wait_battle_seconds = 6.0` секунд ищет builder battle marker.
Если marker не найден и `builder_continue_on_battle_marker_timeout = true`, бот продолжает прямой deploy.

## Деплой

Активный builder deploy mode: `builder_deploy_mode = hotkeys`.

Стартовый deploy:

1. Зажимает `G+0` на `builder_hotkey_deploy_hold_seconds = 2.0` секунды.
2. Сразу нажимает hotkey slots: `2`, `3`, `4`, `5`, `6`, `7`, `8`.

Проверка состояний слотов отключена: `builder_slot_state_checks_enabled = false`.

## Во Время Боя

Пока бот ждет `Return Home`:

1. Каждые `builder_redeploy_slots_interval_seconds = 10.0` секунд повторяет `G+0`, затем `2..8`.
2. Каждые `builder_first_slot_retap_interval_seconds = 10.0` секунд нажимает `builder_first_slot_key = 1`.
3. Каждые `builder_g_point_sweep_interval_seconds = 45.0` секунд делает один sweep: для slot keys `2..8`
   нажимает slot key, затем `G+1`, `G+2`, `G+3`, `G+4`.

Builder hero ability loop отключен: `builder_hero_ability_enabled = false`.

## Возврат Домой

Бот до `builder_battle_timeout_seconds = 240.0` секунд ищет `Return Home`.
Если кнопка найдена, нажимает `builder_return_home_point = 50.38%,83.33%`.
Если не найдена за таймаут, все равно нажимает эту точку.

## Защита Тапов

ADB-тапы builder-flow проходят через calibration/guard:

- expected screen: `1600x900`
- max drift: `2%`
- safe area: `x 0..100`, `y 0..96`

Forbidden areas:

1. `x 72..100`, `y 78..100`
2. `x 82..100`, `y 58..78`
3. `x 0..8`, `y 0..18`

Если координата вне safe area или внутри forbidden area, бот бросает `UnsafeBuilderTapError` и уходит в recovery.
