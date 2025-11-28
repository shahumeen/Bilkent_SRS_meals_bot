# Bilkent SRS Meals Bot 🍽️

Check your remaining SRS meals quickly and securely via Telegram.

Try it now: https://t.me/SRSMealsBOT

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)
![Selenium](https://img.shields.io/badge/Selenium-4.15-green)

---

## What It Does
- Fetches your SRS remaining meals from STARS automatically.
- Handles OTP/2FA by logging into Bilkent Webmail and parsing the verification email.
- Deletes your credentials message immediately for privacy.
- Provides live status updates while working (login → OTP → fetch → result).
- Prevents spam with temporary bans and per‑user concurrency.

Source code: https://github.com/shahumeen/Bilkent_SRS_meals_bot

---

## How To Use (Telegram)
1. Open the bot: https://t.me/SRSMealsBOT
2. Send `/start` to see instructions and an example.
3. Send ONE message with 4 lines in this exact order:
   ```
   <SRS ID>
   <SRS Password>
   <Bilkent Email>
   <Email Password>
   ```
   Example:
   ```
   12345678
   SRSPass123
   name.surname@ug.bilkent.edu.tr
   emailPass456
   ```
4. Wait for the status updates and result.

Privacy note: Your message is deleted right after it’s processed. No credentials are stored.

---

## Local Development

### Prerequisites
- Python 3.11 (see `runtime.txt`)
- Google Chrome (headless)
- Selenium 4.15 (Selenium Manager typically fetches the matching ChromeDriver automatically)

### Setup
```zsh
# from repo root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set TELEGRAM_BOT_TOKEN from @BotFather
```

### Run
```zsh
python bot.py
```

---

## Configuration
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from @BotFather (see `.env.example`).

No other environment variables are required. The bot runs in polling mode.

---

## Deployment (Heroku)
This repo includes `Procfile` and `runtime.txt` for Heroku. For a detailed guide, see `deploy.md`.

1. Create the app and set the token:
```zsh
heroku create <your-app-name>
heroku config:set TELEGRAM_BOT_TOKEN=xxxx:yyyy
```

2. Add buildpacks (order matters):
```zsh
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-chrome-for-testing
heroku buildpacks:add --index 2 heroku/python
```

3. Deploy and scale the worker:
```zsh
git push heroku main
heroku ps:scale worker=1
heroku logs --tail
```

If you use another platform, ensure headless Chrome is available at runtime.

---

## Architecture Overview
- `bot.py`: Telegram bot using `python-telegram-bot` v22.5+
  - Commands: `/start`
  - Message handler: expects 4‑line credentials, deletes it, spawns a per‑user async task, live‑updates status, reports remaining meals.
  - Anti‑spam: in‑memory rate limit with temporary bans.
- `get_remaining_meals.py`: Logs into STARS (SRS), triggers OTP, fetches meals page, extracts the remaining count via robust patterns.
- `get_otp.py`: Logs into Bilkent Webmail, finds the latest STARS verification email, extracts the OTP, deletes the email.

Data persistence: none. All state is in memory and ephemeral.

---

## Troubleshooting
- Invalid format: The bot requires exactly 4 lines in a single message.
- OTP failed: Webmail delay or layout changes can cause issues. Try again.
- Wrong credentials: Double‑check SRS and email password.
- SRS down: If STARS/SRS is unavailable, fetching will fail temporarily.
- Spam protection: Sending too many messages quickly results in a temporary ban.

---

## Security & Disclaimer
- This bot does not store your credentials. Messages are deleted once processed.
- Use at your own risk. You are responsible for your account security.

---

## License
This project is licensed under the terms of the repository `LICENSE` file.

---

## Credits
Built with:
- `python-telegram-bot`
- `selenium`
- `python-dotenv`

Afiyet olsun! 😋
