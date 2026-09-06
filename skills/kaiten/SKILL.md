---
name: kaiten
description: Работа с Kaiten (карточки, доски, комментарии, тайм-логи) через CLI `kaiten-mini`. Use when the user asks to find/read/create/move Kaiten cards, comment on them, or pull time logs / reports from Kaiten.
---

# Kaiten через CLI `kaiten-mini`

Вся работа с Kaiten идёт через консольную утилиту `kaiten-mini` (проект kaiten-mini).
Вывод всегда JSON на stdout; ошибки — JSON на stderr с exit code 1. ID везде числовые
(кроме `cards get`, который принимает и ключ вида PROJ-123).

## Пререквизиты

- В окружении должны быть `KAITEN_SUBDOMAIN` и `KAITEN_TOKEN`. Проверка:
  `kaiten-mini whoami --compact` — вернёт JSON текущего пользователя. Если команда не
  найдена — установи: `uv tool install git+https://github.com/hodzanassredin/kaiten-mini`
  (или `uvx --from git+https://github.com/hodzanassredin/kaiten-mini kaiten-mini ...` разово).

### Если токена нет

Не останавливайся и не гадай — проведи пользователя за руку. **Токен не должен
попасть в контекст модели**: не проси вставить его в чат и не подставляй в команду
(`KAITEN_TOKEN=... kaiten-mini ...` или `--token ...`) — команды и сообщения
читаются моделью и пишутся в логи.

1. Скажи: токен получается на https://developers.kaiten.ru/ (профиль в Kaiten →
   «API и вебхуки» → создать токен). Предложи открыть страницу сам:
   `xdg-open https://developers.kaiten.ru/` (macOS: `open`, Windows: `start`).
2. Пусть ПОЛЬЗОВАТЕЛЬ САМ запишет токен в файл — `kaiten-mini` читает `./.env`
   и `~/.config/kaiten-mini/.env`:
   ```
   KAITEN_SUBDOMAIN=<поддомен>
   KAITEN_TOKEN=<токен>
   ```
   Поддомен виден в адресной строке любой доски: `https://<поддомен>.kaiten.ru`.
   `.env` проекта не коммитить (проверь `.gitignore`).
3. Проверка без раскрытия токена — просто `kaiten-mini whoami --compact`:
   JSON пользователя = всё работает, `401` = токен неверный,
   «not configured» = файл не найден или переменные не записаны.

Если токен всё же попал в чат/команду — предупреди пользователя, что его стоит
перевыпустить (там же, в профиле Kaiten).

## Самообслуживание

Справка полная — сначала смотри её, а не гадай по флагам:
`kaiten-mini --help` → `kaiten-mini <group> --help` → `kaiten-mini <group> <action> --help`.

Группы: `spaces`, `boards`, `columns`, `users`, `cards`, `files`, `comments`, `time-logs`, `whoami`.

Разрешить id пользователя в имя: `kaiten-mini users get <UID> --fields full_name,username`
или списком: `kaiten-mini users list --fields id,full_name,username --compact`.

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
kaiten-mini spaces list --fields id,title --compact
kaiten-mini boards list --space <SPACE_ID> --fields id,title --compact
kaiten-mini cards list --board <BOARD_ID> --query "текст" --fields id,title --compact
kaiten-mini cards get <CARD_ID>
kaiten-mini cards url <CARD_ID> --fields url --compact   # ссылка на карточку в UI — отдавать её в ответе
kaiten-mini comments add <CARD_ID> --text "комментарий (markdown)"
kaiten-mini columns list --board <BOARD_ID> --fields id,title --compact
kaiten-mini cards move <CARD_ID> --column <COLUMN_ID>
```

Создать карточку:
```bash
kaiten-mini cards create --board <BOARD_ID> --title "Заголовок" \
  [--column ID] [--description "..."] [--due 2026-09-30] [--asap]
```

Вложения (картинки, документы):
```bash
kaiten-mini files list --card <CARD_ID> --fields id,name,size,url --compact
kaiten-mini files download --card <CARD_ID> --file <FILE_ID> [-o ./file.png]
kaiten-mini api PUT /cards/<CARD_ID>/files --attach ./file.pdf   # загрузка
```
`url` вложения на files.kaiten.ru открывается без токена (ссылка с UUID) — её можно
отдавать пользователю как есть. Картинки в описании/комментариях вставлены markdown'ом
на те же files.kaiten.ru-ссылки.

Тайм-логи:
```bash
kaiten-mini time-logs list --card <CARD_ID> [--for-date 2026-09-01] [--personal]
kaiten-mini time-logs add --card <CARD_ID> --minutes 90 [--for-date DATE] [--comment "..."]
```

Отчёт по времени за период: глобального эндпоинта нет — собирай по карточкам:
`cards list --board ... --fields id,title` → для каждой `time-logs list --card ...`.

## Модель данных: дерево и path_data

Иерархия: пространство (space) → доска (board) → колонка → карточка. Ссылки «вверх»
API не отдаёт: у карточки есть только `board_id`, у доски нет `space_id`, глобального
списка досок нет. Как находить нужное:

- Ссылка на карточку в UI: `kaiten-mini cards url <CARD_ID>` — команда сама резолвит
  пространство (через `path_data` списка карточек, с фолбэком на обход дерева).
- Пространство/колонка/линия карточки вручную: поле `path_data` есть в ответе
  **списка** `api GET /cards --param board_id=<ID>` (в одиночном `cards get` его нет).
- Обход дерева вручную: `spaces list` → `boards list --space ID` →
  `cards list --board ID`.

## Метаданные API (референс встроен в CLI)

Kaiten не отдаёт OpenAPI, но `kaiten-mini docs` вытаскивает весь референс
с developers.kaiten.ru (62 сущности, схемы запросов и примеры ответов).
Не гадай по эндпоинтам и полям — сначала посмотри в метаданные:

```bash
kaiten-mini docs list [filter]                 # сущности и операции (метод + путь)
kaiten-mini docs search "time"                 # поиск по имени операции/пути
kaiten-mini docs get "/cards/{card_id}/time-logs"  # request-схема и поля ответа
```

Полный объект операции тяжёлый — комбинируй с `--fields`/`--compact`.

## Универсальный вызов (любой эндпоинт)

Если под задачу нет готовой команды — не останавливайся: `kaiten-mini api` ходит
в любой эндпоинт API напрямую:

```bash
kaiten-mini api GET /boards/<ID>/lanes --param limit=10
kaiten-mini api GET /card-types --fields id,name
kaiten-mini api POST /cards --body '{"title": "...", "board_id": 123}'
kaiten-mini api PATCH /cards/<ID> --body '{"column_id": 777}'
kaiten-mini api PUT /cards/<ID>/files --attach ./file.pdf  # прикрепить файл (multipart)
```

Путь — относительно `/api/latest`; `--param key=value` повторяемый, значения
авто-приводятся к int/bool; тело — JSON-строка или `@file.json`. Список эндпоинтов
и поля тел смотри в доке: https://developers.kaiten.ru/

## Осторожно

Пишущие команды (`cards create/update/move`, `comments add`, `time-logs add`,
`cards update --archive`) меняют данные — для массовых операций сначала покажи
пользователю список того, что будешь менять, и получи подтверждение.
Delete-операций в CLI нет.
