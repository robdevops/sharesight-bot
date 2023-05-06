import json
import sys
import datetime
import requests
from lib.config import *
import lib.util as util

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = "Bearer " + self.token
        return r

def get_token():
    now = int(datetime.datetime.now().timestamp())
    cache_file = config_cache_dir + "/finbot_sharesight_token.json"
    cache = util.read_cache(cache_file, 1740)
    url = "https://api.sharesight.com/oauth2/token"
    if config_cache and cache:
        cache_expiry = cache['created_at'] + cache['expires_in']
        if cache_expiry < now + 60:
            print("token cache has expired")
        else:
            return cache['access_token']
    print("Fetching Sharesight auth token")
    try:
        r = requests.post(url, data=sharesight_auth, timeout=config_http_timeout)
    except Exception as e:
        print("Error", str(e), url, file=sys.stderr)
        sys.exit(1)
    if r.status_code != 200:
        print(r.status_code, "error", url, file=sys.stderr)
    data = r.json()
    if 'error' in data:
        print("Sharesight error:", data['error_code'], data['error'], file=sys.stderr)
        sys.exit(1)
    if 'access_token' in data:
        util.write_cache(cache_file, data)
    print(data)
    return data['access_token']

def get_portfolios():
    cache_file = config_cache_dir + "/finbot_sharesight_portfolios.json"
    cache = util.read_cache(cache_file, config_cache_seconds)
    portfolio_dict = {}
    if config_cache and cache:
        data = cache
    else:
        token = get_token()
        print("Fetching Sharesight portfolios")
        url = "https://api.sharesight.com/api/v3/portfolios"
        try:
            r = requests.get(url, headers={'Content-type': 'application/json'}, auth=BearerAuth(token), timeout=config_http_timeout)
        except Exception as e:
            print("Error", str(e), url, file=sys.stderr)
            sys.exit(1)
        if r.status_code != 200:
            print(r.status_code, "error", url, file=sys.stderr)
        data = r.json()
        if 'error' in data:
            print("Sharesight error:", data['error_code'], data['error'], file=sys.stderr)
            sys.exit(1)
        if 'portfolios' in data:
            util.write_cache(cache_file, data)
    for portfolio in data['portfolios']:
        if str(portfolio['id']) in config_exclude_portfolios:
            print(portfolio['id'], "(" + portfolio['name'] + ") in exclusion list. Skipping.")
        elif str(portfolio['id']) not in config_include_portfolios and config_include_portfolios:
            print("Exclusion list is defined and does not contain", portfolio['id'], "(" + portfolio['name'] + "). Skipping.")
        else:
            portfolio_dict[portfolio['name']] = portfolio['id']
    if not len(portfolio_dict):
        print("No portfolios found. Exiting.", file=sys.stderr)
        sys.exit(1)
    print(portfolio_dict)
    return portfolio_dict

def get_trades(portfolio_name, portfolio_id, days=config_past_days):
    cache_file = config_cache_dir + "/finbot_sharesight_trades_" + str(portfolio_id) + "_" + str(days) + ".json"
    cache = util.read_cache(cache_file, 299) # max freq 5 min
    if config_cache and cache:
        return cache['trades']
    start_date = datetime.datetime.now() - datetime.timedelta(days=days)
    start_date = start_date.strftime('%Y-%m-%d') # 2022-08-20
    token = get_token()
    print("Fetching Sharesight trades for", portfolio_name, end=": ")
    url = 'https://api.sharesight.com/api/v2/portfolios/'
    url = url + str(portfolio_id) + '/trades.json' + '?start_date=' + start_date
    try:
        r = requests.get(url, auth=BearerAuth(token), timeout=config_http_timeout)
    except Exception as e:
        print("Error", str(e), url, file=sys.stderr)
        sys.exit(1)
    if r.status_code != 200:
        print(r.status_code, "error", url, file=sys.stderr)
    data = r.json()
    print(len(data['trades']))
    if 'error' in data:
        print("Sharesight error:", data['error_code'], data['error'], file=sys.stderr)
        sys.exit(1)
    for trade in data['trades']:
        trade['portfolio'] = portfolio_name # inject custom field
    if config_cache and 'trades' in data:
        util.write_cache(cache_file, data)
    return data['trades']

def get_holdings(portfolio_name, portfolio_id):
    print("Fetching Sharesight holdings", portfolio_name, end=": ")
    data = get_performance(portfolio_id, 0)
    print(len(data['report']['holdings']))
    holdings = {}
    for item in data['report']['holdings']:
        code = item['instrument']['code']
        holdings[code] = item['instrument']
    tickers = set()
    for holding in holdings:
        symbol = holdings[holding]['code']
        market = holdings[holding]['market_code']
        ticker = util.transform_to_yahoo(symbol, market)
        tickers.add(ticker)
    tickers = list(tickers)
    tickers.sort()
    return tickers

def get_holdings_wrapper():
    tickers = set()
    portfolios = get_portfolios()
    if not portfolios:
        return False
    for portfolio_name, portfolio_id in portfolios.items():
        tickers.update(get_holdings(portfolio_name, portfolio_id))
    return tickers

def get_performance(portfolio_id, days):
    start_date = datetime.datetime.now() - datetime.timedelta(days=days)
    start_date = start_date.strftime('%Y-%m-%d') # 2023-04-25
    cache_file = config_cache_dir + "/finbot_sharesight_performance_" + str(portfolio_id) + "_" + str(days) + '.json'
    cache = util.read_cache(cache_file, config_cache_seconds)
    if config_cache and cache:
        data = cache
    else:
        token = get_token()
        endpoint = 'https://api.sharesight.com/api/v3/portfolios/'
        url = endpoint + str(portfolio_id) + '/performance?grouping=ungrouped&start_date=' + start_date
        try:
            r = requests.get(url, auth=BearerAuth(token), timeout=config_http_timeout)
        except Exception as e:
            print("Error", str(e), url, file=sys.stderr)
            sys.exit(1)
        if r.status_code != 200:
            print(r.status_code, "error", url, file=sys.stderr)
        data = r.json()
        if 'error' in data:
            print("Sharesight error:", data['error_code'], data['error'], file=sys.stderr)
            sys.exit(1)
        if 'report' in data:
            util.write_cache(cache_file, data)
    return data

def get_performance_wrapper(days=config_past_days):
    performance = {}
    portfolios = get_portfolios()
    for portfolio_name, portfolio_id in portfolios.items():
        performance[portfolio_id] = get_performance(portfolio_id, days)
        if not performance[portfolio_id]:
            print("Could not get performance for portfolio:", portfolio_id, file=sys.stderr)
            sys.exit(1)
    return performance
