# Deploying to Heroku

This project runs a Telegram worker that uses Selenium with headless Chrome. Below are tested steps using the chrome-for-testing buildpack.

## Prerequisites
- Heroku account and Heroku CLI installed
- Git repository with this code on the `main` branch
- Telegram bot token from @BotFather

## One-time App Setup
```zsh
# create the app (or use an existing one)
heroku create <your-app-name>

# add buildpacks (order matters)
# 1) Install Chrome + Chromedriver (chrome-for-testing)
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-chrome-for-testing
# 2) Python runtime + dependencies
heroku buildpacks:add --index 2 heroku/python

# required configuration
heroku config:set TELEGRAM_BOT_TOKEN=xxxx:yyyy
```

The `Procfile` defines a worker process: `worker: python bot.py`.

## Deploy
```zsh
git push heroku main

# scale up the worker dyno
heroku ps:scale worker=1

# check logs
heroku logs --tail
```

## Verify Chrome/Chromedriver Availability (optional)
```zsh
heroku run 'which google-chrome || which chrome || which chromium || echo no-chrome'
heroku run 'which chromedriver || echo no-chromedriver'
```

The chrome-for-testing buildpack places Chrome and Chromedriver on the `PATH`, so no extra configuration is typically needed. The app already uses headless flags in Selenium options.

## Troubleshooting
- Stuck at login/OTP: Try again; SRS or Webmail may be slow. Ensure credentials are correct.
- Driver not found: Confirm buildpack order and verify binaries with the commands above.
- Dyno sleeping: For always-on behavior, use a paid dyno or another host.
- Region/network issues: If OTP emails are delayed, increase wait time or retry later.

## Optional: Force Selenium to Use Buildpack Chromedriver
If auto-detection fails, you can explicitly point Selenium to the Chromedriver from the buildpack:

```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import os

options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

service = Service(executable_path=os.environ.get('CHROMEDRIVER_PATH'))
driver = webdriver.Chrome(service=service, options=options)
```

Only apply this change if you observe driver resolution issues on Heroku.
