import argparse
import json
import time

import apprise
import requests


def get_balance(address: str) -> float:
    url = f"https://blockstream.info/api/address/{address}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    satoshi_balance = (
        data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]
    )
    return satoshi_balance / 100_000_000.0


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        return None


def setup_apprise(apprise_urls: list) -> apprise.Apprise:
    """Set up Apprise notification system."""
    apobj = apprise.Apprise()
    if not apprise_urls:
        print(
            "Warning: No Apprise notification URLs configured. Notifications will not be sent.",
        )
        return apobj

    for url in apprise_urls:
        try:
            apobj.add(url)
        except Exception as e:
            print(f"Error adding Apprise URL '{url}': {e}")
            print(
                "Please check the URL format and ensure all necessary dependencies for the notification service are installed.",
            )

    return apobj


def send_test_notification(apobj: apprise.Apprise) -> None:
    """Send a test notification."""
    if apobj.urls:
        print("Sending test notification...")
        if apobj.notify(
            body="This is a test notification from your Bitcoin address monitor.",
            title="Bitcoin Monitor Test Notification",
        ):
            print("Test notification sent successfully.")
        else:
            print(
                "Failed to send test notification. Check your Apprise URLs and network connectivity.",
            )
    else:
        print("No Apprise URLs configured. Cannot send test notification.")


def validate_config(addresses_config: list) -> bool:
    """Validate that addresses are configured."""
    if not addresses_config:
        print(
            "No addresses found in the configuration file. Please add at least one address.",
        )
        return False
    return True


def initialize_balances(addresses_config: list) -> dict:
    """Initialize the balance tracking dictionary."""
    return {item["address"]: None for item in addresses_config}


def monitor_address(item: dict, last_balances: dict, apobj: apprise.Apprise) -> None:
    """Monitor a single address for balance changes."""
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
                    title="Bitcoin Funds Received!",
                )
        elif balance < last_balances[address]:
            message = (
                f"⚠️ Balance decreased for {title} ({address})! Now {balance:.8f} BTC"
            )
            print(message)
            if apobj.urls:
                apobj.notify(
                    body=message,
                    title="Bitcoin Balance Decreased!",
                )
        last_balances[address] = balance
    except Exception as e:
        print(f"Error monitoring {title} - {address}: {e}")
        if apobj.urls:
            apobj.notify(
                body=f"Error monitoring {title} ({address}): {e}",
                title="Bitcoin Monitor Error",
            )


def monitor_addresses(
    addresses_config: list,
    last_balances: dict,
    apobj: apprise.Apprise,
) -> None:
    """Monitor all configured addresses."""
    for item in addresses_config:
        monitor_address(item, last_balances, apobj)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor Bitcoin addresses for incoming funds.",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the configuration file (default: config.json)",
    )
    parser.add_argument(
        "--test-notifications",
        action="store_true",
        help="Send a test notification using the configured Apprise URLs.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    config = load_config(args.config)
    if config is None:
        return

    addresses_config = config.get("addresses", [])
    interval = config.get("interval", 60)
    apprise_urls = config.get("apprise_urls", [])

    apobj = setup_apprise(apprise_urls)

    if args.test_notifications:
        send_test_notification(apobj)
        return

    if not validate_config(addresses_config):
        return

    last_balances = initialize_balances(addresses_config)

    while True:
        monitor_addresses(addresses_config, last_balances, apobj)
        time.sleep(interval)


if __name__ == "__main__":
    main()
