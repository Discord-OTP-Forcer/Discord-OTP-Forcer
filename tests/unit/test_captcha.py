"""Tests for the captcha detection module (src.auth.captcha)"""

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import TimeoutException

from src.auth.captcha import captcha_detection
from src.lib.types import AccountConfig, BrowserSession, Config, ProgramConfig


@pytest.fixture
def mock_driver() -> MagicMock:
    """Creates a fresh instance of a MagicMock that mocks the WebDriver from Selenium"""
    return MagicMock()


@pytest.fixture
def mock_config() -> MagicMock:
    """Creates a fresh instance of a MagicMock that mocks the application configuration"""
    program_config = MagicMock(spec=ProgramConfig)
    program_config.elementLoadTolerance = 5.0

    account_config = MagicMock(spec=AccountConfig)

    config = MagicMock(spec=Config)
    config.program = program_config
    config.account = account_config

    return config


@pytest.fixture
def browser_session(mock_driver: MagicMock, mock_config: MagicMock) -> BrowserSession:
    """Provides a BrowserSession instance using the mocked driver and configuration"""
    return BrowserSession(driver=mock_driver, config=mock_config)


class TestCaptchaPresent:
    """Scenarios where the captcha element is initially detected"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Patch WebDriverWait and time.sleep"""
        webDriverWait_patcher = patch("src.auth.captcha.WebDriverWait")
        sleep_patcher = patch("src.auth.captcha.time.sleep")

        webDriverWait_patcher.start()
        self.sleep_mock = sleep_patcher.start()

        try:
            yield

        finally:
            sleep_patcher.stop()
            webDriverWait_patcher.stop()

    def test_polls_until_captcha_disappears(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should poll the captcha element repeatedly until it disappears from the DOM"""
        mock_driver.find_elements.side_effect = [
            ["captcha"],
            ["captcha"],
            ["captcha"],
            [],
        ]

        captcha_detection(browser_session.driver, browser_session.config)

        assert mock_driver.find_elements.call_count == 4, "Expected find_elements to be called exactly 4 times"

    def test_pauses_execution_for_each_active_captcha(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should call time.sleep exactly once for each time the captcha is detected"""
        mock_driver.find_elements.side_effect = [["captcha"], ["captcha"], []]

        captcha_detection(browser_session.driver, browser_session.config)

        assert self.sleep_mock.call_count == 2, "Expected time.sleep to be called exactly 2 times"

    def test_polling_delay_is_exactly_one_second(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should pause the execution for exactly 1 second during the polling cycle"""
        mock_driver.find_elements.side_effect = [["captcha"], []]

        captcha_detection(browser_session.driver, browser_session.config)

        self.sleep_mock.assert_called_with(1)

    def test_correct_locator_used(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should search for the captcha by class name using the expected CSS selector"""
        mock_driver.find_elements.side_effect = [["captcha"], []]

        captcha_detection(browser_session.driver, browser_session.config)

        mock_driver.find_elements.assert_any_call("class name", "container__8a031")

    def test_disappears_on_first_poll(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should call find_elements only once when the captcha is already gone on the first check"""
        mock_driver.find_elements.side_effect = [[]]

        captcha_detection(browser_session.driver, browser_session.config)

        assert mock_driver.find_elements.call_count == 1, "Expected find_elements to be called exactly 1 times"

    def test_no_sleep_when_disappears_immediately(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should not sleep if the while loop exits on its first evaluation"""
        mock_driver.find_elements.side_effect = [[]]

        captcha_detection(browser_session.driver, browser_session.config)

        self.sleep_mock.assert_not_called()

    def test_returns_none(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should always return None. Callers do not handle any return value"""
        mock_driver.find_elements.side_effect = [["captcha"], []]

        result = captcha_detection(browser_session.driver, browser_session.config)

        assert result is None


class TestNoCaptcha:
    """Scenarios where no captcha element is present (WebDriverWait times out)"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Patch WebDriverWait so that wait.until() raises TimeoutException"""
        webDriverWait_patcher = patch("src.auth.captcha.WebDriverWait")
        wait_mock = webDriverWait_patcher.start()

        wait_instance = MagicMock()
        wait_instance.until.side_effect = TimeoutException()
        wait_mock.return_value = wait_instance
        self.wait_mock = wait_mock

        try:
            yield

        finally:
            webDriverWait_patcher.stop()

    def test_skips_polling(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should never enter the polling loop when TimeoutException is raised"""
        captcha_detection(browser_session.driver, browser_session.config)

        mock_driver.find_elements.assert_not_called()

    def test_configured_timeout_passed_to_wait(
        self,
        browser_session: BrowserSession,
        mock_config: MagicMock,
    ):
        """Should forward elementLoadTolerance from config as the WebDriverWait timeout"""
        mock_config.program.elementLoadTolerance = 10.0

        captcha_detection(browser_session.driver, browser_session.config)

        self.wait_mock.assert_called_once_with(browser_session.driver, 10.0)

    def test_wait_receives_correct_driver(
        self,
        browser_session: BrowserSession,
        mock_driver: MagicMock,
    ):
        """Should pass the session's driver instance to WebDriverWait"""
        captcha_detection(browser_session.driver, browser_session.config)

        actual_driver = self.wait_mock.call_args[0][0]
        assert actual_driver is mock_driver

    def test_ec_receives_correct_locator(
        self,
        browser_session: BrowserSession,
    ):
        """Should pass the captcha locator tuple to EC.presence_of_element_located"""
        expected_locator = ("class name", "container__8a031")

        ec_patcher = patch("src.auth.captcha.EC.presence_of_element_located")
        ec_mock = ec_patcher.start()

        try:
            captcha_detection(browser_session.driver, browser_session.config)
            ec_mock.assert_called_once_with(expected_locator)
        finally:
            ec_patcher.stop()

    def test_returns_none(
        self,
        browser_session: BrowserSession,
    ):
        """Should always return None. Callers do not handle any return value"""
        result = captcha_detection(browser_session.driver, browser_session.config)

        assert result is None
