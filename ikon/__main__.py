import json
import logging
import os

import nodriver as uc  # type: ignore[import-untyped]
from sinch import SinchClient  # type: ignore[import-untyped]
from sinch.core.exceptions import SinchException  # type: ignore[import-untyped]

# Configure logging at the module level
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def send_sinch_sms(
    sinch_client: SinchClient,
    from_number: str,
    to_numbers: list[str],
    body: str,
) -> None:
    """
    Sends an SMS message using the official Sinch Python SDK.
    """
    try:
        response = sinch_client.sms.batches.send(
            body=body,
            to=to_numbers,
            from_=from_number,
            delivery_report="none",
        )
        logger.info(
            "Sent SMS to %s: %s. Batch ID: %s",
            ", ".join(to_numbers),
            body,
            response.id,
        )
    except SinchException as exc:
        logger.warning("Failed to send to %s. Error: %s", ", ".join(to_numbers), exc)


async def main() -> None:
    """
    A scraper for "Windham" data on the Ikon ski pass website.

    Environment variables used:
      For the scraper:
      • CHROME_DATA_DIR     : e.g. "/path/to/some/chrome_profile_dir"

      For the Ikon site:
      • LOGIN_EMAIL         : e.g. "your_email@example.com"
      • LOGIN_PASSWORD      : e.g. "MyP@ssw0rd!"
      • LOGIN_URL           : e.g. "https://example.com/login"
      • FETCH_URL           : e.g.
          "https://account.ikonpass.com/api/v2/reservation-availability/88"
      • DESIRED_DATES       : Comma-separated list, e.g. "2025-03-01,2025-03-02"

      For Sinch alerts (via the official Sinch Python SDK):
      • SINCH_KEY_ID
      • SINCH_KEY_SECRET
      • SINCH_PROJECT_ID
      • SINCH_FROM_NUMBER
      • SINCH_TO_NUMBERS
    """

    # Fetch configuration from environment variables (Ikon + Chrome)
    chrome_data_dir = os.environ.get("CHROME_DATA_DIR")

    login_email = os.environ.get("LOGIN_EMAIL")
    login_password = os.environ.get("LOGIN_PASSWORD")
    login_url = os.environ.get("LOGIN_URL")
    fetch_url = os.environ.get("FETCH_URL")
    desired_dates_str = os.environ.get("DESIRED_DATES")

    # Fetch configuration from environment variables (Sinch)
    sinch_key_id = os.environ.get("SINCH_KEY_ID")
    sinch_key_secret = os.environ.get("SINCH_KEY_SECRET")
    sinch_project_id = os.environ.get("SINCH_PROJECT_ID")
    sinch_from_number = os.environ.get("SINCH_FROM_NUMBER")
    sinch_to_numbers_str = os.environ.get("SINCH_TO_NUMBERS")

    # Collect and check for missing or empty env vars
    required_env_vars = {
        "CHROME_DATA_DIR": chrome_data_dir,
        "LOGIN_EMAIL": login_email,
        "LOGIN_PASSWORD": login_password,
        "LOGIN_URL": login_url,
        "FETCH_URL": fetch_url,
        "DESIRED_DATES": desired_dates_str,
        "SINCH_KEY_ID": sinch_key_id,
        "SINCH_KEY_SECRET": sinch_key_secret,
        "SINCH_PROJECT_ID": sinch_project_id,
        "SINCH_FROM_NUMBER": sinch_from_number,
        "SINCH_TO_NUMBERS": sinch_to_numbers_str,
    }
    missing_env_vars = [k for k, v in required_env_vars.items() if not v]
    if missing_env_vars:
        logger.error(
            "The following environment variables are missing or empty: %s. Exiting.",
            ", ".join(missing_env_vars),
        )
        return

    # Make mypy happy by asserting that all required env vars are non-None.
    assert (
        chrome_data_dir
        and login_email
        and login_password
        and login_url
        and fetch_url
        and desired_dates_str
        and sinch_key_id
        and sinch_key_secret
        and sinch_project_id
        and sinch_from_number
        and sinch_to_numbers_str
    )

    # Parse desired dates
    DESIRED_DATES = [d.strip() for d in desired_dates_str.split(",") if d.strip()]
    if not DESIRED_DATES:
        logger.error("DESIRED_DATES environment variable is empty or invalid. Exiting.")
        return

    # Parse phone number list
    SINCH_TO_NUMBERS = [p.strip() for p in sinch_to_numbers_str.split(",") if p.strip()]
    if not SINCH_TO_NUMBERS:
        logger.error(
            "SINCH_TO_NUMBERS environment variable is empty or invalid. Exiting."
        )
        return

    # Create the Sinch client
    sinch_client = SinchClient(
        key_id=sinch_key_id,
        key_secret=sinch_key_secret,
        project_id=sinch_project_id,
    )

    # Start the "nodriver" browser in undetected Chrome mode
    browser = await uc.start(user_data_dir=chrome_data_dir)

    #
    # 1. Log in.
    #
    tab = await browser.get(login_url)

    # Optional wait in case the session auto-redirects, etc.
    await tab.sleep(3)

    # Check if "Make a Reservation" button is present to detect logged-in state
    reservation_btn = await tab.select(
        'a[data-testid="button"][href="/myaccount/reservations/add/"]'
    )

    if reservation_btn:
        logger.info("It appears we are already logged in. Skipping login steps.")
    else:
        # Proceed with login steps
        email_input = await tab.select('input[name="email"]')
        password_input = await tab.select('input[name="password"]')
        login_button = await tab.find("Log In", best_match=True)

        if not email_input or not password_input or not login_button:
            logger.error("Could not locate login fields. Adjust selectors as needed.")
            await tab.sleep(3)
            browser.stop()
            return

        # Fill in login credentials
        await email_input.send_keys(login_email)
        await password_input.send_keys(login_password)

        # Click the "Log In" button
        await login_button.click()

        # Optional: wait for post-login transitions or captchas
        await tab.sleep(5)

        # After logging in, try to find the "Make a Reservation" button again
        reservation_btn = await tab.select(
            'a[data-testid="button"][href="/myaccount/reservations/add/"]'
        )
        if not reservation_btn:
            logger.error("Failed to locate 'Make a Reservation' button after login.")
            await tab.sleep(3)
            browser.stop()
            return

    logger.info("Login successful (or already logged in). Beginning repeated checks...")

    while True:
        #
        # 2. Perform a raw fetch request via JavaScript to get Ikon availability data
        #
        result = await tab.evaluate(
            f"""
            fetch("{fetch_url}", {{
              method: "GET",
              credentials: "include"
            }})
            .then(r => r.text());
            """,
            await_promise=True,
        )

        #
        # 3. Parse the JSON and check for dates of interest
        #
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            logger.warning("Unable to parse JSON from API. Will retry in 5 minutes.")
            await tab.sleep(300)
            continue

        logger.debug("Received JSON data: %s", data)

        if "data" not in data:
            logger.warning("JSON has no top-level 'data' key. Will retry in 5 minutes.")
            await tab.sleep(300)
            continue

        # We'll collect availability information here
        availability_found: dict[str, list[str]] = {}

        for pass_info in data["data"]:
            pass_id = pass_info.get("id")
            # Only proceed if you can still make reservations for this pass
            if pass_info.get("reservations_available", 0) < 1:
                continue

            closed_dates = pass_info.get("closed_dates", [])
            blackout_dates = pass_info.get("blackout_dates", [])
            unavailable_dates = pass_info.get("unavailable_dates", [])

            for date_str in DESIRED_DATES:
                # Mark date "available" if not in closed / blackout / unavailable
                if (
                    date_str not in closed_dates
                    and date_str not in blackout_dates
                    and date_str not in unavailable_dates
                ):
                    availability_found.setdefault(pass_id, []).append(date_str)

        if availability_found:
            # Build a summary message for all found availability
            lines = ["Found availability for these pass IDs and dates:"]
            for pid, dates in availability_found.items():
                lines.append(f"  - Pass ID {pid}: {dates}")

            msg_text = "\n".join(lines)
            logger.info(msg_text)

            # Send an SMS to each recipient
            send_sinch_sms(
                sinch_client,
                sinch_from_number,
                SINCH_TO_NUMBERS,
                msg_text,
            )
        else:
            logger.info("No availability found for desired dates.")

        logger.info("Sleeping for 5 minutes before the next check...")
        await tab.sleep(300)

    # No browser.stop() here – we never exit the loop unless manually interrupted.


if __name__ == "__main__":
    # nodriver uses its own event loop; typical usage:
    uc.loop().run_until_complete(main())
