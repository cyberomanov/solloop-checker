# /// script
# requires-python = ">=3.10"
# dependencies = ["requests[socks]>=2.32.3,<3"]
# ///

import csv
import logging
import math
import random
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

import config

BASE = Path(__file__).resolve().parent
LOG = logging.getLogger('solloop')
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def payload(address):
    return {'t': {'t': 10, 'i': 0, 'p': {'k': ['data'], 'v': [
        {'t': 10, 'i': 1, 'p': {'k': ['address'], 'v': [
            {'t': 1, 's': address}]}, 'o': 0}]}, 'o': 0}, 'f': 127, 'm': []}


def properties(node):
    if not isinstance(node, dict) or node.get('t') not in (10, 11):
        raise ValueError('Expected a serialized API object')
    p = node['p']
    if len(p['k']) != len(p['v']):
        raise ValueError('Invalid API object')
    return dict(zip(p['k'], p['v']))


def parse_result(body, address):
    # Seroval: the response is either a root node or a t/f/m wrapper.
    root = body['t'] if isinstance(body, dict) and isinstance(body.get('t'), dict) else body
    fields = properties(root)
    error = fields.get('error')
    if error is not None and error != {'t': 2, 's': 1}:
        raise ValueError('API returned an error')
    result = properties(fields['result'])
    if result.get('wallet') != {'t': 1, 's': address}:
        raise ValueError('Response wallet does not match the requested address')
    values = []
    for name in ('allocation', 'score'):
        node = result[name]
        value = node.get('s')
        if node.get('t') != 0 or type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid field {name}')
        values.append(value)
    return tuple(values)


def load_accounts():
    addresses = (BASE / config.ADDRESS_FILE).read_text(encoding='utf-8-sig').splitlines()
    proxies = (BASE / config.PROXY_FILE).read_text(encoding='utf-8-sig').splitlines()
    if not addresses or len(addresses) != len(proxies):
        raise ValueError('Address and proxy files must be non-empty and have matching line counts')
    accounts = []
    for row, (address, proxy) in enumerate(zip(addresses, proxies), 1):
        address, proxy = address.strip(), proxy.strip()
        if not address or any(c not in ALPHABET for c in address):
            raise ValueError(f'Line {row}: invalid Solana address')
        number = 0
        for char in address:
            number = number * 58 + ALPHABET.index(char)
        size = (number.bit_length() + 7) // 8 + len(address) - len(address.lstrip('1'))
        if size != 32:
            raise ValueError(f'Line {row}: address must encode 32 bytes')
        try:
            parsed = urlsplit(proxy)
            valid = (parsed.scheme in ('http', 'socks5') and parsed.hostname and parsed.port
                     and parsed.username and parsed.password and not parsed.query
                     and not parsed.fragment and parsed.path in ('', '/'))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f'Line {row}: expected http://user:pass@host:port or socks5://user:pass@host:port')
        # Resolve DNS through the SOCKS proxy as well.
        if proxy.startswith('socks5://'):
            proxy = 'socks5h://' + proxy[len('socks5://'):]
        accounts.append((address, proxy))
    return accounts


def check_wallet(address, proxy):
    for attempt in range(config.RETRIES + 1):
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    config.API_URL, json=payload(address),
                    proxies={'http': proxy, 'https': proxy},
                    headers={'Accept': 'application/json', 'x-tsr-serverFn': 'true',
                             'Origin': 'https://check.solloop.fun',
                             'Referer': 'https://check.solloop.fun/'},
                    timeout=config.TIMEOUT, allow_redirects=False,
                )
                if response.status_code != 200:
                    raise ValueError(f'HTTP {response.status_code}')
                return parse_result(response.json(), address)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            # Do not log requests exception messages: they may contain proxy passwords.
            reason = type(exc).__name__ if isinstance(exc, requests.RequestException) else str(exc)
            LOG.warning('%s | attempt %s/%s: %s', address, attempt + 1, config.RETRIES + 1, reason)
            if attempt < config.RETRIES:
                time.sleep(random.uniform(*config.SLEEP_BETWEEN_RETRIES))
    return '', ''


def validate_config():
    if type(config.RETRIES) is not int or config.RETRIES < 0:
        raise ValueError('RETRIES must be an integer >= 0')
    for name in ('SLEEP_BETWEEN_ACCOUNTS', 'SLEEP_BETWEEN_RETRIES'):
        interval = getattr(config, name)
        if len(interval) != 2 or not all(type(x) in (int, float) and math.isfinite(x) for x in interval) or not 0 <= interval[0] <= interval[1]:
            raise ValueError(f'Invalid range {name}')
    if not math.isfinite(config.TIMEOUT) or config.TIMEOUT <= 0:
        raise ValueError('TIMEOUT must be > 0')
    output = (BASE / config.OUTPUT_FILE).resolve()
    if output in ((BASE / config.ADDRESS_FILE).resolve(), (BASE / config.PROXY_FILE).resolve()):
        raise ValueError('OUTPUT_FILE must not match either input file')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
    try:
        validate_config()
        accounts = load_accounts()
    except (OSError, ValueError, TypeError) as exc:
        LOG.error('%s', exc)
        return 1
    success = 0
    with (BASE / config.OUTPUT_FILE).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['id', 'address', 'allocation', 'score'])
        handle.flush()
        for row, (address, proxy) in enumerate(accounts, 1):
            allocation, score = check_wallet(address, proxy)
            writer.writerow([row, address, allocation, score])
            handle.flush()
            success += allocation != ''
            LOG.info('[%s/%s] %s | allocation=%s score=%s', row, len(accounts), address, allocation, score)
            if row < len(accounts):
                time.sleep(random.uniform(*config.SLEEP_BETWEEN_ACCOUNTS))
    LOG.info('Done: %s successful, %s failed. CSV: %s', success, len(accounts) - success, config.OUTPUT_FILE)
    return 0 if success == len(accounts) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOG.warning('Stopped. Completed addresses have been saved to CSV.')
        raise SystemExit(130)
