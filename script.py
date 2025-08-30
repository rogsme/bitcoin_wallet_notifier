import requests
import time
import argparse
import json
import apprise

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
    parser.add_argument("--test-notifications", action="store_true", help="Send a test notification using the configured Apprise URLs.")
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
    apprise_urls = config.get("apprise_urls", [])

    apobj = apprise.Apprise()
    if apprise_urls:
        for url in apprise_urls:
            try:
                apobj.add(url)
            except Exception as e:
                print(f"Error adding Apprise URL '{url}': {e}")
                print("Please check the URL format and ensure all necessary dependencies for the notification service are installed.")
    else:
        print("Warning: No Apprise notification URLs configured. Notifications will not be sent.")

    if args.test_notifications:
        if apobj.urls:
            print("Sending test notification...")
            if apobj.notify(
                body='This is a test notification from your Bitcoin address monitor.',
                title='Bitcoin Monitor Test Notification'
            ):
                print("Test notification sent successfully.")
            else:
                print("Failed to send test notification. Check your Apprise URLs and network connectivity.")
        else:
            print("No Apprise URLs configured. Cannot send test notification.")
        return

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
                    message = f"🎉 New funds received for {title} ({address})! Balance increased to {balance:.8f} BTC"
                    print(message)
                    if apobj.urls:
                        apobj.notify(
                            body=message,
                            title='Bitcoin Funds Received!'
                        )
                elif balance < last_balances[address]:
                    message = f"⚠️ Balance decreased for {title} ({address})! Now {balance:.8f} BTC"
                    print(message)
                    if apobj.urls:
                        apobj.notify(
                            body=message,
                            title='Bitcoin Balance Decreased!'
                        )
                last_balances[address] = balance
            except Exception as e:
                print(f"Error monitoring {title} - {address}: {e}")
                if apobj.urls:
                    apobj.notify(
                        body=f"Error monitoring {title} ({address}): {e}",
                        title='Bitcoin Monitor Error'
                    )

        time.sleep(interval)

if __name__ == "__main__":
    main()
