---
name: kaiten
description: Работа с Kaiten (карточки, доски, комментарии, тайм-логи) через CLI `kaiten`. Use when the user asks to find/read/create/move Kaiten cards, comment on them, or pull time logs / reports from Kaiten.
---

# Kaiten через CLI `kaiten`

Вся работа с Kaiten идёт через консольную утилиту `kaiten` (проект kaiten-cli).
Вывод всегда JSON на stdout; ошибки — JSON на stderr с exit code 1. ID везде числовые
(кроме `cards get`, который принимает и ключ вида PROJ-123).

## Пререквизиты

- В окружении должны быть `KAITEN_SUBDOMAIN` и `KAITEN_TOKEN`. Проверка:
  `kaiten whoami --compact` — вернёт JSON текущего пользователя. Если команда не
  найдена — установи: `uv tool install git+https://github.com/hodzanassredin/kaiten-cli`
  (или `uvx --from git+https://github.com/hodzanassredin/kaiten-cli kaiten ...` разово).

## Самообслуживание

Справка полная — сначала смотри её, а не гадай по флагам:
`kaiten --help` → `kaiten <group> --help` → `kaiten <group> <action> --help`.

Группы: `spaces`, `boards`, `columns`, `cards`, `comments`, `time-logs`, `whoami`.

## Правила экономии контекста

- Всегда добавляй `--fields id,title` (или нужные поля) к list/get — у карточек много
  тяжёлых полей (description, вложенные пользователи). Полный JSON бери только когда
  реально нужен.
- `--compact` — однострочный JSON, дешевле для длинных списков.
- Rate limit Kaiten — 5 req/s. Не вызывай CLI в tight-цикле; на больших выгрузках
  используй `--limit/--offset` с паузами.

## Типовые сценарии

Найти карточку по тексту → прочитать → прокомментировать → передвинуть:
```bash
kaiten spaces list --fields id,title --compact
kaiten boards list --space <SPACE_ID> --fields id,title --compact
kaiten cards list --board <BOARD_ID> --query "текст" --fields id,title --compact
kaiten cards get <CARD_ID>
kaiten comments add <CARD_ID> --text "комментарий (markdown)"
kaiten columns list --board <BOARD_ID> --fields id,title --compact
kaiten cards move <CARD_ID> --column <COLUMN_ID>
```

Создать карточку:
```bash
kaiten cards create --board <BOARD_ID> --title "Заголовок" \
  [--column ID] [--description "..."] [--due 2026-09-30] [--asap]
```

Тайм-логи:
```bash
kaiten time-logs list --card <CARD_ID> [--for-date 2026-09-01] [--personal]
kaiten time-logs add --card <CARD_ID> --minutes 90 [--for-date DATE] [--comment "..."]
```

Отчёт по времени за период: глобального эндпоинта нет — собирай по карточкам:
`cards list --board ... --fields id,title` → для каждой `time-logs list --card ...`.

## Осторожно

Пишущие команды (`cards create/update/move`, `comments add`, `time-logs add`,
`cards update --archive`) меняют данные — для массовых операций сначала покажи
пользователю список того, что будешь менять, и получи подтверждение.
Delete-операций в CLI нет.
