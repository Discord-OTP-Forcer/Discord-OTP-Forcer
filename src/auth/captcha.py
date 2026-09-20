import time

from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import ByType
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.lib.constants import CAPTCHA_CONTAINER_CLASS
from src.lib.types import Config


def captcha_detection(driver: WebDriver, config: Config) -> None:
    captcha_box: tuple[ByType, str] = CAPTCHA_CONTAINER_CLASS
    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance)

    try:
        wait.until(EC.presence_of_element_located(captcha_box))
        logger.info("A captcha detected. Please complete the captcha for the program to continue.")

        while driver.find_elements(*captcha_box):
            time.sleep(1)

        logger.debug("Captcha has been completed. Moving on to the rest of the script.")

    except TimeoutException:
        logger.debug("No captcha detected. Moving on to the rest of the script.")
