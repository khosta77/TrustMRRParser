# trustmrr-scraper

Сбор базы стартапов с [TrustMRR](https://trustmrr.com) через официальный API
`/api/v1/startups`, с уведомлениями о прогрессе на почту.

## Возможности

- Полный список всех стартапов (~7600) за ~153 запроса с учётом rate limit (20/мин).
- Опциональное обогащение детальным эндпоинтом (`--enrich`): `techStack`,
  `marketingChannels`, `xFollowerCount`, `isMerchantOfRecord`.
- Вывод в JSON с полем `scraped_at` для накопления истории.
- Email-уведомления: старт, прогресс каждые 10%, завершение, ошибка.

## Установка

```bash
poetry install
```

## Запуск

`--api-key` и `--proxy` обязательны. Прокси нужен, потому что TrustMRR не
отвечает на запросы из РФ напрямую.

```bash
poetry run trustmrr-scrape \
  --api-key "tmrr_xxx" \
  --proxy "http://user:pass@host:port" \
  --enrich \
  --out data/startups.json
```

Тестовый прогон без писем:

```bash
poetry run trustmrr-scrape --api-key tmrr_xxx --proxy http://... --limit 30 --no-notify
```

## Почта

Настройки берутся из переменных окружения (по умолчанию — локальный релей VM):

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `MAIL_SMTP_HOST` | `172.17.0.1` | SMTP-релей (docker-gateway хоста) |
| `MAIL_SMTP_PORT` | `25` | порт |
| `MAIL_FROM` | `noreply@kisscolab.ru` | отправитель |
| `MAIL_TO` | `puwerfulpants@mail.ru` | получатель (можно `--notify-to`) |
| `MAIL_USER` / `MAIL_PASSWORD` | — | если релей требует auth |

Если `MAIL_USER`/`MAIL_PASSWORD` не заданы, письма отправляются без
аутентификации (открытый релей на порту 25). Отправка обёрнута в try/except и
не прерывает сбор.

## Docker

```bash
cp .env.example .env        # заполнить TRUSTMRR_API_KEY, TRUSTMRR_PROXY
docker compose up --build
```

Результат — в `./data/startups.json` (том примонтирован). Контейнер ходит на
релей `172.17.0.1:25` через docker-bridge, как и исходный notification-сервис.

## Лимиты API

20 запросов в минуту на ключ. Клиент читает `x-ratelimit-remaining` /
`x-ratelimit-reset` и засыпает до сброса окна.

## Структура

- `src/trustmrr_scraper/client.py` — клиент API (rate limit, прокси)
- `src/trustmrr_scraper/notifier.py` — отправка email-уведомлений
- `src/trustmrr_scraper/cli.py` — CLI, tqdm, вывод JSON
