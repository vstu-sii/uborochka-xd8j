# Деплой прода

Выбрана площадка: **Render** (render.com) — бесплатный тир для старта,
деплой из Docker-образа прямо по репозиторию, авто-деплой на каждый
push в `main`, публичный HTTPS-URL из коробки, легко даёт доступ всей
команде (Render → Team). Если позже понадобится больше ресурсов —
проект без изменений переезжает на VPS, т.к. всё уже в Docker.

## Первый деплой (сделать один раз)

1. Зарегистрироваться на render.com, привязать GitHub-аккаунт команды
2. New → Web Service → выбрать этот репозиторий
3. Настройки сервиса:
   - **Environment**: Docker
   - **Dockerfile path**: `./Dockerfile`
   - **Branch**: `main`
   - **Auto-Deploy**: On (деплой на каждый push в main)
4. Environment Variables — перенести все ключи из `.env.example` с
   реальными значениями (Render → Environment)
5. Deploy. После первого успешного деплоя Render выдаст публичный URL
   вида `https://<service-name>.onrender.com`
6. Проверить, что `https://<service-name>.onrender.com/health`
   отдаёт `{"status": "healthy"}`
7. Вписать этот URL в README.md в раздел «Прод»
8. Дать доступ всей команде: Render → Project → Settings → Team →
   Invite

## Подключение Telegram webhook (когда бот будет готов)

```bash
curl -F "url=https://<service-name>.onrender.com/webhook/telegram" \
  https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
```

## Дальнейшие деплои

Ничего руками делать не нужно: push/merge в `main` → CI зелёный →
Render автоматически пересобирает и выкатывает новую версию. Именно
поэтому прод существует с первой недели и дальше только наращивается.

## Если что-то сломалось

- Логи: Render → Service → Logs
- Откат: Render → Service → Events → выбрать предыдущий успешный
  деплой → Rollback
