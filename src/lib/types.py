import time
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path
from typing import NewType, TypedDict, assert_never

from selenium.webdriver.common.by import ByType
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from src.lib.constants import CODE_STATUS_ELT_CLASS, HOMEPAGE_CLASS

"""
This is the canonical definition for program and account configuration. all possibilities defined here

Naming convention here:

PascalCase for classes, types, kinds, enum-possibilities
camelCase for objects, variables, instances, members
"""


class ProgramMode(Enum):
    Login = 0
    Reset = 1


@dataclass
class CodeMode:
    pattern: str


@dataclass
class CodeMode_Normal(CodeMode):
    pattern: str = r"\d{6}"


@dataclass
class CodeMode_Backup(CodeMode):
    pattern: str = r"[a-z0-9]{8}"


class Browser(StrEnum):
    # SeleniumBase uses Chrome as default for "chrome",
    # if not, uses Chromium it seems.
    Chrome = "chrome"
    Chromium = "chromium"
    Thorium = "thorium"
    Brave = "brave"
    # Imposible for the moment to implement as this program
    # uses CDP commands and undetected-chromedriver
    # Firefox = "firefox"


@dataclass(frozen=True)
class ProgramConfig:
    """
    This is public and can be shared anywhere.
    """

    programMode: ProgramMode
    codeMode: CodeMode
    browser: Browser

    checkUpdates: bool
    sensitiveDebug: bool
    logCreation: bool
    headless: bool
    logLevel: str
    elementLoadTolerance: float

    usualAttemptDelayRange: tuple[int, int]
    ratelimitedAttemptDelayRange: tuple[int, int]


class CensoredStr(str):
    def __repr__(self) -> str:
        return "'******'"


@dataclass(frozen=True)
class AccountConfig:
    """
    I want this to be private and shared as little as possible.
    """

    email: str | CensoredStr
    password: str | CensoredStr

    newPassword: str | CensoredStr
    resetToken: str | CensoredStr

    authToken: str | CensoredStr


@dataclass(frozen=True)
class Config:
    program: ProgramConfig
    account: AccountConfig


@dataclass(frozen=True)
class BrowserSession:
    driver: WebDriver
    config: Config


class ProgramConfigDict(TypedDict):
    """
    Raw YAML structure for program configuration.
    """

    programMode: str
    codeMode: str
    browser: str
    checkUpdates: bool
    headless: bool
    logCreation: bool
    sensitiveDebug: bool
    logLevel: str
    elementLoadTolerance: float
    usualAttemptDelayMin: int
    usualAttemptDelayMax: int
    ratelimitedAttemptDelayMin: int
    ratelimitedAttemptDelayMax: int


@dataclass
class SessionStats:
    attemptedCodeCount: int  # The number of codes attempted in this session
    attemptedBackupCodeCount: int  # The number of backup codes attempted in this session
    ratelimitCount: int  # The number of times I got ratelimited
    slowDownCount: int  # The number of times the submit button loaded too slowly, because of a server-side invisible ratelimit or network conditions.
    serviceUnavailableCount: int  # The number of times discord was unavailable.
    elapsedTimeSeconds: float  # The time this program ran, in seconds


BinaryPath = NewType("BinaryPath", str)


@dataclass(frozen=True, slots=True)
class InvalidCode:
    attempted_code: str
    raw_message: str


@dataclass(frozen=True, slots=True)
class RateLimited:
    raw_message: str


@dataclass(frozen=True)
class ServiceUnavailable:
    raw_message: str


@dataclass(frozen=True)
class TokenExpired:
    raw_message: str


@dataclass(frozen=True)
class UnknownError:
    raw_message: str


@dataclass(frozen=True)
class NetworkOffline:
    raw_message: str


CodeError = InvalidCode | RateLimited | ServiceUnavailable | TokenExpired | UnknownError | NetworkOffline


@dataclass(frozen=True, slots=True)
class CodeStatusFound:
    message: str
    used_fallback: bool


@dataclass(frozen=True, slots=True)
class CodeStatusNotFound:
    pass


CodeStatusResult = CodeStatusFound | CodeStatusNotFound


@dataclass(frozen=True, slots=True)
class SubmissionSuccess:
    pass


@dataclass(frozen=True, slots=True)
class SubmissionError:
    status: CodeStatusFound


@dataclass(frozen=True, slots=True)
class SubmissionTimeout:
    pass


@dataclass(frozen=True, slots=True)
class SubmissionPending:
    pass


SubmissionResult = SubmissionSuccess | SubmissionError | SubmissionTimeout | SubmissionPending


@dataclass(frozen=True, slots=True)
class CheckLoginSuccess:
    """Callable condition that checks if the program has successfully logged in."""

    homepage: tuple[ByType, str] = HOMEPAGE_CLASS

    def check(self, driver: WebDriver) -> bool:
        """Default check."""
        return "/channels" in driver.current_url or bool(driver.find_elements(*self.homepage))

    def __call__(self, driver: WebDriver) -> bool:
        """Delegates to self.check for Selenium's WebDriverWait callable condition."""
        return self.check(driver)


@dataclass(frozen=True, slots=True)
class CheckSubmissionResult:
    """Callable condition that checks the outcome of a code submission."""

    wait: WebDriverWait[WebDriver]

    code_status_elt: tuple[ByType, str] = CODE_STATUS_ELT_CLASS
    login: CheckLoginSuccess = CheckLoginSuccess()

    def check(self, driver: WebDriver) -> SubmissionResult:
        """Determines whether the submission succeeded, failed, or is still pending."""
        from src.auth.code_errors import get_code_status

        if self.login.check(driver):
            return SubmissionSuccess()

        match get_code_status(driver, self.wait, self.code_status_elt):
            case CodeStatusFound() as found:
                return SubmissionError(status=found)
            case CodeStatusNotFound():
                if self.login.check(driver):
                    return SubmissionSuccess()
                return SubmissionPending()
            case _ as unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class TokenFound:
    token: CensoredStr

    def save_to_file(self, path: Path) -> None:
        with path.open("a+", encoding="utf-8") as f:
            f.write(f"{self.token}\n")


@dataclass(frozen=True, slots=True)
class TokenNotFound:
    pass


Token = TokenFound | TokenNotFound


@dataclass(slots=True)
class Stopwatch:
    _start: float = field(default_factory=time.monotonic)
    _stop: float | None = None

    def stop(self) -> None:
        self._stop = time.monotonic()

    def elapsed(self) -> float:
        # If the Stopwatch stopped, return the elapsed time between start time and stop time
        if self._stop is not None:
            return self._stop - self._start

        # If not, return the elapsed time between start time and now
        return time.monotonic() - self._start


@dataclass(frozen=True)
class TomlNotFound:
    pass


@dataclass(frozen=True)
class TomlParseError:
    pass


@dataclass(frozen=True)
class NetworkError:
    reason: str


VersionCheckError = TomlNotFound | TomlParseError | NetworkError

LocalVersion = NewType("LocalVersion", str)
CodebergVersion = NewType("CodebergVersion", str)


@dataclass(frozen=True)
class ValidationOk:
    pass


@dataclass(frozen=True)
class ValidationError:
    message: str


ValidationResult = ValidationOk | ValidationError


class FileRef(StrEnum):
    config = "config"
    account = "account"


@dataclass(frozen=True)
class FileRead:
    raw: str
    lines: list[str]


@dataclass(frozen=True)
class FileReadError:
    message: str


FileReadResult = FileRead | FileReadError


@dataclass(frozen=True)
class YamlParsed:
    data: dict


@dataclass(frozen=True)
class YamlParseError:
    message: str


YamlParseResult = YamlParsed | YamlParseError
