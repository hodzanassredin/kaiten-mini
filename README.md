# kaiten-mini

Маленький CLI поверх [Kaiten](https://kaiten.ru) REST API: карточки, комментарии,
тайм-логи. Задуман как инструмент для AI-агентов и скриптов: **вывод всегда JSON** на
stdout, ошибки — JSON на stderr с exit code 1, самодокументируемый `--help`.

Замена тяжёлым MCP-серверам: вместо сотен tool-схем в контексте агента — один скилл
с кулинарной книгой команд, который подгружается только когда Kaiten реально нужен.

## Альтернатива и чем мы отличаемся

Полнофункциональный вариант — [ViktorOgnev/kaiten-cli](https://github.com/ViktorOgnev/kaiten-cli)
(Community Edition, тот же доменный слой, что и у kaiten-mcp). Он покрывает весь API
Kaiten и умеет много всего для работы человека из терминала: автодополнение shell,
read-only режим, локальные SQLite-снимки для офлайн-аналитики, графики, команды
discovery (`search-tools`, `describe`, `examples`), релизы с тегами.

Этот проект — сознательно **минимальный, agent-first** вариант:

| | ViktorOgnev/kaiten-cli | этот репо |
|---|---|---|
| Покрытие API | весь Kaiten (27 доменов) | ~15 команд: карточки, комментарии, тайм-логи, спейсы/борды/колонки |
| Зависимости | Click и др. | только `httpx` |
| Код | реестр команд, плагины | 3 файла, читается за 10 минут |
| Аудитория | человек в терминале + автоматизация | AI-агент (скилл в комплекте) и простые скрипты |
| Вывод | человеко-читаемый + JSON | только JSON |

Правило выбора: нужен полный доступ к Kaiten из терминала руками — берите
ViktorOgnev/kaiten-cli. Нужен маленький предсказуемый инструмент, который агент
освоит по `--help` и одному скиллу, — этот.


## Установка

```bash
# разово, без установки
uvx --from git+https://github.com/hodzanassredin/kaiten-mini kaiten-mini whoami

# как инструмент
uv tool install git+https://github.com/hodzanassredin/kaiten-mini

# из исходников
uv tool install .
```

Требуется Python >= 3.11. Единственная зависимость — `httpx[socks]`.

## Установка скилла для AI-агента

В репо лежит скилл `skills/kaiten/SKILL.md` — кулинарная книга команд для агента
(лениво подгружается в контекст только когда Kaiten реально нужен).

Через [skills CLI](https://github.com/vercel-labs/skills) (нужен Node.js; ставит в
Claude Code, Kimi Code CLI, Cursor, Codex и ещё ~70 агентов):

```bash
# глобально (~/.agents/skills/kaiten для Kimi Code CLI и др.)
npx skills add hodzanassredin/kaiten-mini --skill kaiten-mini -g -y

# или в конкретный агент
npx skills add hodzanassredin/kaiten-mini --skill kaiten-mini -g -a claude-code
```

Или вручную:

```bash
mkdir -p ~/.agents/skills/kaiten
curl -sL https://raw.githubusercontent.com/hodzanassredin/kaiten-mini/main/skills/kaiten/SKILL.md \
  -o ~/.agents/skills/kaiten/SKILL.md
```


## Настройка

| Переменная | Описание |
|---|---|
| `KAITEN_SUBDOMAIN` | Поддомен компании (`yourcompany` для `yourcompany.kaiten.ru`) |
| `KAITEN_TOKEN` | API-токен — получить: [developers.kaiten.ru](https://developers.kaiten.ru/) (Kaiten → Профиль → API-ключи) |
| `KAITEN_BASE_URL` | Полный override хоста API для нестандартных стендов |
| `KAITEN_BASE_DOMAIN` | Базовый домен, по умолчанию `kaiten-mini.ru` |

Всё это можно передать и флагами: `--subdomain`, `--token`, `--base-url`, `--base-domain`.

CLI также подхватывает `./.env` и `~/.config/kaiten-mini/.env` (не переопределяет
уже установленные переменные). Это предпочтительный способ для токена: файл пишет
человек, и токен не светится ни в истории shell, ни в контексте AI-агента.

## Команды

```
kaiten-mini whoami                          # проверка auth: текущий пользователь

kaiten-mini spaces list
kaiten-mini boards list --space ID
kaiten-mini columns list --board ID

kaiten-mini users list [--query TEXT] [--include-inactive]
kaiten-mini users get UID

# метаданные API: референс с developers.kaiten.ru (auth не нужен)
kaiten-mini docs list [FILTER]      # сущности и операции (метод + путь)
kaiten-mini docs search "time"      # поиск операций по имени/пути
kaiten-mini docs get "/cards/{card_id}/time-logs"   # схема запроса и примеры ответа

# универсальный вызов любого эндпоинта (без отдельной команды)
kaiten-mini api GET /boards/ID/lanes --param limit=10
kaiten-mini api POST /cards --body '{"title": "...", "board_id": 123}'
kaiten-mini api PUT /cards/ID/files --attach ./doc.pdf   # multipart-загрузка файла

kaiten-mini cards list [--board ID] [--space ID] [--query TEXT] [--owner UID] [--responsible UID] [--member UID] [--state 1,2] [--limit N] [--offset N]
kaiten-mini cards get ID                    # числовой ID или ключ вида PROJ-123
kaiten-mini cards url ID                     # кликабельная ссылка на карточку в веб-интерфейсе
kaiten-mini cards create --board ID --title "..." [--column ID] [--description "..."] [--due DATE] [--asap]
kaiten-mini cards update ID [--title ...] [--description ...] [--due DATE] [--archive]
kaiten-mini cards move ID --column ID [--lane ID] [--board ID]

kaiten-mini files list --card ID             # вложения карточки (id, name, size, url)
kaiten-mini files download --card ID --file FILE_ID [-o PATH]

kaiten-mini comments list CARD_ID
kaiten-mini comments add CARD_ID --text "..."

kaiten-mini time-logs list --card ID [--for-date YYYY-MM-DD] [--personal]
kaiten-mini time-logs add --card ID --minutes N [--for-date DATE] [--comment "..."]
```

Полная справка: `kaiten-mini --help`, `kaiten-mini <group> --help`, `kaiten-mini <group> <action> --help`.

## Глобальные флаги вывода

- `--fields id,title,state` — оставить только перечисленные поля верхнего уровня
  (работает и для списков). Главный способ не раздувать контекст агента: у карточек
  много тяжёлых полей (`description`, вложенные объекты пользователей).
- `--compact` — однострочный JSON без отступов.

## Примеры

```bash
# найти карточку по тексту и прочитать
kaiten-mini cards list --board 42 --query "оплата" --fields id,title
kaiten-mini cards get 12345

# прокомментировать и передвинуть в другую колонку
kaiten-mini comments add 12345 --text "Готово, смотрите PR"
kaiten-mini columns list --board 42 --fields id,title
kaiten-mini cards move 12345 --column 777

# тайм-логи
kaiten-mini time-logs list --card 12345 --for-date 2026-09-01
kaiten-mini time-logs add --card 12345 --minutes 90 --comment "ревью"
```

## Ограничения

- Rate limit Kaiten — 5 запросов/сек; при HTTP 429 клиент ретраит с backoff (до 3 раз).
  Не гоняйте CLI в tight-цикле.
- Это read/write клиент: `cards create/update/move`, `comments add`, `time-logs add`,
  `cards update --archive` меняют данные. Деструктивных delete-операций в CLI нет.

## Лицензия

MIT
