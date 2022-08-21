#!/usr/bin/python3

import requests
from datetime import datetime
import json
import os
from dotenv import load_dotenv
import urllib.parse
import time
import yfinance as yf
import re

def lambda_handler(event,context):
    load_dotenv()
    sharesight_auth_data = {
            "grant_type": os.getenv('sharesight_grant_type'),
            "code": os.getenv('sharesight_code'),
            "client_id": os.getenv('sharesight_client_id'),
            "client_secret": os.getenv('sharesight_client_secret'),
            "redirect_uri": os.getenv('sharesight_redirect_uri')
    }
    webhooks = {}
    if os.getenv('slack_webhook'):
        webhooks['slack'] = os.getenv('slack_webhook')
    if os.getenv('discord_webhook'):
        webhooks['discord'] = os.getenv('discord_webhook')
    if os.getenv('telegram_url'):
        webhooks['telegram'] = os.getenv('telegram_url')

    if os.getenv('trade_updates'):
        trade_updates = os.getenv("trade_updates", 'False').lower() in ('true', '1', 't')

    if os.getenv('price_updates'):
        price_updates = os.getenv("price_updates", 'False').lower() in ('true', '1', 't')

    if os.getenv('price_updates_percentage'):
        price_updates_percentage = os.getenv('price_updates_percentage') 
        price_updates_percentage = float(price_updates_percentage)

    date = datetime.today().strftime('%Y-%m-%d')
    #date = '2022-08-13'
    
    class BearerAuth(requests.auth.AuthBase):
        def __init__(self, token):
            self.token = token
        def __call__(self, r):
            r.headers["Authorization"] = "Bearer " + self.token
            return r
    
    def sharesight_get_token(sharesight_auth_data):
        print("Fetching Sharesight auth token")
        try:
            r = requests.post("https://api.sharesight.com/oauth2/token", data=sharesight_auth_data)
        except:
            print(f'Failed to get Sharesight access token')
            exit(1)
            return []
    
        if r.status_code != 200:
            print(f'Could not fetch token from endpoint. Code {r.status_code}. Check config in .env file')
            exit(1)
            return []
    
        data = r.json()
        return data['access_token']


    def sharesight_get_portfolios():
        print("Fetching Sharesight portfolios")
        portfolio_dict = {}
        try:
            r = requests.get("https://api.sharesight.com/api/v2/portfolios.json", headers={'Content-type': 'application/json'}, auth=BearerAuth(token))
        except:
            print(f'Failure talking to Sharesight')
            return []
    
        if r.status_code != 200:
            print(f'Error communicating with Sharesight API. Code {r.status_code}')
            return []
    
        data = r.json()
        for portfolio in data['portfolios']:
            portfolio_dict[portfolio['name']] = portfolio['id']

        print(portfolio_dict)
        return portfolio_dict


    def sharesight_get_trades(portfolio_name, portfolio_id):
        print(f"Fetching Sharesight trades for {portfolio_name} on {date}", end=': ')
        endpoint = 'https://api.sharesight.com/api/v2/portfolios/'
        url = endpoint + str(portfolio_id) + '/trades.json' + '?start_date=' + date + '&end_date=' + date
        r = requests.get(url, auth=BearerAuth(token))
        data = r.json()
        print(len(data['trades']))
        for trade in data['trades']:
           trade['portfolio'] = portfolio_name
        return data['trades']


    def sharesight_get_holdings(portfolio_id, portfolio_name):
        print(f"Fetching Sharesight holdings for {portfolio_name}", end=': ')
        endpoint = 'https://api.sharesight.com/api/v2/portfolios/'
        url = endpoint + str(portfolio_id) + '/valuation.json?grouping=ungrouped&balance_date=' + date
        r = requests.get(url, auth=BearerAuth(token))
        data = r.json()
        print(len(data['holdings']))
        return data['holdings']

    def transform_tickers(holdings):
        tickers = {}
        for holding in holdings:
            symbol = holding['symbol']
            name = holding['name']
            market = holding['market']

            # shorten long names to reduce line wrap on mobile
            name = name.replace("- Ordinary Shares - Class A", "")
            name = name.replace("Global X Funds - Global X ", "")
            name = name.replace("- New York Shares", "")
            name = name.replace("Co (The)", " ")
            name = name.replace("- ADR", "")
            name = name.replace(" Index", " ")
            name = name.replace(" Enterprises", " ")
            name = name.replace(" Enterprise", " ")
            name = name.replace(" Enterpr", " ")
            name = name.replace(" Group", " ")
            name = name.replace(" Co.", " ")
            name = name.replace(" Holdings", " ")
            name = name.replace(" Infrastructure", " Infra")
            name = name.replace(" Technologies", " ")
            name = name.replace(" Technology", " ")
            name = name.replace(" Plc", " ")
            name = name.replace(" Limited", " ")
            name = name.replace(" Ltd", " ")
            name = name.replace(" Incorporated", " ")
            name = name.replace(" Inc", " ")
            name = name.replace(" Corporation", " ")
            name = name.replace(" Corp", " ")
            name = name.replace(" Australian", " Aus")
            name = name.replace(" Australia", " Aus")
            name = name.replace("Etf", "ETF")
            name = name.replace("Tpg", "TPG")
            name = name.replace("Rea", "REA")
            name = name.replace(" .", " ")
            name = name.replace("  ", " ")
            name = name.rstrip()
            if symbol == 'QCLN':
                name = 'NASDAQ Clean Energy ETF'
            if symbol == 'LIS' and market == 'ASX':
                name = 'LI-S Energy'
            if symbol == 'TSM':
                name = 'Taiwan Semiconductor'
            if symbol == 'MAP' and market == 'ASX':
                name = 'Microba Life Sciences'
            if symbol == 'DRNA' and market == 'NASDAQ':
                continue

            if market == 'ASX':
                tickers[symbol + '.AX'] = name
            elif market == 'NASDAQ' or market == 'NYSE' or market == 'BATS':
                tickers[symbol] = name
            else:
                continue
        return tickers
        
    def prepare_trade_payload(service, trades):
        print(f"Preparing payload: {service}")
        trade_payload = []
        for trade in trades:
            trade_id = trade['id']
            portfolio = trade['portfolio']
            date = trade['transaction_date']
            type = trade['transaction_type']
            units = round(trade['quantity'])
            price = trade['price']
            currency = trade['brokerage_currency_code']
            symbol = trade['symbol']
            market = trade['market']
            value = round(trade['value'])
            value = abs(value)
            holding_id = trade['holding_id']
            #print(f"{date} {portfolio} {type} {units} {symbol} on {market} for {price} {currency} per share.")
    
            flag=''
            if market == 'ASX':
                flag = '🇦🇺'
            elif market == 'NASDAQ' or market == 'NYSE' or market == 'BATS':
                flag = '🇺🇸'
            elif market == 'KRX' or market == 'KOSDAQ':
                flag = '🇰🇷'
            elif market == 'TAI':
                flag = '🇹🇼'
            elif market == 'HKG':
                flag = '🇭🇰'
            elif market == 'LSE':
                flag = '🇬🇧'

            action=''
            emoji=''
            if type == 'BUY':
                action = 'bought'
                emoji = '💸'
            elif type == 'SELL':
                action = 'sold'
                emoji = '💰'
    
            if service == 'telegram':
                holding_link = '<a href=https://portfolio.sharesight.com/holdings/>' + str(holding_id) + f'>{symbol}</a>'
                trade_link = '<a href=https://portfolio.sharesight.com/holdings/' + str(holding_id) + '/trades/' + str(trade_id) + f'/edit>{action}</a>'
            else:
                holding_link = '<https://portfolio.sharesight.com/holdings/' + str(holding_id) + f'|{symbol}>'
                trade_link = '<https://portfolio.sharesight.com/holdings/' + str(holding_id) + '/trades/' + str(trade_id) + '/edit' + f'|{action}>'
            trade_payload.append(f"{emoji} {portfolio} {trade_link} {currency} {value} of {holding_link} {flag}")
        return trade_payload
    
    def webhook_write(url, payload):
        # slack: "unfurl_links": false, "unfurl_media": false
        try:
            r = requests.post(url, headers={'Content-type': 'application/json'}, json={"text":payload})
        except:
            print(f'Failure talking to webhook: {url}')
            return []
    
        if r.status_code != 200:
            print(f'Error communicating with webhook. HTTP code {r.status_code}, URL: {url}')
            return []
    
    def telegram_write(url, payload):
        payload = urllib.parse.quote_plus(payload)
        url = url + '&parse_mode=HTML' + '&disable_web_page_preview=true' + '&text=' + payload
        try:
            r = requests.get(url)
        except:
            print(f'Failure talking to webhook: {url}')
            return []

        if r.status_code != 200:
            print(f'Error communicating with webhook. HTTP code {r.status_code}, URL: {url}')
            return []

    def chunker(seq, size):
        return (seq[pos:pos + size] for pos in range(0, len(seq), size))

    def percentage_change(previous, current):
        if current == previous:
            return 0
        try:
            return (abs(current - previous) / previous) * 100.0
        except ZeroDivisionError:
            return float('inf')
    
    def yahoo_get_prices(tickers):
        alert = []
        alert_telegram = []
        all_tickers_string = ' '.join(tickers)
        print("Fetching Yahoo price histories for ", all_tickers_string)
        price_data = yf.download(all_tickers_string, period="2d", group_by='ticker')
        return price_data

    def prepare_price_payload(service, price_data, price_updates_percentage):
        price_payload = []
        for ticker in tickers:
            previous = price_data[ticker].to_numpy()[0][4]
            current = price_data[ticker].to_numpy()[1][4]
            #print(ticker, previous, current)
            percentage = percentage_change(previous, current)
            percentage = round(percentage, 2)
            if percentage > price_updates_percentage:
                yahoo_url = 'https://finance.yahoo.com/quote/' + ticker
                if previous > current:
                    if service == 'telegram':
                        price_payload.append('🔻' + tickers[ticker] + ' (<a href="' + yahoo_url + '">' + ticker + '</a>) ' + "day change: -" + str(percentage) + '%')
                    else:
                        price_payload.append(f'🔻{tickers[ticker]} (<{yahoo_url}|{ticker}>) day change: -{str(percentage)}%')
                else:
                    if service == 'telegram':
                        price_payload.telegram.append('⬆️ ' + tickers[ticker] + ' (<a href="' + yahoo_url + '">' + ticker + '</a>) ' + "day change: " + str(percentage) + '%')
                    else:
                        price_payload.append(f'⬆️ {tickers[ticker]} (<{yahoo_url}|{ticker}>) day change: {str(percentage)}%')
        print(len(price_payload), "holdings moved more than", price_updates_percentage, '%')
        return price_payload

### MAIN ###
    token = sharesight_get_token(sharesight_auth_data)
    portfolios = sharesight_get_portfolios()
    trades = []
    holdings = []
    tickers = {}

    if trade_updates:
        for portfolio in portfolios:
            trades = trades + sharesight_get_trades(portfolio, portfolios[portfolio])
        if trades:
            print(len(trades), "trades found for", date)
        else:
            print("No trades found for", date)

    if price_updates and price_updates_percentage:
        for portfolio in portfolios:
            holdings = holdings + sharesight_get_holdings(portfolios[portfolio], portfolio)
        tickers = transform_tickers(holdings)
        price_data = yahoo_get_prices(tickers)
        #print(json.dumps(tickers, indent=4, sort_keys=True))

    for service in webhooks:
        if trades:
            print(f"Preparing {service} trades payload")
            trade_payload = prepare_trade_payload(service, trades)
            url = webhooks[service]
            print(f"Sending {service} trades payload")
            for payload_chunk in chunker(trade_payload, 20): # workaround potential max length
                payload_chunk = '\n'.join(payload_chunk)
                if service == 'telegram':
                    telegram_write(url, payload_chunk)
                else:
                    webhook_write(url, payload_chunk)
                time.sleep(1) # workaround potential API throttling
    
        if tickers:
            price_payload = prepare_price_payload(service, price_data, price_updates_percentage)
            if price_payload and price_updates:
                price_payload_string = '\n'.join(price_payload)
                print(f"preparing {service} price alert payload")
                print(price_payload_string)
                url = webhooks[service]
                print(f"Sending {service} price alert payload")
                if service == 'telegram':
                    telegram_write(url, price_payload_string)
                else:
                    webhook_write(url, price_payload_string)
            else:
                print(f"{service}: no holdings changed by {price_updates_percentage}% in the last session.")

