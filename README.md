# Railway-ready Telegram Bot

This project is a complete Telegram bot built with **pyTelegramBotAPI** and prepared for deployment on **Railway.app**.

## Included
- Admin/User panel keyboards
- `/start` command
- `🔙 User Panel` handler from your code
- Railway deployment files

## Environment Variables
Set these in Railway:

- `TELEGRAM_BOT_TOKEN` = your Telegram bot token from BotFather
- `ADMIN_IDS` = comma-separated Telegram user IDs that should have admin access

Example:

```env
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
ADMIN_IDS=123456789,987654321
```

## Local Run
```bash
pip install -r requirements.txt
python bot.py
```

## Deploy on Railway
1. Create a new project on Railway.
2. Upload this project or connect a GitHub repo.
3. Add the environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_IDS`
4. Deploy.

Railway will use the `Procfile`:

```txt
worker: python bot.py
```

## Notes
- This version uses **long polling**, which is the simplest way to run on Railway.
- The `Users` section is a placeholder. Add a database later if you want persistent storage.
