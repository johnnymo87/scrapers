import os

import nodriver as uc  # type: ignore[import-untyped]


async def main() -> None:
    """
    A scraper for "Windham" data on the Ikon ski pass website.

    Environment variables used:
      • SCRAPER_EMAIL       : e.g. "your_email@example.com"
      • SCRAPER_PASSWORD    : e.g. "MyP@ssw0rd!"
      • LOGIN_URL           : e.g. "https://example.com/login"
      • CHROME_DATA_DIR     : e.g. "/path/to/some/chrome_profile_dir"
    """

    # Fetch configuration from environment variables
    scraper_email = os.environ["SCRAPER_EMAIL"]
    scraper_password = os.environ["SCRAPER_PASSWORD"]
    login_url = os.environ["LOGIN_URL"]
    chrome_data_dir = os.environ["CHROME_DATA_DIR"]

    # Start the "nodriver" browser in undetected Chrome mode
    browser = await uc.start(user_data_dir=chrome_data_dir)

    #
    # 1. Navigate to the login page
    #
    tab = await browser.get(login_url)

    # Optional wait in case the session auto-redirects, etc.
    await tab.sleep(3)

    # Check if we see the "Make a Reservation" button.
    reservation_btn = await tab.select(
        'a[data-testid="button"][href="/myaccount/reservations/add/"]'
    )

    if reservation_btn:
        print("It appears we are already logged in. Skipping login steps.")
    else:
        # Proceed with the login steps since we appear not to be logged in
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

        # Optional: wait for post-login page transitions or captchas
        await tab.sleep(5)

        # After logging in, try to find the reservation button again
        reservation_btn = await tab.select(
            'a[data-testid="button"][href="/myaccount/reservations/add/"]'
        )
        if not reservation_btn:
            print("Failed to locate 'Make a Reservation' button after login.")
            await tab.sleep(3)
            browser.stop()
            return

    #
    # 2. Now that we're presumably on a page where we have a valid session,
    #    perform a raw fetch request via JavaScript.
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
    print(result)
    breakpoint()

    # At this point, you can parse or store the fetched response as needed.

    print("Done. Sleeping for demonstration...")
    # await tab.sleep(5)

    # Shutdown
    browser.stop()


if __name__ == "__main__":
    # nodriver uses its own event loop; typical usage:
    uc.loop().run_until_complete(main())
