# Ikon

This module scrapes the [Ikon Pass](https://www.ikonpass.com/) website for resort availability information, specifically checking for open dates at certain resorts.

## Why NODRIVER?

We use [nodriver](https://pypi.org/project/nodriver/) because it provides an undetected Chrome automation environment, making it harder for anti-bot systems (e.g. reCAPTCHA, CloudFlare, Imperva, hCaptcha) to detect and block our scraper.

## Configuration

This module uses the following environment variables:

- **CHROME_DATA_DIR**: The path on your local machine to store Chrome user data, allowing nodriver to reuse browser profiles, making it appear more human-like.

We need credentials to log into the Ikon site, URLs to scrape, and dates to check for availability.

- **LOGIN_EMAIL**: The email address used to log into your Ikon account.
- **LOGIN_PASSWORD**: The password for your Ikon account.
- **LOGIN_URL**: The URL for logging into Ikon.
- **FETCH_URL**: The endpoint for retrieving availability data.
  - Figure this out by inspecting the network requests in your browser's developer tools. For instance, for Windham, the URL is `https://account.ikonpass.com/api/v2/reservation-availability/88`.
- **DESIRED_DATES**: A comma-separated list of dates (in `YYYY-MM-DD` format) to check for availability. For example:
  `DESIRED_DATES="2025-03-01,2025-03-02"`

We use Sinch to automate notifications to the "user" (you) when the scraper finds something of value. (I used to use Twilio, but I switched to Sinch. [Here's why](https://www.reddit.com/r/rails/comments/175e0fk/which_provider_for_sending_sms_messages_is_the/ly25agl/).)

For Sinch notifications:
- **SINCH_SERVICE_PLAN_ID**: Your Sinch account identifier.
- **SINCH_API_TOKEN**: Your Sinch account secret, used to authenticate API requests.
- **SINCH_PHONE_NUMBER**: The Sinch phone number from which SMS alerts will be sent.
- **USER_PHONE_NUMBERs**: A comma-separated list of phone numbers to which SMS alerts will be sent. For example:
  `USER_PHONE_NUMBERS="+15555555555,+16666666666"`

## Running the Scraper

Make sure your environment variables are set (e.g. in your `.envrc`), then run:

```bash
poetry run python -m ikon
```

This script logs into the Ikon site, checks resort availability at specified intervals, and sends an SMS alert via Sinch if your desired dates open up.

## Script Flow

1. **Login**: Launches undetected Chrome (via `nodriver`) and attempts to log in using `SCRAPER_EMAIL` and `SCRAPER_PASSWORD`.
2. **Availability Check**: Uses a JavaScript `fetch` call to query the Ikon API for availability of the dates listed in `DESIRED_DATES`.
3. **Notifications**: If any of the desired dates are available, sends an SMS message with details (via Sinch).

## Notes

- This script runs in an infinite loop by default, pausing 5 minutes between checks.
- To stop the script, press **Ctrl + C**.

---

Enjoy your newly discovered slope days!
