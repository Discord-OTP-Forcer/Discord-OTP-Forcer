"""Tests for the code error handling module (src.auth.code_errors)"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By, ByType

from src.auth.code_errors import _RATE_LIMIT_MESSAGES, _SERVICE_UNAVAILABLE_MESSAGES, get_code_status, parse_code_error
from src.lib.types import (
    CodeStatusFound,
    CodeStatusNotFound,
    InvalidCode,
    NetworkOffline,
    RateLimited,
    ServiceUnavailable,
    TokenExpired,
    UnknownError,
)


@pytest.fixture
def mock_driver() -> MagicMock:
    """Creates a fresh instance of a MagicMock that mocks the WebDriver from Selenium"""
    return MagicMock()


@pytest.fixture
def mock_wait() -> MagicMock:
    """Creates a fresh instance of a MagicMock that mocks WebDriverWait"""
    return MagicMock()


@pytest.fixture
def code_status_element() -> tuple[ByType, str]:
    """A dummy CSS locator used as the primary code status element"""
    return (By.CSS_SELECTOR, ".error-message")


class TestGetCodeStatusPrimaryElement:
    """Scenarios where the primary code status element is visible"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_driver: MagicMock):
        """Configure mock_driver to return primary element text"""
        mock_driver.find_element.return_value.text = "Invalid two-factor code"

    def test_returns_code_status_found(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should return CodeStatusFound when the primary element is visible"""
        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)

    def test_message_matches_element_text(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should capture the text content from the primary element"""
        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)
        assert result.message == "Invalid two-factor code"

    def test_used_fallback_is_false(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should set used_fallback=False when the primary element is found"""
        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)
        assert result.used_fallback is False

    def test_locator_passed_to_find_element(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should use the exact locator tuple to find the element"""
        get_code_status(mock_driver, mock_wait, code_status_element)

        mock_driver.find_element.assert_called_with(*code_status_element)


class TestGetCodeStatusFallback:
    """Scenarios where the primary element is not visible but the fallback XPath matches"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_driver: MagicMock, mock_wait: MagicMock):
        """Configure element not found and mock element response for fallback testing."""
        mock_wait.until.side_effect = NoSuchElementException()
        mock_driver.find_element.return_value.text = "Invalid two-factor code"

    def test_returns_code_status_found(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should return CodeStatusFound when a fallback XPath matches"""

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)

    def test_used_fallback_is_true(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should set used_fallback=True when falling back to XPath search"""

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)
        assert result.used_fallback is True

    def test_uses_xpath_locator(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should query the DOM using By.XPATH for the fallback"""

        get_code_status(mock_driver, mock_wait, code_status_element)

        args = mock_driver.find_element.call_args
        # Checks that find_element used the XPATH strategy
        assert args[0][0] == By.XPATH

    def test_timeout_returns_code_status_not_found(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should return CodeStatusNotFound and not trigger fallback on TimeoutException"""
        mock_wait.until.side_effect = TimeoutException()

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusNotFound)
        mock_driver.find_element.assert_not_called()

    def test_falls_through_on_no_such_element(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should also fall through to fallback when NoSuchElementException is raised"""
        mock_wait.until.side_effect = NoSuchElementException()

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)
        assert result.used_fallback is True

    def test_falls_through_on_stale_element(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should also fall through to fallback when StaleElementReferenceException is raised"""
        mock_wait.until.side_effect = StaleElementReferenceException()

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusFound)
        assert result.used_fallback is True


class TestGetCodeStatusNotFound:
    """Scenarios where neither the primary element nor fallback XPath is found"""

    def test_returns_code_status_not_found(
        self,
        mock_driver: MagicMock,
        mock_wait: MagicMock,
        code_status_element: tuple[ByType, str],
    ):
        """Should return CodeStatusNotFound when all lookups fail"""
        mock_wait.until.side_effect = NoSuchElementException()
        mock_driver.find_element.side_effect = NoSuchElementException()

        result = get_code_status(mock_driver, mock_wait, code_status_element)

        assert isinstance(result, CodeStatusNotFound)


class TestParseCodeErrorInvalidCode:
    """Tests for the 'Invalid two-factor code' branch"""

    def test_returns_invalid_code(self):
        """Should return InvalidCode for the exact invalid code message"""
        result = parse_code_error("Invalid two-factor code", "123456")

        assert isinstance(result, InvalidCode)

    def test_captures_attempted_code(self):
        """Should store the attempted code that triggered the error"""
        result = parse_code_error("Invalid two-factor code", "123456")

        assert isinstance(result, InvalidCode)
        assert result.attempted_code == "123456"

    def test_captures_raw_message(self):
        """Should store the raw invalid two-factor code error message"""
        msg = "Invalid two-factor code"
        result = parse_code_error(msg, "123456")

        assert isinstance(result, InvalidCode)
        assert result.raw_message == msg


class TestParseCodeErrorRateLimited:
    """Tests for all rate-limit message variants"""

    @pytest.mark.parametrize("message", sorted(_RATE_LIMIT_MESSAGES))
    def test_returns_rate_limited(self, message: str):
        """Should return RateLimited for known rate-limit messages"""
        result = parse_code_error(message, "123456")

        assert isinstance(result, RateLimited)

    @pytest.mark.parametrize("message", sorted(_RATE_LIMIT_MESSAGES))
    def test_captures_raw_message(self, message: str):
        """Should store the raw rate-limit message"""
        result = parse_code_error(message, "123456")

        assert isinstance(result, RateLimited)
        assert result.raw_message == message


class TestParseCodeErrorTokenExpired:
    """Tests for the token-expired branch"""

    def test_returns_token_expired(self):
        """Should return TokenExpired for the reset 400 HTTP status code message"""
        result = parse_code_error("POST /auth/reset [400]", "123456")

        assert isinstance(result, TokenExpired)

    def test_captures_raw_message(self):
        """Should store the raw reset error message"""
        msg = "POST /auth/reset [400]"
        result = parse_code_error(msg, "123456")

        assert isinstance(result, TokenExpired)
        assert result.raw_message == msg


class TestParseCodeErrorServiceUnavailable:
    """Tests for service-unavailable branch"""

    @pytest.mark.parametrize("message", sorted(_SERVICE_UNAVAILABLE_MESSAGES))
    def test_returns_service_unavailable(self, message: str):
        """Should return ServiceUnavailable for known 503 HTTP status code messages"""
        result = parse_code_error(message, "123456")

        assert isinstance(result, ServiceUnavailable)

    @pytest.mark.parametrize("message", sorted(_SERVICE_UNAVAILABLE_MESSAGES))
    def test_captures_raw_message(self, message: str):
        """Should store the raw service unavailable error message"""
        result = parse_code_error(message, "123456")

        assert isinstance(result, ServiceUnavailable)
        assert result.raw_message == message


class TestParseCodeErrorNetworkOffline:
    """Tests for the network-offline branch"""

    def test_returns_network_offline(self):
        """Should return NetworkOffline when the message contains 'the network is offline'"""
        result = parse_code_error("the network is offline", "123456")

        assert isinstance(result, NetworkOffline)

    def test_case_sensitive_match(self):
        """Should NOT match when the text is uppercase"""
        result = parse_code_error("The Network Is Offline", "123456")

        assert isinstance(result, UnknownError)

    def test_captures_raw_message(self):
        """Should store the raw network offline error message"""
        msg = "the network is offline"
        result = parse_code_error(msg, "123456")

        assert isinstance(result, NetworkOffline)
        assert result.raw_message == msg


class TestParseCodeErrorUnknown:
    """Tests for the unknown branch"""

    def test_returns_unknown_for_unrecognized_message(self):
        """Should return UnknownError for any message not matching known patterns"""
        result = parse_code_error("Something completely unexpected", "123456")

        assert isinstance(result, UnknownError)

    def test_captures_raw_message(self):
        """Should store the raw unrecognized error message"""
        msg = "Something completely unexpected"
        result = parse_code_error(msg, "123456")

        assert isinstance(result, UnknownError)
        assert result.raw_message == msg

    def test_empty_message(self):
        """Should return UnknownError for an empty string"""
        result = parse_code_error("", "123456")

        assert isinstance(result, UnknownError)
