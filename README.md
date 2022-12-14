# sharesight-bot

_This project has no affiliation with Sharesight Ltd._

## Description
* Trade notifications
* Intraday price movements for holdings over a defined threshold
* Earnings date reminders for your holdings
* Ex-dividend date warnings for your holdings
* Highly shorted stock warnings for your holdings (AU, US)
* Discord, Slack and Telegram support
* Supports multiple Sharesight portfolios, including portfolios shared to you
* For speed and reliability, no use of uncommon libraries or screen scraping
* Interactive chat commands (alpha)

![screenshot of Slack message](img/screenshot.png?raw=true "Screenshot of Slack message")

## Dependencies
* Sharesight paid plan, preferably with automatic trade imports, and an API key
* Slack / Discord webhooks / Telegram bot user
* Python 3
* Python modules:
```
bs4 datetime python-dotenv requests
```

## Installation (Linux)
```
sudo pip3 install git bs4 datetime python-dotenv requests
```

```
git clone https://github.com/robdevops/sharesight-bot.git ~/sharesight-bot
```

## Setup
Configuration is set by the .env file in the parent directory. Example:
```
vi ~/sharesight-bot/.env
```

### Sharesight
* Email Sharesight support to get an API key and add the [access details](https://portfolio.sharesight.com/oauth_consumers) to the .env file. Example:
```
sharesight_code = '01d692d4de7mockupfc64bc2e2f01d692d4de72986ea808f6e99813f'
sharesight_client_id = '01d692d4de7mockupfc64bc2e2f01d692d4de72986ea808f6e99813f'
sharesight_client_secret = '01d692d4de7mockupfc64bc2e2f01d692d4de72986ea808f6e99813f'
```

### Discord
* We use Discord's Slack compatibility by appending `/slack` to the Discord webhook in the .env file. Example:
```
discord_webhook = 'https://discord.com/api/webhooks/1009998000000000000/AbCdEfGhIjKlMnOmockupvWxYz-AbCdEfGhIjKlMn/slack'
```

### Slack
* Slack support simply requires the Slack webhook in the .env file. Example:
```
slack_webhook = 'https://hooks.slack.com/services/XXXXXXXXXXX/YYYYYYYYYYY/AAAAAAAAmockupAAAAAAAAAAAA'
```

### Telegram
* Set up the bot by messaging [BotFather](https://telegram.me/BotFather).
* Add your bot to a group or channel.
* In the .env file, add your bots token to `telegram_url` in form `https://api.telegram.org/botTOKEN/`
  * Ensure `bot` is prepended to the token.
* In the .env file, set `telegram_chat_id` to the chat group or channel id.
   * For channels and supergroups, _CHAT_ID_ should be negative and 13 characters. Prepend `-100` if necessary.
   * Be aware a group id can change if you edit group settings and it becomes a "supergroup". Currently, the bot does not automatically handle this.
* Example .env entry:
```
telegram_url = 'https://api.telegram.org/bot0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAA/'
telegram_chat_id = '-1001000000000'
```

### Portfolios
Portfolios are auto-discovered, including other people's portfolios which are shared to you. To exclude specific portfolios, add their IDs to `exclude_portfolios` in the .env file:
```
exclude_portfolios = "100003 100004"
```

Alternatively, you can include only specific portfolios:
```
include_portfolios = "100001 100002"
```

### Watchlist
Tracks securities which are not in your Sharesight holdings. Use the Yahoo! Finance ticker format. Example:
```
watchlist = "RMBS STEM ZS SYR.AX 2454.TW"
```

### Caching
Many object sources are cached for 1 day by default. Cache is controlled by the settings below. Trades are not cached.
```
cache=True
cache_seconds=82800
```

## Reports

### Trades
![trade update in Slack](img/trades.png?raw=true "Trade update in Slack")

`trades.py` sends recent Sharesight trades to your configured chat services.
* To avoid duplicate trades, you can either limit this to one run per day (after market close), or run it in an environment with persistent storage. To allow frequent runs, known trades are tracked in a state file defined by `state_file` in the .env file.
* By default, this report only checks for trades for the current day. You can override this with `past_days` in the .env file. This is useful if Sharesight imports trades with past dates for any reason. Without persistent storage, it is recommended to leave this set to 0. With persistent storage, it is recommended to set it to 31. In this case, the first run will send all historical trades for the period.
```
state_file = '/tmp/sharesight-bot-trades.txt'
past_days = 31
```

### Price alerts
![price alert in Slack](img/price.png?raw=true "Price alert in Slack")

`prices.py` sends intraday price alerts for Sharesight holdings if the movement is over a percentage threshold. This data is sourced from Yahoo! Finance. The default threshold is 10% but you can change it by setting `price_percent` in the .env file. Decimal fractions are accepted. Example:
```
price_percent = 9.4
```

### Price alerts (pre-market)

`premarket.py` sends pre/post market price alerts for Sharesight holdings if the movement is over a percentage threshold. This data is sourced from Yahoo! Finance. The default threshold is 10% but you can change it by setting `price_percent` in the .env file. Decimal fractions are accepted. Example:
```
price_percent = 9.4
```

### Earnings reminders
![earnings message in Slack](img/earnings.png?raw=true "Earnings message in Slack")

`earnings.py` sends upcoming earnings date alerts. The data is sourced from Yahoo! Finance. Events more than `future_days` into the future will be ignored. **Explanation:** when a company releases its quarterly earnings report, the stock price may undergo a signficant positive or negative movement, depending on whether the company beat or missed market expectations. You may wish to hold off buying more of this stock until after its earnings report, unless you think the stock will beat market expectations.
```
future_days = 7
```

### Ex-dividend warnings
![ex-dividend warning in Slack](img/ex-dividend.png?raw=true "Ex-dividend warning in Slack")

`ex-dividend.py` sends upcoming ex-dividend date alerts. The data is sourced from Yahoo! Finance. Events more than `future_days` into the future will be ignored. **Explanation:** When a stock goes ex-dividend, the share price [typically drops](https://www.investopedia.com/articles/stocks/07/ex_dividend.asp) by the amount of the dividend paid. If you buy right before the ex-dividend date, you can expect an unrealised capital loss, plus a tax obligation for the dividend. Thus, you may wish to wait for the ex-dividend date before buying more of this stock.
```
future_days = 7
```

### Highly shorted stock warnings
`shorts.py` sends highly shorted stock warnings. The data is sourced from Yahoo Finance and Shortman (AU). `shorts_percent` defines the alert threshold for the percentage of a stock's float shorted. **Explanation:** A high short ratio indicates a stock is exposed to high risks, such as potential banktrupcy. It may also incentivise negative news articles which harm the stock price. If the market is wrong, however, risk tolerant investors may receive windfall gains. This report is intended to alert you to an above-average risk, and prompt you to investigate this stock more closely. 
```
shorts_percent = 15
```


## Scheduling example
Recommended for a machine set to UTC:
```
# Every 20 minutes on weekdays
*/20 * * * Mon-Fri ~/sharesight-bot/trades.py > /dev/null

# Daily
30  21 * * * ~/sharesight-bot/finance_calendar.py > /dev/null

# Daily on weekdays
29  21 * * Mon-Fri ~/sharesight-bot/price.py > /dev/null

# Weekly
28  21 * * Fri { cd ~/sharesight-bot/; ./earnings.py; ./ex-dividend.py ;} > /dev/null

# Monthly
27  21 1 * * ~/sharesight-bot/shorts.py > /dev/null
```
The above can be installed with:
```
(crontab -l ; cat ~/sharesight-bot/crontab.txt)| crontab -
```

## Interactive bot
Currently in alpha and supporting only Telegram. You need to host `mywsgi.py` and point `telegram_outgoing_webhook` to it. Supported commands:
```
!AAPL
!AAPL bio
!holdings
!premarket [percent]
!shorts [percent]
!trades [days]
!watchlist
!watchlist [add|del] AAPL
@botname AAPL
@botname AAPL bio
@botname holdings
@botname premarket [percent]
@botname shorts [percent]
@botname trades [days]
@botname watchlist
@botname watchlist [add|del] AAPL
```

## Serverless
_The following are notes from an AWS Lambda install and may not be current_
### Installation
To prepare zip for upload to cloud:
```
cd ~/sharesight-bot
pip3 install datetime python-dotenv requests --upgrade --target=$(pwd)
zip -r script.zip .
```

### Configuration
For four portfolios (72 holdings) and with all features enabled, this script takes the better part of a minute to run. It is recommended to set _Lambda > Functions > YOUR_FUNCTION > Configuration > General configuration > Edit > Timeout_ to 2 minutes.

### Scheduling
For AWS, go to _Lambda > Functions > YOUR_FUNCTION > Add Trigger > EventBridge (Cloudwatch Events)_, and set _Schedule expression_ to, for example, 10 PM Monday to Friday UTC:
```
cron(0 22 ? * 2-6 *)
```

## Limitations
* Discord shows garbage link previews from Sharesight. Modify the script to remove hyperlinks, or disable this for your Discord account under _Settings > Text & Images > Embeds and link previews._

## Suggestions
* Know a chat or notification service with a REST API?
* Is my code is doing something the hard way?
* Something important is missing from this README?

Log an [issue](https://github.com/robdevops/sharesight-bot/issues)!
