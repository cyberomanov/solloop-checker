# Solloop checker

Checks public Solana addresses sequentially through the Solloop API. Requires Python 3.10 or newer. No private keys or wallet connection are needed.

## Clone the repository

```bash
git clone https://github.com/cyberomanov/solloop-checker.git
cd solloop-checker
```

## Input

Create and fill these files next to `main.py`:

- `address.txt`: one Solana address per line.
- `proxy.txt`: one proxy per line, matching the address on the same line number.

Supported proxy formats: `http://user:pass@host:port` and `socks5://user:pass@host:port`. URL-encode special characters in usernames and passwords (for example, `@` becomes `%40`).

Blank lines are not allowed, and both files must have the same number of lines. All inputs are validated before any requests are sent. Each attempt uses a fresh session with the same assigned proxy. SOCKS5 also routes DNS resolution through the proxy. There is no direct-connection fallback.

## Configuration

Edit `config.py` to set the API URL, input/output paths, random sleep ranges between accounts and retries (in seconds), retry count, and request timeout. Paths are relative to the script directory.

`RETRIES = 3` means one initial attempt plus three retries. Addresses are checked sequentially.

## Run with uv

Install `uv` on macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the terminal or load the updated shell environment, then run the checker:

```bash
uv run main.py
```

The script declares its dependencies inline, so `uv` installs them automatically in an isolated environment.

## Run with Python and pip

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Results

Results are saved to `results.csv` with the columns `id,address,allocation,score`. IDs are input line numbers starting at 1. Allocation and score are saved as returned by the API, without filtering on `unavailable` flags.

Each completed address is written immediately. After all attempts fail, allocation and score are left blank and the error is logged to the console. Actual zero values are saved as `0`.

Each run overwrites the previous CSV. Pressing Ctrl+C preserves rows already written. The exit code is 1 if any address fails and 130 after Ctrl+C.

Address files, proxies, CSV files, and logs are excluded from Git. If the website changes its server function, update `API_URL` in `config.py`.

## Donate

`0x81fb0dF0F16ABC3BE334aB619154C9b3736aB9c1` (EVM)

[@thecyberomanovsmoment](https://t.me/thecyberomanovsmoment)