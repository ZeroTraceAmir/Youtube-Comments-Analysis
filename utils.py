# package imports
import os
from datetime import datetime

# logs messages with timestamps
# -----------------------------------------------------------------------------
def log(message: str):
  # get current time
  current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
  # print message
  print(f"[{current_time}] {message}")

# reads the optional proxy from the environment
# set PROXY in .env (example: 127.0.0.1:7898) to route all traffic through it
# leave it empty to connect directly
# the socks5h scheme is assumed when it is not given
# (h = domain names are also resolved by the proxy)
# write it with an explicit scheme (example: http://127.0.0.1:7898) to override
# -----------------------------------------------------------------------------
def get_proxy_url() -> str:
  proxy = os.getenv("PROXY", "").strip()

  # no proxy configured
  if not proxy:
    return ""

  # default to the socks5h scheme when it is not given
  if "://" not in proxy:
    proxy = f"socks5h://{proxy}"

  return proxy

# builds the proxies dict for the requests library
# returns None so requests keeps its default behavior
# -----------------------------------------------------------------------------
def get_requests_proxies() -> dict | None:
  proxy = get_proxy_url()

  if not proxy:
    return None

  return {"http": proxy, "https": proxy}

