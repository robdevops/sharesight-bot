# Import the necessary modules
from wsgiref.simple_server import make_server
from gevent import pywsgi
from html import escape
import numpy
#from itertools import pairwise # python 3.10
from itertools import groupby

import json, re, time
from lib.config import *
import lib.util as util
import lib.webhook as webhook
import lib.yahoo as yahoo
import lib.telegram as telegram
import lib.sharesight as sharesight
import premarket
import shorts
import trades

botName = '@' + telegram.getBotName()
interactive=True

def main(env, start_response):
    user=''
    request_body = env['wsgi.input'].read()
    inbound = json.loads(request_body)
    
    # Set the response status code and headers
    status = '200 OK'
    headers = [('Content-type', 'application/json')]
    start_response(status, headers)
    
    # Return the response body
    #try:
    #    print("Incoming request:", json.dumps(inbound, indent=4))
    #except Exception as e:
    #    print(e, "raw body: ", inbound)

    # read telegram message
    if "message" in inbound:
        if "text" in inbound["message"]:
            message = inbound["message"]["text"]
            chat_id = inbound["message"]["chat"]
            chat_id = str(chat_id["id"])
            if "username" in inbound["message"]["from"]:
                user = '@' + inbound["message"]["from"]["username"]
            else:
                user = '@' + inbound["message"]["from"]["first_name"]
            print(message)
        else:
            print("unhandled 'message' without 'text'")
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [b'<h1>Unhandled</h1>']
    elif "edited_message" in inbound:
        if "text" in inbound["edited_message"]:
            message = inbound["edited_message"]["text"]
            chat_id = inbound["edited_message"]["chat"]
            chat_id = str(chat_id["id"])
            if "username" in inbound["edited_message"]["from"]:
                user = inbound["edited_message"]["from"]["username"]
            else:
                user = inbound["edited_message"]["from"]["first_name"]
            print(message)
        else:
            print("unhandled 'edited_message' without 'text'")
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [b'<h1>Unhandled</h1>']
    elif "channel_post" in inbound:
        message = inbound["channel_post"]["text"]
        chat_id = inbound["channel_post"]["chat"]["id"]
        user = ''
        print(message)
    else:
        print("unhandled not 'message' nor 'channel_post'")
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [b'<h1>Unhandled</h1>']

    # read bot command
    stockfinancial_command = "^\!([\w\.]+)\s*(bio|info|profile)*|^" + botName + "\s+([\w\.]+)\s*(bio|info|profile)*"
    watchlist_command = "^\!watchlist\s*([\w]+)*\s*([\w\.]+)*|^" + botName + "\s+watchlist\s*(\w+)*\s*([\w\.]+)*"
    trades_command = "^\!trades\s*(\d+)*|^" + botName + "\s+trades\s*(\d+)*"
    holdings_command = "^\!holdings\s*([\w\s]+)*|^" + botName + "\s+holdings\s*([\w\s]+)*"
    shorts_command = "^\!shorts\s*([\d]+)*|^" + botName + "\s+shorts\s*([\d]+)*"
    premarket_command = "^\!premarket\s*([\d]+)*|^" + botName + "\s+premarket\s*([\d]+)*"
    m_stockfinancial = re.match(stockfinancial_command, message)
    m_watchlist = re.match(watchlist_command, message)
    m_trades = re.match(trades_command, message)
    m_holdings = re.match(holdings_command, message)
    m_shorts = re.match(shorts_command, message)
    m_premarket = re.match(premarket_command, message)
    if m_watchlist:
        action = False
        ticker = False
        if m_watchlist.group(3) and m_watchlist.group(4):
            action = m_watchlist.group(3)
            ticker = m_watchlist.group(4).upper()
        elif m_watchlist.group(1) and m_watchlist.group(2):
            action = m_watchlist.group(1)
            ticker = m_watchlist.group(2).upper()
        if action in {'del', 'rem', 'rm', 'delete', 'remove'}:
            action = 'delete'
        for service in webhooks:
            payload = prepare_watchlist("telegram", user, action, ticker)
            url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
            if service == 'telegram':
                webhook.payload_wrapper("telegram", url, payload)
            return [b"<b>OK</b>"]
    elif message in ("!help", "!usage", botName + " help", botName + " usage"):
        for service in webhooks:
            payload = prepare_help("telegram", user)
            url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
            if service == 'telegram':
                webhook.payload_wrapper("telegram", url, payload)
            return [b"<b>OK</b>"]
    elif m_premarket:
        premarket_threshold = config_price_percent
        if m_premarket.group(2):
            premarket_threshold = int(m_premarket.group(2))
        elif m_premarket.group(1):
            premarket_threshold = int(m_premarket.group(1))
        for service in webhooks:
            payload = prepare_help("telegram", user)
            if service == 'telegram':
                premarket.lambda_handler(chat_id, interactive, user, premarket_threshold)
            return [b"<b>OK</b>"]
    elif m_shorts:
        shorts_threshold = config_shorts_percent
        if m_shorts.group(2):
            shorts_threshold = int(m_shorts.group(2))
        elif m_shorts.group(1):
            shorts_threshold = int(m_shorts.group(1))
        for service in webhooks:
            if service == 'telegram':
                shorts.lambda_handler(chat_id, interactive, user, shorts_threshold)
            return [b"<b>OK</b>"]
    elif message in ("!todo", "!roadmap", botName  + " todo", botName + " roadmap"):
        for service in webhooks:
            payload = prepare_todo("telegram", user)
            url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
            if service == 'telegram':
                webhook.payload_wrapper("telegram", url, payload)
            return [b"<b>OK</b>"]
    elif m_trades:
        if m_trades.group(2):
            days = int(m_trades.group(2))
        elif m_trades.group(1):
            days = int(m_trades.group(1))
        else:
            days = 1
        payload = [ f"{user}", f"beep boop. Rummaging for trades from the past {days} days 🔍" ]
        url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
        webhook.payload_wrapper("telegram", url, payload)
        for service in webhooks:
            if service == 'telegram':
                trades.lambda_handler(chat_id, interactive, user, days)
            return [b"<b>OK</b>"]
    elif m_holdings:
        payload = []
        portfolioName = False
        print("Starting holdings report")
        if m_holdings.group(2):
            portfolioName = m_holdings.group(2)
        elif m_holdings.group(1):
            portfolioName = m_holdings.group(1)
        portfolios = sharesight.get_portfolios()
        portfoliosLower = {k.lower():v for k,v in portfolios.items()}
        if portfolioName:
            if portfolioName.lower() in portfoliosLower:
                portfolioId = portfoliosLower[portfolioName.lower()]
                tickers = sharesight.get_holdings(portfolioName, portfolioId)
                market_data = yahoo.fetch(tickers)
                print("")
                brief = True
                for item in market_data:
                    ticker = market_data[item]['ticker']
                    title = market_data[item]['profile_title']
                    for service in webhooks:
                        yahoo_link = utils.yahoo_link(ticker, service, brief)
                    payload.append(f"{title} ({yahoo_link})")
                portfoliosReverseLookup = {v:k for k,v in portfolios.items()}
                payload.sort()
                payload.insert(0, f"<b>Holdings for {portfoliosReverseLookup[portfolioId]}</b>")
            else:
                payload = [ f"{user} {portfolioName} portfolio not found. I only know about:" ]
                for item in portfolios:
                    payload.append( item )
        else:
            payload = [ f"{user} Please try again specifying a portfolio:" ]
            for item in portfolios:
                payload.append( item )
        for service in webhooks:
            url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
            if service == 'telegram':
                webhook.payload_wrapper("telegram", url, payload)
        return [b"<b>OK</b>"]

    elif m_stockfinancial:
        print("starting stock detail")
        bio=False
        if m_stockfinancial.group(3):
            ticker = m_stockfinancial.group(3).upper()
            if m_stockfinancial.group(4):
                bio=True
        elif m_stockfinancial.group(1):
            ticker = m_stockfinancial.group(1).upper()
            if m_stockfinancial.group(2):
                bio=True
        for service in webhooks:
            payload = prepare_stockfinancial_payload("telegram", user, ticker, bio)
            url = webhooks["telegram"] + 'sendMessage?chat_id=' + str(chat_id)
            if service == 'telegram':
                webhook.payload_wrapper("telegram", url, payload)
            return [b"<b>OK</b>"]
    else:
        #print(message, "is not a bot command")
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [b"<b>OK</b>"]

def doDelta(inputList):
    deltaString = ''
    #deltaList = [j-i for i,j in zip(inputList, inputList[1:])]
    #deltaList = [y-x for (x,y) in pairwise(inputList)] # python 3.10
    deltaList = numpy.diff(inputList)
    for delta in deltaList:
        if delta < 0:
            deltaString = deltaString + '🔻'
        elif delta > 0:
            deltaString = deltaString + '🔼'
        else:
            deltaString = deltaString + '▪️'
    return deltaString

def prepare_watchlist(service, user, action=False, ticker=False):
    if ticker:
        ticker_link = util.yahoo_link(ticker, service)
        ticker_orig = ticker.upper()
        ticker = ticker.upper()
    duplicate = False
    transformed = False
    cache_file = config_cache_dir + "/sharesight_watchlist.json"
    if os.path.isfile(cache_file):
        with open(cache_file, "r") as f:
            watchlist = json.loads(f.read())
    else:
        watchlist = list(config_watchlist)
    print(watchlist)
    if action == 'add':
        if ticker in watchlist:
            duplicate = True
        else:
            watchlist.append(ticker)
    market_data = yahoo.fetch(watchlist)
    print("")
    if action == 'delete':
        if ticker in watchlist:
            watchlist.remove(ticker)
        else:
            print(ticker, "not in watchlist")
    if action == 'add':
        if '.' not in ticker and ticker not in market_data:
            watchlist.remove(ticker)
            ticker = ticker + '.AX'
            transformed = True
            ticker_link = util.yahoo_link(ticker, service)
            print(ticker_orig, "not found. Trying", ticker)
            if ticker in watchlist:
                print(ticker, "already in watchlist")
                duplicate = True
            else:
                watchlist.append(ticker)
                market_data = yahoo.fetch(watchlist)
                print("")
                if ticker in market_data:
                    print("found", ticker)
                else:
                    watchlist.remove(ticker)
                    print(ticker, "not found")
        elif ticker not in market_data:
            watchlist.remove(ticker)

    print(watchlist)

    payload = []
    for item in market_data:
        item_link = util.yahoo_link(item, service)
        profile_title = market_data[item]['profile_title']
        if item == ticker and action == 'delete':
            pass
        elif item == ticker and action == 'add': # make the requested item bold
            payload.append(f"<b>{profile_title} ({item_link})</b>")
        else:
            payload.append(f"{profile_title} ({item_link})")

    def profile_title(e): # disregards the <b> in sort command
        return re.findall('[A-Z].*', e)
    payload.sort(key=profile_title)

    if action == 'delete':
        if ticker not in market_data:
            payload.insert(0, f"Beep Boop. I could not find <b>{ticker}</b> to remove it")
        else:
            payload.insert(0, f"Ok {user}, I deleted <b>{ticker_link}</b>")

    elif action == 'add':
        if ticker not in market_data:
            payload = [f"{user}", f"Beep Boop. I could not find <b>{ticker_orig}</b> to add it"]
        elif transformed and duplicate:
            print("ticker au and duplicate")
            payload.insert(0, f"Beep Boop. I could not find <b>{ticker_orig}</b> and I'm already tracking <b>{ticker_link}</b>")
        elif transformed:
            payload.insert(0, f"Beep Boop. I could not find <b>{ticker_orig}</b> so I added <b>{ticker_link}</b>")
        elif duplicate:
            print("ticker us and duplicate")
            payload.insert(0, f"{user}, I'm already tracking <b>{ticker_link}</b>")
        else:
            payload.insert(0, f"Ok {user}, I added <b>{ticker_link}</b>")
    elif action == False:
        payload.insert(0, f"Hi {user}, I'm currently tracking:")

    with open(cache_file, "w") as f:
        f.write(json.dumps(watchlist))
    return payload

def prepare_help(service, user):
    payload = []
    payload.append("<b>Examples:</b>")
    payload.append("!AAPL")
    payload.append("!AAPL bio")
    payload.append("!holdings")
    payload.append("!premarket [percent]")
    payload.append("!shorts [percent]")
    payload.append("!trades [days]")
    payload.append("!watchlist")
    payload.append("!watchlist [add|del] AAPL")
    payload.append(botName + " AAPL")
    payload.append(botName + " AAPL bio")
    payload.append("etc.")
    return payload

def prepare_stockfinancial_payload(service, user, ticker, bio):
    cashflow = False
    ticker_orig = ticker
    tickerNative = ticker.split('.')[0]
    now = int(time.time())
    payload = []
    market_data = yahoo.fetch_detail(ticker, 600)
    print("")
    if not market_data and '.' not in ticker:
        ticker = ticker + '.AX'
        print("trying again with", ticker)
        market_data = yahoo.fetch_detail(ticker, 600)
        print("")
    if not market_data:
        payload = [ f"{user} 🛑", f"Beep Boop. I could not find {ticker_orig}" ]
        return payload
    #print("Yahoo data:", json.dumps(market_data, indent=4))
    yahoo_link = util.yahoo_link(ticker, service)
    profile_title = market_data[ticker]['profile_title']
    if 'marketState' in market_data[ticker]:
        marketState = market_data[ticker]['marketState'].rstrip()
        if marketState == 'REGULAR':
            marketStateEmoji = '🟢'
        elif marketState in {'PRE', 'POST'}:
            marketStateEmoji = '🟠'
        else:
            marketStateEmoji = '🔴'
    if 'profile_exchange' in market_data[ticker]:
        profile_exchange = market_data[ticker]['profile_exchange']
        swsURL = 'https://www.google.com/search?q=site:simplywall.st+(' + profile_title + '+' + profile_exchange + ':' + ticker.split('.')[0] + ')+Stock+Price+Quote+Analysis&btnI'
        swsLink = '<a href="' + swsURL + '">Simply Wall St</a>'
        if profile_exchange == 'ASX':
            market_url = 'https://www2.asx.com.au/markets/company/' + ticker.split('.')[0]
            shortman_url = 'https://www.shortman.com.au/stock?q=' + ticker.split('.')[0].lower()
            shortman_link = '<a href="' + shortman_url + '">shortman</a>'
        elif profile_exchange == 'HKSE':
            market_url = 'https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=' + ticker.split('.')[0] + '&sc_lang=en'
        elif 'Nasdaq' in profile_exchange:
            market_url = 'https://www.nasdaq.com/market-activity/stocks/' + ticker.lower()
        elif profile_exchange == 'NYSE':
            market_url = 'https://www.nyse.com/quote/XNYS:' + ticker
        elif profile_exchange == 'Taiwan':
            profile_exchange = 'TWSE'
            market_url = 'https://mis.twse.com.tw/stock/fibest.jsp?stock=' + ticker.split('.')[0] + '&lang=en_us'
        elif profile_exchange == 'Tokyo':
            profile_exchange = 'JPX'
            market_url = 'https://quote.jpx.co.jp/jpx/template/quote.cgi?F=tmp/e_stock_detail&MKTN=T&QCODE=' + ticker.split('.')[0]
        else:
            market_url = 'https://www.google.com/search?q=stock+exchange+' + profile_exchange + '+' + ticker.split('.')[0] + '&btnI'
        market_link = '<a href="' + market_url + '">' + profile_exchange + '</a>'
    if bio:
        location = []
        if 'profile_city' in market_data[ticker]:
            location.append(market_data[ticker]['profile_city'])
        if 'profile_state' in market_data[ticker]:
            location.append(market_data[ticker]['profile_state'])
        if 'profile_country' in market_data[ticker]:
            profile_country = market_data[ticker]['profile_country']
            location.append(profile_country)
        if 'profile_bio' in market_data[ticker]:
            payload.append(f"{market_data[ticker]['profile_bio']}")
            payload.append("")
        if location:
            payload.append(f"<b>Location:</b> " + ', '.join(location))
        if 'profile_industry' in market_data[ticker] and 'profile_sector' in market_data[ticker]:
            payload.append(f"<b>Classification:</b> {market_data[ticker]['profile_industry']}, {market_data[ticker]['profile_sector']}")
        if 'profile_employees' in market_data[ticker]:
            payload.append(f"<b>Employees:</b> {market_data[ticker]['profile_employees']:,}")
        if 'profile_website' in market_data[ticker]:
            payload.append(f"<b>Website:</b> {market_data[ticker]['profile_website']}")
        if 'profile_website' in market_data[ticker]:
            if profile_exchange == 'NYSE' or 'Nasdaq' in profile_exchange:
                finvizURL='https://finviz.com/quote.ashx?t=' + ticker
                marketwatchURL = 'https://www.marketwatch.com/investing/stock/' + ticker.lower()
                seekingalphaURL='https://seekingalpha.com/symbol/' + ticker
                finvizLink='<a href="' + finvizURL + '">Finviz</a>'
                marketwatchLink='<a href="' + marketwatchURL + '">MarketWatch</a>'
                seekingalphaLink='<a href="' + seekingalphaURL + '">Seeking Alpha</a>'
                payload.append(f"<b>Other links:</b> {market_link} | {finvizLink} | {seekingalphaLink} | {marketwatchLink} | {swsLink}")
            elif profile_exchange == 'ASX':
                payload.append(f"<b>Other links:</b> {market_link} | {shortman_link} | {swsLink}")
            else:
                payload.append(f"<b>Other links:</b> {market_link} | {swsLink}")
        if ticker_orig == ticker:
            payload.insert(0, f"<b>{profile_title} ({yahoo_link})</b>")
        else:
            payload.insert(0, f"Beep Boop. I could not find " + ticker_orig + ", but I found " + yahoo_link)
            payload.insert(1, "")
            payload.insert(2, f"<b>{profile_title} ({yahoo_link})</b>")
        if len(payload) < 2:
            payload.append("no data found")
        payload = [i[0] for i in groupby(payload)]
        return payload
    if 'currency' in market_data[ticker] and 'market_cap' in market_data[ticker]:
        currency = market_data[ticker]['currency']
        market_cap = market_data[ticker]['market_cap']
        market_cap = util.humanUnits(market_cap)
        payload.append(f"<b>Mkt cap:</b> {currency} {market_cap}")
    if 'free_cashflow' in market_data[ticker]:
        cashflow = market_data[ticker]['free_cashflow']
    elif 'operating_cashflow' in market_data[ticker]:
        cashflow = market_data[ticker]['operating_cashflow']
    if 'shareholder_equity' in market_data[ticker] and 'total_debt' in market_data[ticker]:
        total_debt = market_data[ticker]['total_debt']
        shareholder_equity = market_data[ticker]['shareholder_equity']
        debt_equity_ratio = round(total_debt / shareholder_equity * 100)
        profile_industry = market_data[ticker]['profile_industry']
        if 'total_cash' in market_data[ticker]:
            total_cash = market_data[ticker]['total_cash']
            if 'Bank' not in profile_industry:
                emoji = ''
                net_debt_equity_ratio = round(((total_debt - total_cash) / shareholder_equity * 100))
                if net_debt_equity_ratio > 40:
                    emoji = '⚠️ '
                if net_debt_equity_ratio > 0:
                    payload.append(f"<b>Net debt/equity ratio:</b> {net_debt_equity_ratio}%{emoji}")
    if 'earnings_date' in market_data[ticker]:
        earnings_date = market_data[ticker]['earnings_date']
        human_earnings_date = time.strftime('%b %d', time.localtime(earnings_date))
        if earnings_date > now:
            payload.append(f"<b>Earnings date:</b> {human_earnings_date}")
        else:
            print("Skipping past earnings:", ticker, human_earnings_date)
    if 'dividend' in market_data[ticker]:
        dividend = market_data[ticker]['dividend']
        if market_data[ticker]['dividend'] > 0:
            dividend = str(market_data[ticker]['dividend']) + '%'
            payload.append(f"<b>Dividend:</b> {dividend}")
            if 'ex_dividend_date' in market_data[ticker]:
                ex_dividend_date = market_data[ticker]['ex_dividend_date']
                human_exdate = time.strftime('%b %d', time.localtime(ex_dividend_date))
                if ex_dividend_date > now:
                    payload.append(f"<b>Ex-dividend date:</b> {human_exdate}")
                else:
                    print("Skipping past ex-dividend:", ticker, human_exdate)
    if cashflow:
        if cashflow < 0:
            payload.append(f"<b>Cashflow positive:</b> no⚠️ ")
        else:
            payload.append(f"<b>Cashflow positive:</b> yes")
    if 'net_income' in market_data[ticker]:
        if market_data[ticker]['net_income'] < 0:
            payload.append(f"<b>Profitable:</b> no ⚠️ ")
        else:
            payload.append(f"<b>Profitable:</b> yes")

    payload.append("")

    if 'earningsQ' in market_data[ticker]:
        revenueQs = doDelta(market_data[ticker]['earningsQ'])
        earningsQs = doDelta(market_data[ticker]['revenueQ'])
        revenueYs = doDelta(market_data[ticker]['revenueY'])
        earningsYs = doDelta(market_data[ticker]['earningsY'])
        payload.append(f"{revenueQs}  quarterly revenue")
        payload.append(f"{earningsQs}  quarterly earnings")
        payload.append(f"{revenueYs}  yearly revenue")
        payload.append(f"{earningsYs}  yearly earnings")

    payload.append("")

    if 'revenueEstimateY' in market_data[ticker]:
        revenueEstimateY = int(round(market_data[ticker]['revenueEstimateY']))
        earningsEstimateY = int(round(market_data[ticker]['earningsEstimateY']))
        revenueAnalysts = market_data[ticker]['revenueAnalysts']
        earningsAnalysts = market_data[ticker]['earningsAnalysts']
        payload.append(f"<b>Revenue growth forecast (1Y):</b> {revenueEstimateY}%")
        payload.append(f"<b>Earnings growth forecast (1Y):</b> {earningsEstimateY}%")
    if 'insiderBuy' in market_data[ticker]:
        emoji=''
        insiderBuy = market_data[ticker]['insiderBuy']
        insiderSell = market_data[ticker]['insiderSell']
        insiderBuyValue = market_data[ticker]['insiderBuyValue']
        insiderSellValue = market_data[ticker]['insiderSellValue']
        if insiderBuy > insiderSell:
            action = 'Buy'
            humanValue = util.humanUnits(insiderBuyValue)
            payload.append(f"<b>Net insider action (3M)</b>: {action} {currency} {humanValue}{emoji}")
        elif insiderBuy < insiderSell:
            emoji = '⚠️ '
            action = 'Sell'
            humanValue = util.humanUnits(insiderSellValue)
            payload.append(f"<b>Net insider action (3M)</b>: {action} {currency} {humanValue}{emoji}")
    if 'short_percent' in market_data[ticker]:
        emoji=''
        short_percent = market_data[ticker]['short_percent']
        if short_percent > 10:
            emoji = '⚠️ '
        payload.append(f"<b>Shorted stock:</b> {short_percent}%{emoji}")
    if 'recommend' in market_data[ticker]:
        recommend = market_data[ticker]['recommend']
        recommend_index = market_data[ticker]['recommend_index']
        recommend_analysts = market_data[ticker]['recommend_analysts']
        payload.append(f"<b>Score:</b> {recommend_index} {recommend} ({recommend_analysts} analysts)")

    payload.append("")

    if 'price_to_earnings_trailing' in market_data[ticker]:
        trailingPe = int(round(market_data[ticker]['price_to_earnings_trailing']))
        payload.append(f"<b>Trailing P/E:</b> {trailingPe}")
    if 'price_to_earnings_forward' in market_data[ticker]:
        forwardPe = int(round(market_data[ticker]['price_to_earnings_forward']))
        emoji=''
        if 'Software' in market_data[ticker]['profile_industry'] and forwardPe > 100:
            emoji = '⚠️ '
        elif 'Software' not in market_data[ticker]['profile_industry'] and forwardPe > 30:
            emoji = '⚠️ '
        payload.append(f"<b>Forward P/E:</b> {forwardPe}{emoji}")
    if 'price_to_earnings_peg' in market_data[ticker]:
        peg = round(market_data[ticker]['price_to_earnings_peg'], 1)
        payload.append(f"<b>PEG ratio:</b> {peg}")
    if 'price_to_sales' in market_data[ticker]:
        price_to_sales = round(market_data[ticker]['price_to_sales'], 1)
        payload.append(f"<b>PS ratio:</b> {price_to_sales}")

    payload.append("")

    if 'percent_change_year' in market_data[ticker]:
        percent_change_year = str(market_data[ticker]['percent_change_year']) + '%'
        payload.append(f"<b>1Y:</b> {percent_change_year}")
        payload.append(f"<b>1D:</b> {market_data[ticker]['percent_change']}%")
    if 'percent_change_premarket' in market_data[ticker]:
        percent_change_premarket = str(market_data[ticker]['percent_change_premarket']) + '%'
        payload.append(f"<b>Pre-market:</b> {percent_change_premarket}")
    elif 'percent_change_postmarket' in market_data[ticker]:
        percent_change_postmarket = str(market_data[ticker]['percent_change_postmarket']) + '%'
        payload.append(f"<b>Post-market:</b> {percent_change_postmarket}")
    if ticker_orig == ticker:
        payload.insert(0, f"{profile_title} ({yahoo_link}) {marketStateEmoji}")
    else:
        payload.insert(0, f"I could not find {ticker_orig} but I found {yahoo_link}:")
        payload.insert(1, "")
        payload.insert(2, f"{profile_title} ({yahoo_link}) {marketStateEmoji}")
    payload = [i[0] for i in groupby(payload)]
    return payload

ip="127.0.0.1"
port=5000
print(f'Serving on https://{ip}:{port}')
server = pywsgi.WSGIServer((ip, port), main)
# to start the server asynchronously, call server.start()
# we use blocking serve_forever() here because we have no other jobs
server.serve_forever()
