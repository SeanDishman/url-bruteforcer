import json
import os
import sys
import re
import requests
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

CONFIG_FILE = "config.json"
ENDPOINTS_FILE = "attempt_endpoints.txt"

DEFAULT_CONFIG = {
    "log_responces": True,
    "log_dataresponces": False,
    "threads": 10,
    "proxys": False,
    "proxyinfo": "exampleusername:examplepassword@rotatingexample.com"
}

results_so_far = []
base_url_global = ""
config_global = {}


def create_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
    print(f"[+] '{CONFIG_FILE}' has been created with default settings.")
    print("[!] Please configure it to your liking, then restart the program for changes to load.")
    sys.exit(0)


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def normalize_domain(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r'^https?://', '', raw)
    raw = raw.rstrip('/')
    return f"https://{raw}"


def build_url(base: str, endpoint: str) -> str:
    base = base.rstrip('/')
    endpoint = endpoint.strip().lstrip('/')
    return f"{base}/{endpoint}"


def load_endpoints() -> list:
    if not os.path.exists(ENDPOINTS_FILE):
        print(f"[!] '{ENDPOINTS_FILE}' not found. Please create it with one endpoint per line.")
        sys.exit(1)

    with open(ENDPOINTS_FILE, "r") as f:
        endpoints = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    if not endpoints:
        print(f"[!] '{ENDPOINTS_FILE}' is empty. Add endpoints (one per line) and restart.")
        sys.exit(1)

    return endpoints


def build_proxy(config: dict):
    if not config.get("proxys"):
        return None
    info = config.get("proxyinfo", "")
    proxy_url = f"http://{info}"
    return {"http": proxy_url, "https": proxy_url}


def test_proxy(config: dict):
    proxies = build_proxy(config)
    if proxies is None:
        print(f"[~] Proxys: disabled")
        return

    print(f"[~] Proxys: enabled — testing rotation...")
    ips_seen = []

    for i in range(1, 4):
        try:
            resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
            ip = resp.json().get("ip", "unknown")
            ips_seen.append(ip)
            print(f"  Request {i}: {ip}")
        except Exception as e:
            print(f"  Request {i}: FAILED — {e}")

    unique = set(ips_seen)
    if len(unique) > 1:
        print(f"[+] Proxy rotation confirmed — {len(unique)} different IPs seen\n")
    elif len(unique) == 1:
        print(f"[!] Proxy connected but same IP all 3 times — may not be rotating yet\n")
    else:
        print(f"[!] Proxy test failed — check your proxyinfo in config\n")


def print_summary(results: list, total_urls: int):
    ok     = [r for r in results if r["status"] == 200]
    live   = [r for r in results if r["status"] and r["status"] != 404 and not r["error"]]
    errors = [r for r in results if r["error"]]

    print(f"\n{'='*55}")
    print(f"  SCAN SUMMARY")
    print(f"{'='*55}")
    print(f"  Checked  : {len(results)} / {total_urls} endpoints")
    print(f"  200 OK   : {len(ok)}")
    print(f"  Live     : {len(live)}  (non-404, no error)")
    print(f"  Errors   : {len(errors)}")
    print(f"  Skipped  : {total_urls - len(results)}")
    print(f"{'='*55}")

    if ok:
        print(f"\n  [200 hits]")
        for r in ok:
            print(f"    {r['url']}")


def save_log(results: list, base_url: str):
    if not results:
        return
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    site = re.sub(r'^https?://', '', base_url).rstrip('/').replace('/', '_')
    log_path = os.path.join("logs", f"responcecodes({site})({timestamp}).txt")

    def sort_key(r):
        return r["status"] if r["status"] is not None else 999

    sorted_results = sorted(results, key=sort_key)

    with open(log_path, "w") as f:
        for r in sorted_results:
            if r["error"]:
                f.write(f"ERR-{r['url']}\n")
            else:
                f.write(f"{r['status']}-{r['url']}\n")

    print(f"[+] Log saved → '{log_path}'")


def save_data_log(results: list, base_url: str):
    if not results:
        return
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    site = re.sub(r'^https?://', '', base_url).rstrip('/').replace('/', '_')
    log_path = os.path.join("logs", f"dataresponces({site})({timestamp}).txt")

    hits = [r for r in results if r["status"] == 200 and r["body"] is not None]

    if not hits:
        print(f"[!] No 200 responses with data to log.")
        return

    with open(log_path, "w", encoding="utf-8") as f:
        for i, r in enumerate(hits):
            f.write(f"200:{r['url']}\n")
            f.write(r["body"])
            if i < len(hits) - 1:
                f.write("\n\n\n\n\n")

    print(f"[+] Data log saved → '{log_path}'")


def flush_and_exit(total_urls: int = 0):
    print(f"\n\n[!] Interrupted — saving progress...")
    print_summary(results_so_far, total_urls)
    if config_global.get("log_responces"):
        save_log(results_so_far, base_url_global)
    if config_global.get("log_dataresponces"):
        save_data_log(results_so_far, base_url_global)
    print(f"\n[!] Exited cleanly.")
    sys.exit(0)


def check_endpoint(url: str, proxies, config: dict) -> dict:
    result = {"url": url, "status": None, "error": None, "body": None}
    try:
        resp = requests.get(url, proxies=proxies, timeout=10, allow_redirects=True)
        result["status"] = resp.status_code
        if config.get("log_dataresponces") and resp.status_code == 200:
            result["body"] = resp.text
    except requests.RequestException as e:
        result["error"] = str(e)
    return result


def print_result(result: dict, config: dict):
    url = result["url"]
    if result["error"]:
        print(f"  [ERR] {url}  =>  {result['error']}")
        return

    status = result["status"]
    if status == 200:
        tag = "[200 OK      ]"
    elif status in (301, 302, 303, 307, 308):
        tag = f"[{status} REDIRECT]"
    elif status == 403:
        tag = "[403 FORBIDDEN]"
    elif status == 404:
        tag = "[404 NOT FOUND]"
    elif status == 401:
        tag = "[401 UNAUTH   ]"
    elif status == 500:
        tag = "[500 SVR ERR  ]"
    else:
        tag = f"[{status}        ]"

    if config.get("log_responces"):
        print(f"  {tag}  {url}")


def scan(base_url: str, endpoints: list, config: dict):
    global results_so_far

    proxies = build_proxy(config)
    threads = config.get("threads", 10)
    urls = [build_url(base_url, ep) for ep in endpoints]
    total_urls = len(urls)

    print(f"\n[~] Scanning {total_urls} endpoint(s) on {base_url} with {threads} thread(s)...")
    print(f"[!] Press Ctrl+C at any time to stop and save progress.\n")

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(check_endpoint, url, proxies, config): url for url in urls}
            for future in as_completed(futures):
                result = future.result()
                results_so_far.append(result)
                print_result(result, config)
    except KeyboardInterrupt:
        flush_and_exit(total_urls)

    print_summary(results_so_far, total_urls)

    if config.get("log_responces"):
        save_log(results_so_far, base_url)
    if config.get("log_dataresponces"):
        save_data_log(results_so_far, base_url)


def main():
    global base_url_global, config_global

    if not os.path.exists(CONFIG_FILE):
        create_config()

    config = load_config()
    config_global = config
    print(f"[+] Config loaded from '{CONFIG_FILE}'")
    print(f"[~] Threads: {config.get('threads', 10)}")

    test_proxy(config)

    endpoints = load_endpoints()
    print(f"[+] Loaded {len(endpoints)} endpoint(s) from '{ENDPOINTS_FILE}'")

    try:
        raw = input("\n[?] Enter target domain (e.g. google.com or https://google.com): ").strip()
    except KeyboardInterrupt:
        print(f"\n[!] Exited before scan started.")
        sys.exit(0)

    if not raw:
        print("[!] No domain entered. Exiting.")
        sys.exit(1)

    base_url = normalize_domain(raw)
    base_url_global = base_url
    print(f"[~] Normalized target: {base_url}")

    scan(base_url, endpoints, config)


if __name__ == "__main__":
    main()