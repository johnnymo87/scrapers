import json
import os

import nodriver as uc  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]


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

      For Twilio alerts:
      • TWILIO_ACCOUNT_SID
      • TWILIO_AUTH_TOKEN
      • TWILIO_PHONE_NUMBER
      • USER_PHONE_NUMBERS  : Comma-separated list, e.g. "+15551234567,+15557654321"
    """

    # Fetch configuration from environment variables

    # Scraper-specific env vars
    chrome_data_dir = os.environ["CHROME_DATA_DIR"]

    # Ikon-specific env vars
    login_email = os.environ["LOGIN_EMAIL"]
    login_password = os.environ["LOGIN_PASSWORD"]
    login_url = os.environ["LOGIN_URL"]
    fetch_url = os.environ.get("FETCH_URL")
    desired_dates_str = os.environ.get("DESIRED_DATES")

    # Twilio / SMS-related env vars
    twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
    user_phone_numbers = os.environ.get("USER_PHONE_NUMBER")
    # If any of these are missing, exit immediately
    if not all(
        [
            chrome_data_dir,
            login_email,
            login_password,
            login_url,
            fetch_url,
            desired_dates_str,
            twilio_account_sid,
            twilio_auth_token,
            twilio_phone_number,
            user_phone_numbers,
        ]
    ):
        print("One or more environment variables are missing. Exiting.")
        return

    assert desired_dates_str is not None
    DESIRED_DATES = [d.strip() for d in desired_dates_str.split(",") if d.strip()]
    if not DESIRED_DATES:
        print("DESIRED_DATES environment variable is empty or invalid. Exiting.")
        return

    assert user_phone_numbers is not None
    USER_PHONE_NUMBERS = [p.strip() for p in user_phone_numbers.split(",") if p.strip()]
    if not USER_PHONE_NUMBERS:
        print("USER_PHONE_NUMBERS environment variable is empty or invalid. Exiting.")
        return

    # Create the Twilio client
    client = Client(twilio_account_sid, twilio_auth_token)

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
            print("Failed to locate 'Make a Reservation' button after login.")
            await tab.sleep(3)
            browser.stop()
            return

    print("Login successful (or already logged in). Beginning repeated checks...")

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
            print("Unable to parse JSON from API. Will retry in 5 minutes.")
            await tab.sleep(300)
            continue

        if "data" not in data:
            print("JSON has no top-level 'data' key. Will retry in 5 minutes.")
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
            print(msg_text)

            for user_phone_number in USER_PHONE_NUMBERS:
                # Send via Twilio
                client.messages.create(
                    from_=twilio_phone_number,
                    to=user_phone_number,
                    body=msg_text,
                )
        else:
            print("No availability found for desired dates.")

        print("Sleeping for 5 minutes before the next check...")
        await tab.sleep(300)

    # No browser.stop() here – we never exit the loop unless manually interrupted.


if __name__ == "__main__":
    # nodriver uses its own event loop; typical usage:
    uc.loop().run_until_complete(main())
