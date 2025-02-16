import json
import os

import nodriver as uc  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]


async def main() -> None:
    """
    A scraper for "Windham" data on the Ikon ski pass website.

    Environment variables used:
      • SCRAPER_EMAIL       : e.g. "your_email@example.com"
      • SCRAPER_PASSWORD    : e.g. "MyP@ssw0rd!"
      • LOGIN_URL           : e.g. "https://example.com/login"
      • CHROME_DATA_DIR     : e.g. "/path/to/some/chrome_profile_dir"

      For Twilio alerts:
      • TWILIO_ACCOUNT_SID
      • TWILIO_AUTH_TOKEN
      • TWILIO_PHONE_NUMBER
      • USER_PHONE_NUMBER
    """

    # Fetch configuration from environment variables
    scraper_email = os.environ["SCRAPER_EMAIL"]
    scraper_password = os.environ["SCRAPER_PASSWORD"]
    login_url = os.environ["LOGIN_URL"]
    chrome_data_dir = os.environ["CHROME_DATA_DIR"]

    # Twilio / SMS-related env vars
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
    user_phone_number = os.getenv("USER_PHONE_NUMBER")

    # Attempt to create a Twilio client (if all vars are present)
    client = None
    if (
        twilio_account_sid
        and twilio_auth_token
        and twilio_phone_number
        and user_phone_number
    ):
        client = Client(twilio_account_sid, twilio_auth_token)
    else:
        print(
            "One or more Twilio environment variables are missing. "
            "Will not attempt to send SMS messages."
        )

    # Start the "nodriver" browser in undetected Chrome mode
    browser = await uc.start(user_data_dir=chrome_data_dir)

    #
    # 1. Navigate to the login page
    #
    tab = await browser.get(login_url)

    # Optional wait in case the session auto-redirects, etc.
    await tab.sleep(3)

    # Check if "Make a Reservation" button is present to detect logged-in state
    reservation_btn = await tab.select(
        'a[data-testid="button"][href="/myaccount/reservations/add/"]'
    )

    if reservation_btn:
        print("It appears we are already logged in. Skipping login steps.")
    else:
        # Proceed with login steps
        email_input = await tab.select('input[name="email"]')
        password_input = await tab.select('input[name="password"]')
        login_button = await tab.find("Log In", best_match=True)

        if not email_input or not password_input or not login_button:
            print("Could not locate login fields. Adjust selectors as needed.")
            await tab.sleep(3)
            browser.stop()
            return

        # Fill in login credentials
        await email_input.send_keys(scraper_email)
        await password_input.send_keys(scraper_password)

        # Click the "Log In" button
        await login_button.click()

        # Optional: wait for post-login transitions or captchas
        await tab.sleep(5)

        # After logging in, try to find the "Make a Reservation" button again
        reservation_btn = await tab.select(
            'a[data-testid="button"][href="/myaccount/reservations/add/"]'
        )
        if not reservation_btn:
            print("Failed to locate 'Make a Reservation' button after login.")
            await tab.sleep(3)
            browser.stop()
            return

    #
    # 2. Perform a raw fetch request via JavaScript to get data
    #
    result = await tab.evaluate(
        """
    fetch("https://account.ikonpass.com/api/v2/reservation-availability/88", {
      method: "GET",
      credentials: "include"
    })
    .then(r => r.text());
    """,
        await_promise=True,
    )
    # print("Raw JSON result from reservation-availability API:\n", result)

    #
    # 3. Parse the JSON and check for dates of interest
    #
    DESIRED_DATES = ["2025-03-01"]

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        print("Unable to parse JSON from API. Exiting.")
        browser.stop()
        return

    # We'll collect availability information here
    availability_found: dict[str, list[str]] = {}
    if "data" not in data:
        print("JSON has no top-level 'data' key. Exiting.")
        browser.stop()
        return

    for pass_info in data["data"]:
        pass_id = pass_info.get("id")
        # Only proceed if you can still make reservations for this pass
        if pass_info.get("reservations_available", 0) < 1:
            continue

        closed_dates = pass_info.get("closed_dates", [])
        blackout_dates = pass_info.get("blackout_dates", [])
        unavailable_dates = pass_info.get("unavailable_dates", [])

        for date_str in DESIRED_DATES:
            # Simple check: date is "available" if not in closed/blackout/unavailable
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

        print(msg_text)
        # Attempt to send via Twilio if client is set up
        if client:
            client.messages.create(
                from_=twilio_phone_number, to=user_phone_number, body=msg_text
            )
    else:
        print("No availability found for desired dates.")

    print("Done. Sleeping for demonstration...")

    # Shutdown
    browser.stop()


if __name__ == "__main__":
    # nodriver uses its own event loop; typical usage:
    uc.loop().run_until_complete(main())
