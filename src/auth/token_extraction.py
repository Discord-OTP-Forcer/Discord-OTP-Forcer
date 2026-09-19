import time

from loguru import logger
from selenium.webdriver.remote.webdriver import WebDriver

from src.lib.types import (
    CensoredStr,
    Token,
    TokenFound,
    TokenNotFound,
)


def clean_raw_token(raw_token: str) -> str:
    """Clean double quotes of raw token."""
    return raw_token.strip('"').strip()


def get_browser_token(driver: WebDriver) -> str:
    """Reads the browser's localStorage and returns the cleaned token or an empty string."""
    if raw := driver.execute_script("return window.localStorage.getItem('token');"):
        return clean_raw_token(raw)
    return ""


def extract_token(driver: WebDriver) -> Token:
    """Attempts to extract the discord session token from window.localStorage."""
    for i in range(100):
        logger.debug(f"Attempt {i + 1} of trying to extract token")
        if token_str := get_browser_token(driver):
            return TokenFound(token=CensoredStr(token_str))

        time.sleep(0.5)
    return TokenNotFound()
