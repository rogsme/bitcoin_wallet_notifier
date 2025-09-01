import argparse
import json
import logging
import time

import apprise
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BitcoinAddressMonitor:
    """Monitors Bitcoin addresses for balance changes and sends notifications."""

    def __init__(self, config_path: str):
        """Initialize the Bitcoin address monitor.

        Args:
            config_path (str): Path to the configuration file.
        """
        self.config_path = config_path
        self.config = self._load_config()
        if self.config is None:
            raise ValueError("Failed to load configuration")

        self.addresses_config = self.config.get("addresses", [])
        self.interval = self.config.get("interval", 60)
        self.notify_errors = self.config.get("notify_errors", False)
        self.apprise_urls = self.config.get("apprise_urls", [])
        self.apobj = self._setup_apprise()
        self.last_balances = self._initialize_balances()

        # Log configuration details
        logger.info(f"Config location: {self.config_path}")
        logger.info(f"Number of addresses to monitor: {len(self.addresses_config)}")
        logger.info(f"Monitoring interval: {self.interval} seconds")
        logger.info(f"Error notifications enabled: {self.notify_errors}")
        logger.info(f"Number of Apprise URLs configured: {len(self.apprise_urls)}")

    def _load_config(self) -> dict | None:
        """Load configuration from JSON file.

        Returns:
            dict | None: Configuration dictionary, or None if loading failed.
        """
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file '{self.config_path}' not found.")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file: {e}")
            return None

    def _setup_apprise(self) -> apprise.Apprise:
        """Set up Apprise notification system.

        Returns:
            apprise.Apprise: Configured Apprise object.
        """
        apobj = apprise.Apprise()
        if not self.apprise_urls:
            logger.warning(
                "No Apprise notification URLs configured. Notifications will not be "
                "sent.",
            )
            return apobj

        for url in self.apprise_urls:
            try:
                apobj.add(url)
            except Exception as e:
                logger.error(f"Error adding Apprise URL '{url}': {e}")
                logger.error(
                    "Please check the URL format and ensure all necessary "
                    "dependencies for the notification service are installed.",
                )

        return apobj

    def _send_notification(
        self,
        body: str,
        title: str,
        address: str | None = None,
    ) -> None:
        """Sends a notification if Apprise URLs are configured.

        Args:
            body (str): The body of the notification message.
            title (str): The title of the notification.
            address (str, None): The Bitcoin address related to the notification.
                                 If provided, a link to a blockchain explorer will
                                 be appended to the body.
        """
        full_body = body
        if address:
            explorer_url = f"https://blockstream.info/address/{address}"
            full_body += f"\n\nView on explorer: {explorer_url}"

        if self.apobj.urls() and not self.apobj.notify(body=full_body, title=title):
            logger.error(f"Failed to send notification: '{title}' - '{body}'")

    def _initialize_balances(self) -> dict:
        """Initialize the balance tracking dictionary.

        Returns:
            dict: Dictionary with addresses as keys and None as values.
        """
        return {item["address"]: None for item in self.addresses_config}

    def get_balance(self, address: str) -> float:
        """Get the balance of a Bitcoin address in BTC.

        Args:
            address (str): The Bitcoin address to check.

        Returns:
            float: The balance in BTC.

        Raises:
            requests.RequestException: If there's an error fetching the balance.
            KeyError: If the response data structure is unexpected.
        """
        url = f"https://blockstream.info/api/address/{address}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        satoshi_balance = (
            data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]
        )
        return satoshi_balance / 100_000_000.0

    def send_test_notification(self) -> None:
        """Send a test notification."""
        if self.apobj.urls():  # Call urls() to get the list of URLs
            logger.info("Sending test notification...")
            if self.apobj.notify(
                body="This is a test notification from your Bitcoin address monitor.",
                title="Bitcoin Monitor Test Notification",
            ):
                logger.info("Test notification sent successfully.")
            else:
                logger.error(
                    "Failed to send test notification. Check your Apprise URLs "
                    "and network connectivity.",
                )
        else:
            logger.warning("No Apprise URLs configured. Cannot send test notification.")

    def validate_config(self) -> bool:
        """Validate that addresses are configured.

        Returns:
            bool: True if valid, False otherwise.
        """
        if not self.addresses_config:
            logger.error(
                "No addresses found in the configuration file. "
                "Please add at least one address.",
            )
            return False
        return True

    def monitor_address(self, item: dict) -> None:
        """Monitor a single address for balance changes.

        Args:
            item (dict): Address configuration item containing at least 'address' key.
        """
        address = item["address"]
        title = item.get("title", address)

        try:
            balance = self.get_balance(address)
            if self.last_balances[address] is None:
                logger.info(
                    f"[{title} - {address}] Starting balance: {balance:.8f} BTC",
                )
            elif balance > self.last_balances[address]:
                message = (
                    f"🎉 New funds received for {title} ({address})! "
                    f"Balance increased to {balance:.8f} BTC"
                )
                logger.info(message)
                self._send_notification(
                    message,
                    "Bitcoin Funds Received!",
                    address=address,
                )
            elif balance < self.last_balances[address]:
                message = (
                    f"⚠️ Balance decreased for {title} ({address})! Now "
                    f"{balance:.8f} BTC"
                )
                logger.warning(message)
                self._send_notification(
                    message,
                    "Bitcoin Balance Decreased!",
                    address=address,
                )
            self.last_balances[address] = balance
        except Exception as e:
            error_message = f"Error monitoring {title} ({address}): {e}"
            logger.error(error_message)
            if self.notify_errors:
                self._send_notification(
                    error_message,
                    "Bitcoin Monitor Error",
                    address=address,
                )

    def monitor_addresses(self) -> None:
        """Monitor all configured addresses."""
        for item in self.addresses_config:
            self.monitor_address(item)

    def run(self) -> None:
        """Run the main monitoring loop."""
        if not self.validate_config():
            return

        while True:
            self.monitor_addresses()
            time.sleep(self.interval)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
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


def main() -> None:
    """Main function to run the Bitcoin address monitor."""
    args = parse_arguments()

    try:
        monitor = BitcoinAddressMonitor(args.config)
    except ValueError:
        return

    if args.test_notifications:
        monitor.send_test_notification()
        return

    monitor.run()


if __name__ == "__main__":
    main()
