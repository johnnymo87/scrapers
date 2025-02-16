import json
import logging
import os

import nodriver as uc  # type: ignore[import-untyped]
import requests

# Configure logging at the module level
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def send_sinch_sms(
    sinch_service_plan_id: str,
    sinch_api_token: str,
    sinch_phone_number: str,
    to_number: str,
    body: str,
) -> None:
    """
    Sends an SMS message using Sinch's REST API.
    """
    url = f"https://us.sms.api.sinch.com/xms/v1/{sinch_service_plan_id}/batches"
    payload = {
        "from": sinch_phone_number,
        "to": [to_number],
        "body": body,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {sinch_api_token}",
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 201:
        logger.warning("Failed to send to %s: %s", to_number, response.text)
    else:
        logger.info("Sent SMS to %s: %s", to_number, body)


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

      For Sinch alerts:
      • SINCH_SERVICE_PLAN_ID
      • SINCH_API_TOKEN
      • SINCH_PHONE_NUMBER
      • USER_PHONE_NUMBERS
    """

    # Fetch configuration from environment variables
    chrome_data_dir = os.environ.get("CHROME_DATA_DIR")

    login_email = os.environ.get("LOGIN_EMAIL")
    login_password = os.environ.get("LOGIN_PASSWORD")
    login_url = os.environ.get("LOGIN_URL")
    fetch_url = os.environ.get("FETCH_URL")
    desired_dates_str = os.environ.get("DESIRED_DATES")

    # Sinch / SMS-related env vars
    sinch_service_plan_id = os.environ.get("SINCH_SERVICE_PLAN_ID")
    sinch_api_token = os.environ.get("SINCH_API_TOKEN")
    sinch_phone_number = os.environ.get("SINCH_PHONE_NUMBER")
    user_phone_numbers = os.environ.get("USER_PHONE_NUMBERS")

    # Collect and check for missing or empty env vars
    required_env_vars = {
        "CHROME_DATA_DIR": chrome_data_dir,
        "LOGIN_EMAIL": login_email,
        "LOGIN_PASSWORD": login_password,
        "LOGIN_URL": login_url,
        "FETCH_URL": fetch_url,
        "DESIRED_DATES": desired_dates_str,
        "SINCH_SERVICE_PLAN_ID": sinch_service_plan_id,
        "SINCH_API_TOKEN": sinch_api_token,
        "SINCH_PHONE_NUMBER": sinch_phone_number,
        "USER_PHONE_NUMBERS": user_phone_numbers,
    }

    missing_env_vars = [k for k, v in required_env_vars.items() if not v]
    if missing_env_vars:
        logger.error(
            "The following environment variables are missing or empty: %s. Exiting.",
            ", ".join(missing_env_vars),
        )
        return

    assert (
        login_email
        and login_password
        and login_url
        and fetch_url
        and desired_dates_str
        and sinch_service_plan_id
        and sinch_api_token
        and sinch_phone_number
        and user_phone_numbers
    )

    DESIRED_DATES = [d.strip() for d in desired_dates_str.split(",") if d.strip()]
    if not DESIRED_DATES:
        logger.error("DESIRED_DATES environment variable is empty or invalid. Exiting.")
        return

    USER_PHONE_NUMBERS = [p.strip() for p in user_phone_numbers.split(",") if p.strip()]
    if not USER_PHONE_NUMBERS:
        logger.error(
            "USER_PHONE_NUMBERS environment variable is empty or invalid. Exiting."
        )
        return

    # For demonstration—send a quick test message to each user number
    # for user_phone_number in USER_PHONE_NUMBERS:
    #     send_sinch_sms(
    #         sinch_service_plan_id,
    #         sinch_api_token,
    #         sinch_phone_number,
    #         user_phone_number,
    #         "This is a test message from your Sinch account.",
    #     )
    # breakpoint()

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
        # 2. Perform a raw fetch request via JavaScript to get data
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
                # Simple check: date is "available" if not in closed / blackout
                # / unavailable.
                if (
                    date_str not in closed_dates
                    and date_str not in blackout_dates
                    and date_str not in unavailable_dates
                ):
                    availability_found.setdefault(pass_id, []).append(date_str)

        if availability_found:
            # Build a summary message for all found availability
            lines = ["Found availability for the following pass IDs and dates:"]
            for pid, dates in availability_found.items():
                lines.append(f"  - Pass ID {pid}: {dates}")

            msg_text = "\n".join(lines)
            logger.info(msg_text)

            for user_phone_number in USER_PHONE_NUMBERS:
                # Send via Sinch
                send_sinch_sms(
                    sinch_service_plan_id,
                    sinch_api_token,
                    sinch_phone_number,
                    user_phone_number,
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
