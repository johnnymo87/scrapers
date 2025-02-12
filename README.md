# Scrapers

This repository is a collection of scripts for scraping various websites.

## Overview

- **Ikon:** Scrapes the Ikon Pass website for resort availability information.

## Setup

For instructions on setting up your environment, installing Python (via pyenv), Poetry, and loading environment variables with direnv, please refer to the [Installation section](#installation) below.

### Installation

2. **Environment variables:**
   - Rename `.envrc.example` to `.envrc` and fill in your keys.
   - Allow direnv:
     ```bash
     direnv allow
     ```

3. **Python Setup:**
   - Use pyenv to install Python (see [pyenv installation](https://github.com/pyenv/pyenv#installation)).
   - The required Python version is specified in `.python-version`.

4. **Install Dependencies:**
   - Install Poetry if you haven't already:
     ```bash
     curl -sSL https://install.python-poetry.org | python3 -
     ```
   - Then install project dependencies:
     ```bash
     poetry install --with dev
     ```

5. **Pre-commit Hooks:**
   - Install pre-commit hooks:
     ```bash
     pre-commit install
     ```

6. **Running the linter:**
   - Run the linter with:
     ```bash
     pre-commit run --all-files
     ```

7. **Running Tests:**
   - Execute the test suite using pytest:
     ```bash
     poetry run pytest
     ```

## Development and CI

- **Local Testing:** Run tests with `poetry run pytest`.
- **CI Pipeline:** On each push and pull request, the GitHub Actions workflow runs tests, style checks, and code coverage reports. See `.github/workflows/ci.yaml` for details.

For more module-specific details (e.g. using the email processor or TTS tools), please see the README files in the respective subdirectories.

---

Happy coding!
