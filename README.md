# kaiten-cli

Маленький CLI поверх [Kaiten](https://kaiten.ru) REST API: карточки, комментарии,
тайм-логи. Задуман как инструмент для AI-агентов и скриптов: **вывод всегда JSON** на
stdout, ошибки — JSON на stderr с exit code 1, самодокументируемый `--help`.

Замена тяжёлым MCP-серверам: вместо сотен tool-схем в контексте агента — один скилл
с кулинарной книгой команд, который подгружается только когда Kaiten реально нужен.

## Установка

```bash
# разово, без установки
uvx --from git+https://github.com/hodzanassredin/kaiten-cli kaiten whoami

# как инструмент
uv tool install git+https://github.com/hodzanassredin/kaiten-cli

# из исходников
uv tool install .
```

Требуется Python >= 3.11. Единственная зависимость — `httpx`.

## Настройка

| Переменная | Описание |
|---|---|
| `KAITEN_SUBDOMAIN` | Поддомен компании (`yourcompany` для `yourcompany.kaiten.ru`) |
| `KAITEN_TOKEN` | API-токен (Kaiten → Профиль → API-ключи) |
| `KAITEN_BASE_URL` | Полный override хоста API для нестандартных стендов |
| `KAITEN_BASE_DOMAIN` | Базовый домен, по умолчанию `kaiten.ru` |

Всё это можно передать и флагами: `--subdomain`, `--token`, `--base-url`, `--base-domain`.

## Команды

```
kaiten whoami                          # проверка auth: текущий пользователь

kaiten spaces list
kaiten boards list --space ID
kaiten columns list --board ID

kaiten cards list [--board ID] [--space ID] [--query TEXT] [--limit N] [--offset N]
kaiten cards get ID                    # числовой ID или ключ вида PROJ-123
kaiten cards create --board ID --title "..." [--column ID] [--description "..."] [--due DATE] [--asap]
kaiten cards update ID [--title ...] [--description ...] [--due DATE] [--archive]
kaiten cards move ID --column ID [--lane ID] [--board ID]

kaiten comments list CARD_ID
kaiten comments add CARD_ID --text "..."

kaiten time-logs list --card ID [--for-date YYYY-MM-DD] [--personal]
kaiten time-logs add --card ID --minutes N [--for-date DATE] [--comment "..."]
```

Полная справка: `kaiten --help`, `kaiten <group> --help`, `kaiten <group> <action> --help`.

## Глобальные флаги вывода

- `--fields id,title,state` — оставить только перечисленные поля верхнего уровня
  (работает и для списков). Главный способ не раздувать контекст агента: у карточек
  много тяжёлых полей (`description`, вложенные объекты пользователей).
- `--compact` — однострочный JSON без отступов.

## Примеры

```bash
# найти карточку по тексту и прочитать
kaiten cards list --board 42 --query "оплата" --fields id,title
kaiten cards get 12345

# прокомментировать и передвинуть в другую колонку
kaiten comments add 12345 --text "Готово, смотрите PR"
kaiten columns list --board 42 --fields id,title
kaiten cards move 12345 --column 777

# тайм-логи
kaiten time-logs list --card 12345 --for-date 2026-09-01
kaiten time-logs add --card 12345 --minutes 90 --comment "ревью"
```

## Ограничения

- Rate limit Kaiten — 5 запросов/сек; при HTTP 429 клиент ретраит с backoff (до 3 раз).
  Не гоняйте CLI в tight-цикле.
- Это read/write клиент: `cards create/update/move`, `comments add`, `time-logs add`,
  `cards update --archive` меняют данные. Деструктивных delete-операций в CLI нет.

## Лицензия

MIT
