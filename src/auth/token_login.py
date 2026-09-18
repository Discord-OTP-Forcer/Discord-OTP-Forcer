from pathlib import Path
from typing import Final

from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from src.lib.types import (
    BrowserSession,
    CheckLoginSuccess,
    TokenFound,
)

_TOKEN_LOGIN_JS: Final[str] = (Path(__file__).parent.parent / "lib/js_scripts" / "AuthTokenLogin.js").read_text(encoding="utf-8")


def login_with_discord_auth_token(
    session: BrowserSession,
    auth_token: TokenFound,
) -> bool:
    """Logs into Discord directly using an discord auth token."""
    driver: WebDriver = session.driver
    wait = WebDriverWait(driver, session.config.program.elementLoadTolerance * 3)

    driver.get("https://discord.com/login")
    logger.info("Injecting discord auth token into Discord session...")
    driver.execute_script(_TOKEN_LOGIN_JS, str(auth_token.token))

    try:
        wait.until(CheckLoginSuccess())
        logger.success("Logged in successfully with authToken.")
        return True
    except TimeoutException:
        logger.error("Failed to log in with authToken (timed out waiting for homepage).")
        return False
