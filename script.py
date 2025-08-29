import requests
import time
import argparse
import json # Add this import

def get_balance(address: str) -> float:
    url = f"https://blockstream.info/api/address/{address}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    satoshi_balance = data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]
    return satoshi_balance / 100_000_000.0

def main():
    parser = argparse.ArgumentParser(description="Monitor Bitcoin addresses for incoming funds.")
    parser.add_argument("--config", default="config.json", help="Path to the configuration file (default: config.json)")
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{args.config}' not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        return

    addresses_config = config.get("addresses", [])
    interval = config.get("interval", 60)

    if not addresses_config:
        print("No addresses found in the configuration file. Please add at least one address.")
        return

    last_balances = {item["address"]: None for item in addresses_config}

    while True:
        for item in addresses_config:
            address = item["address"]
            title = item.get("title", address)
            try:
                balance = get_balance(address)
                if last_balances[address] is None:
                    print(f"[{title} - {address}] Starting balance: {balance:.8f} BTC")
                elif balance > last_balances[address]:
                    print(f"🎉 [{title} - {address}] New funds received! Balance increased to {balance:.8f} BTC")
                elif balance < last_balances[address]:
                    print(f"⚠️ [{title} - {address}] Balance decreased! Now {balance:.8f} BTC")
                last_balances[address] = balance
            except Exception as e:
                print(f"Error monitoring {title} - {address}: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    main()

