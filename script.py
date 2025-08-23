import requests
import time
import argparse

def get_balance(address: str) -> int:
    url = f"https://blockstream.info/api/address/{address}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]

def main():
    parser = argparse.ArgumentParser(description="Monitor a Bitcoin address for incoming funds.")
    parser.add_argument("--address", required=True, help="Bitcoin address to monitor")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default: 60)")
    args = parser.parse_args()

    last_balance = None

    while True:
        try:
            balance = get_balance(args.address)
            if last_balance is None:
                print(f"[{args.address}] Starting balance: {balance} sats")
            elif balance > last_balance:
                print(f"🎉 [{args.address}] New funds received! Balance increased to {balance} sats")
            elif balance < last_balance:
                print(f"⚠️ [{args.address}] Balance decreased! Now {balance} sats")
            last_balance = balance
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(args.interval)

if __name__ == "__main__":
    main()

