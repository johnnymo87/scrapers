import os

import nodriver as uc


async def main():
    """
    A simple example demonstrating how to log in, then navigate to a page,
    type 'Windham' in a search input, pick the matching dropdown suggestion,
    and finally click 'Continue'.
    """

    # Fetch configuration from environment variables
    scraper_email = os.environ["SCRAPER_EMAIL"]
    scraper_password = os.environ["SCRAPER_PASSWORD"]
    login_url = os.environ["LOGIN_URL"]
    search_url = os.environ["SEARCH_URL"]
    chrome_data_dir = os.environ["CHROME_DATA_DIR"]

    # Start the "nodriver" browser in undetected Chrome mode
    browser = await uc.start(user_data_dir=chrome_data_dir)

    #
    # 1. Navigate to the login page and log in
    #
    tab = await browser.get(login_url)

    # Example: fill in user + password fields.
    # Adjust selectors/text to match the actual site.
    # If your site has:
    #   <input name="email" />
    #   <input name="password" />
    #   <button type="submit">Log In</button>
    #
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

    # Optional: wait for any post-login page transitions or captchas
    # e.g., to intervene if Incapsula challenges your login:
    await tab.sleep(5)

    #
    # 2. Navigate to the search page (once we believe we're logged in)
    #
    tab = await browser.get(search_url)

    # Again, optional wait if you suspect captchas / slow loads
    await tab.sleep(5)

    #
    # 3. Type "Windham" into a search field
    #
    search_input = await tab.select('input[placeholder="Search"]')
    if not search_input:
        print("Could not find the search input. Adjust the selector for your site.")
        await tab.sleep(3)
        browser.stop()
        return

    await search_input.send_keys("Windham")

    # 4. Pick the "Windham" suggestion
    suggestion = await tab.select(
        'ul > li:first-child [data-testid="resort-suggestion"]'
    )
    if suggestion:
        await suggestion.click()
    else:
        print("Could not find the dropdown suggestion. Adjust text or wait logic.")
        await tab.sleep(3)
        browser.stop()
        return

    #
    # 5. Click the "Continue" button
    #
    continue_button = await tab.find("Continue", best_match=True)
    if continue_button:
        await continue_button.click()
    else:
        print("Could not find the 'Continue' button. Adjust text or selectors.")
        await tab.sleep(3)
        browser.stop()
        return

    # At this point, you're presumably on the 'Windham' page or can gather info.
    # Insert any "final scraping" logic here.

    print("Done. Sleeping for demonstration...")
    await tab.sleep(5)

    # Shutdown
    browser.stop()


if __name__ == "__main__":
    # nodriver uses its own event loop; typical usage:
    uc.loop().run_until_complete(main())
