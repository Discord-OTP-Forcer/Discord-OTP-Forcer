# Import dependencies and libraries
import secrets
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Final, assert_never

from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By, ByType
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from src.binary_finder.find_chromium import find_chromium_binary, register_chromium_browser
from src.binary_finder.find_thorium import find_thorium_binary, register_thorium_browser

from .auth.captcha import captcha_detection
from .auth.code_errors import parse_code_error
from .auth.token_extraction import extract_token
from .lib.codegen import generate_random_code
from .lib.exceptions import InvalidCredentialError
from .lib.types import (
    BinaryPath,
    Browser,
    BrowserSession,
    CheckSubmissionResult,
    CodeMode,
    CodeMode_Backup,
    CodeMode_Normal,
    CodeStatusFound,
    Config,
    InvalidCode,
    NetworkOffline,
    ProgramMode,
    RateLimited,
    ServiceUnavailable,
    SessionStats,
    Stopwatch,
    SubmissionError,
    SubmissionPending,
    SubmissionResult,
    SubmissionSuccess,
    SubmissionTimeout,
    TokenExpired,
    TokenFound,
    TokenNotFound,
    UnknownError,
)

_IS_A_BUG_STRING: Final[str] = "If you think this is a bug, please go to codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new and create an issue."

logger.level(name="SENSITIVE", no=15, color="<m><b>")


def _resolve_and_register_binary_location(browser: Browser) -> BinaryPath | None:
    """
    Returns the binary path for browsers not natively recognized by SeleniumBase, or None if not needed.
    """
    match browser:
        case Browser.Thorium:
            register_thorium_browser()
            return find_thorium_binary()
        case Browser.Chromium:
            register_chromium_browser()
            return find_chromium_binary()

    return None


def bootstrap_browser(config: Config) -> BrowserSession:
    """
    bootstrap_browser is a function that prepares a puppetable browser.
    """

    match config.program.browser:
        case Browser.Chrome | Browser.Brave | Browser.Chromium | Browser.Thorium:
            _HARDEN_WEB_STORAGE_JS: Final[str] = (Path(__file__).parent / "lib/js_scripts" / "HardenWebStorage.js").read_text(encoding="utf-8")

            driver = Driver(
                browser="chrome" if config.program.browser in (Browser.Chromium, Browser.Thorium) else config.program.browser,
                uc=True,
                binary_location=_resolve_and_register_binary_location(config.program.browser),
                headless=config.program.headless,
                locale_code="en-US",
                chromium_arg="--log-level=1" if config.program.headless else None,
            )

            driver.implicitly_wait(0)

            driver.execute_cdp_cmd("Network.enable", {})

            driver.execute_cdp_cmd(
                "Network.setBlockedURLs",
                {
                    "urls": [
                        "a.nel.cloudflare.com/report",
                        "https://discord.com/api/v10/science",
                        "https://discord.com/api/v9/science",
                        "sentry.io",
                    ]
                },
            )

            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": _HARDEN_WEB_STORAGE_JS},
            )
            logger.debug("Fixed compatibility polyfill")
        case _ as unreachable:
            assert_never(unreachable)

    logger.debug("Started browser")

    return BrowserSession(driver=driver, config=config)


def _get_landing_url(program_mode: ProgramMode, reset_token: str) -> str:
    match program_mode:
        case ProgramMode.Login:
            return "https://discord.com/login"
        case ProgramMode.Reset:
            return f"https://discord.com/reset#token={reset_token}"
        case _ as unreachable:
            assert_never(unreachable)


def _get_code_field(code_mode: CodeMode) -> tuple[ByType, str]:
    match code_mode:
        case CodeMode_Backup():
            return (By.XPATH, "//*[@label='Enter Discord Backup Code']")
        case CodeMode_Normal():
            return (By.XPATH, "//*[@label='Enter Discord Auth Code']")
        case _:
            raise ValueError(f"Unhandled CodeMode: {code_mode}")


def bootstrap_code_page(session: BrowserSession) -> BrowserSession:
    """
    This sets up the code entry page.
    """
    driver: WebDriver = session.driver
    config: Config = session.config
    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance)
    wait_longer: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance * 2)

    # Go to the appropriate starting page for the mode
    landing_url: str = _get_landing_url(config.program.programMode, config.account.resetToken)

    driver.get(landing_url)
    logger.debug(f"Gone to {config.program.programMode.name} page")

    # Log-in with credentials
    password_field: tuple[ByType, str] = (By.NAME, "password")
    email_field: tuple[ByType, str] = (By.NAME, "email")
    try:
        match config.program.programMode:
            case ProgramMode.Login:
                wait.until(EC.presence_of_element_located(email_field)).send_keys(config.account.email)
                wait.until(EC.presence_of_element_located(password_field)).send_keys(config.account.password)
            case ProgramMode.Reset:
                wait.until(EC.presence_of_element_located(password_field)).send_keys(config.account.newPassword)
            case _ as unreachable:
                assert_never(unreachable)
        wait.until(EC.presence_of_element_located(password_field)).send_keys(Keys.RETURN)
    except TimeoutException as email_or_password_field_not_located:
        logger.critical(
            "Could not locate the email or password field on the page."
            "This may be caused by a low 'elementLoadTolerance' value in your config/program.yml file."
            "Try increasing it to 5 or 7. (Or even higher if your internet connection or computer is slow.)"
        )
        logger.critical("If that does not fix the issue, please create a new issue at codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new to ask for help.")
        sys.exit(1)

    logger.debug("Found and filled in basic login fields")

    captcha_detection(session)

    # Select the method
    try:
        short_wait = WebDriverWait(driver, 1)
        short_wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Verify with something else')]"))).click()
        try:
            match config.program.codeMode:
                case CodeMode_Normal():
                    wait_longer.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Use your authenticator app')]"))).click()
                case CodeMode_Backup():
                    wait_longer.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Use a backup code')]"))).click()
                    time.sleep(11)
                    wait_longer.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'use a backup code')]"))).click()
        except TimeoutException:
            match config.program.codeMode:
                case CodeMode_Backup():
                    logger.critical("Cannot use Backup mode - you likely have no backup codes left. ", _IS_A_BUG_STRING)
                case CodeMode_Normal():
                    logger.critical("Cannot use Normal mode - it's likely that you DO NOT have an authenticator app linked to your Discord account. ", _IS_A_BUG_STRING)
                case _:
                    logger.critical("Cannot use Backup mode with regex mode - you likely have no backup codes left. ", _IS_A_BUG_STRING)
            sys.exit(1)
    except TimeoutException as only_normal_code_mode_found:
        logger.debug("Only found one TOTP method, proceeding with it")
        match config.program.codeMode:
            case CodeMode_Backup():
                logger.critical("Cannot use backup mode - you likely have no backup codes left. ", _IS_A_BUG_STRING)
                sys.exit(1)
            case CodeMode_Normal():
                try:
                    # TODO: maybe do this a little better later
                    code_field_6_digit: tuple[ByType, str] = (By.XPATH, "//*[@placeholder='6-digit authentication code']")
                    wait.until(EC.presence_of_element_located(code_field_6_digit))
                    logger.debug("Code field with '6-digit authentication code' placeholder found, no need to select mode")
                except TimeoutException:
                    # TODO: Need to document or test more this
                    logger.critical(
                        "Cannot use normal mode - Unknown error on exception 'only_normal_code_mode_found'. "
                        "Please report this by creating an issue at codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new "
                        "so that the developers can look into the issue and fix it."
                    )
                    sys.exit(1)
            case _:
                logger.critical("Cannot use backup mode with regex mode - you likely have no backup codes left. ", _IS_A_BUG_STRING)
                sys.exit(1)

    # Check if the code field exists
    try:
        # TODO: detect when this code field is not found correctly
        code_field: tuple[ByType, str] = (By.CLASS_NAME, "input__75098")
        wait.until(EC.presence_of_element_located(code_field))
    except TimeoutException:
        msg: str
        # TODO: And only show this error messages when it actually can't log in on the account / the password reset token IS expired
        match config.program.programMode:
            case ProgramMode.Login:
                msg = "Could not log in to your account. Is your email and password correct? You may have to reset your password. Check the wiki/docs at discord-otp-forcer.codeberg.page/en/user/setup for more information."
                logger.critical(msg)
                raise InvalidCredentialError(msg)
            case ProgramMode.Reset:
                msg = "Your password reset token may have expired. Generate a new one and fill it in your config/account.yml file. See discord-otp-forcer.codeberg.page/en/user/setup/#how-to-get-your-reset-token for more information."
                logger.critical(msg)
                raise InvalidCredentialError(msg)

    return session


def wait_for_submission_result(
    driver: WebDriver,
    code_status_elt: tuple[ByType, str],
) -> SubmissionResult:
    """Polls the submission result of a generated code."""

    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, 0.5)
    warned_taking_long: bool = False

    condition: CheckSubmissionResult = CheckSubmissionResult(
        code_status_elt=code_status_elt,
        wait=wait,
    )

    timer: Stopwatch = Stopwatch()

    # Poll until condition.check() returns a non-pending result or timeout.
    while timer.elapsed() < 60.0:
        if not warned_taking_long and timer.elapsed() >= 15.0:
            logger.warning("Code taking longer than 15s to submit, you may be on a slow network or rate-limited. Waiting for status...")
            warned_taking_long = True

        result = condition.check(driver)
        match result:
            case SubmissionSuccess() | SubmissionError() | SubmissionTimeout():
                return result
            case SubmissionPending():
                time.sleep(0.5)
            case _ as unreachable:
                assert_never(unreachable)
    return SubmissionTimeout()


def try_codes(session: BrowserSession) -> None:
    """Logic to continously enter TOTP/Backup codes"""
    driver: WebDriver = session.driver
    config: Config = session.config

    user_wait_longer: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance * 3)

    # Set up statistics counters
    sessionStats: SessionStats = SessionStats(0, 0, 0, 0, 0, 0)
    timer: Stopwatch = Stopwatch()

    sleep_duration_range: list[int]

    submit_button: tuple[ByType, str] = (By.XPATH, "//*[@type='submit']")
    code_field: tuple[ByType, str] = _get_code_field(config.program.codeMode)
    code_status_elt: tuple[ByType, str] = (By.CLASS_NAME, "error__7c901")

    make_new_code: bool = False
    rate_limited: bool = False
    random_code: str = generate_random_code(config.program.codeMode)

    logger.info("Starting a Forcer session")
    logger.debug("\n" + pformat(config.program))
    logger.log("SENSITIVE", "\n" + pformat(config.account))

    # Generate a new code.
    try:
        while True:
            if not rate_limited:
                sleep_duration_range = list(config.program.usualAttemptDelayRange)
            else:
                sleep_duration_range = list(config.program.ratelimitedAttemptDelayRange)
                rate_limited = False

            # Use the gen'd backup code only if it's not in the used_backup_codes.txt list. Add the code to the list if I use it.
            # the thing that really sucks here is even if a backup code is valid, by trying it here and logging in, I invalidate it. (backup codes expire on use)
            if isinstance(config.program.codeMode, CodeMode_Backup):
                if make_new_code:
                    random_code = generate_random_code(config.program.codeMode)

                with open("secret/used_backup_codes.txt", "a+") as f:
                    f.seek(0)
                    used_backup_codes: list[str] = f.read().splitlines()
                    if random_code in used_backup_codes:
                        if make_new_code:
                            logger.warning(f"Backup code {random_code} is invalid. Possibly I previously used it, but now it's expired anyway.")
                            random_code = generate_random_code(config.program.codeMode)
                        else:  # If rate limiting occurs, do not generate a new code
                            logger.warning(f"Backup code {random_code} wasn't tested. Will test once the ratelimiting is over.")
                    else:
                        f.write(f"{random_code}\n")
            else:
                random_code = generate_random_code(config.program.codeMode)

            # Attempt the code
            try:
                code_field_element = user_wait_longer.until(EC.element_to_be_clickable(code_field))
                code_field_element.clear()
                code_field_element.send_keys(random_code)
                time.sleep(secrets.choice(sleep_duration_range))
                submit_button_element = user_wait_longer.until(EC.element_to_be_clickable(submit_button))
                submit_button_element.click()
                if isinstance(config.program.codeMode, CodeMode_Backup):
                    sessionStats.attemptedBackupCodeCount += 1
                else:
                    sessionStats.attemptedCodeCount += 1
            except TimeoutException as element_isnt_clickable:
                logger.warning(f"Element isn't clickable yet after {config.program.elementLoadTolerance * 3} sec. You may be on a slow network or ratelimited.")
                sessionStats.slowDownCount += 1
                make_new_code = False
                continue

            # Success check. Break out if it succeeded.
            submission_result: SubmissionResult = wait_for_submission_result(
                driver=driver,
                code_status_elt=code_status_elt,
            )

            match submission_result:
                case SubmissionSuccess():
                    logger.debug("Homepage found, trying to extract token")
                    match extract_token(driver):
                        case TokenFound() as tokenFound:
                            logger.info("FOUND YOUR ACCOUNT'S TOKEN. SAVE IT AND DO NOT LOG OUT OF DISCORD!")
                            logger.success(tokenFound.token)
                            tokenFound.save_to_file(Path("secret/token.txt"))
                        case TokenNotFound():
                            logger.warning("Token not found but logged in successfully.")
                    break
                case SubmissionError(status=CodeStatusFound(message=code_status_msg, used_fallback=used_fallback)):
                    if used_fallback:
                        logger.warning(f"Code Status Element '{code_status_elt[1]}' not found, using fallback selectors. Please report this to the developers.")
                    match parse_code_error(code_status_msg, random_code):
                        case InvalidCode(attempted_code=code, raw_message=msg):
                            logger.warning(f"{msg}: {code}")
                            make_new_code = True
                        case RateLimited(raw_message=msg):
                            logger.warning(msg)
                            sessionStats.ratelimitCount += 1
                            make_new_code = False
                            rate_limited = True
                        case TokenExpired(raw_message=msg):
                            logger.critical(f"{msg}: The reset token has expired. Please create a new reset token and update it in config/account.yml")
                            sys.exit()
                        case ServiceUnavailable(raw_message=msg):
                            logger.warning(f"{msg}: The service is unavailable, Discord is probably under maintenance.")
                            sessionStats.serviceUnavailableCount += 1
                            make_new_code = False
                        case NetworkOffline(raw_message=msg):
                            logger.error("Network disconnection detected. Trying again in 15 seconds...")
                            time.sleep(15)
                            make_new_code = False
                        case UnknownError(raw_message=msg):
                            logger.error(f"Encountered unimplemented status message. Tell the developers about this: {msg}")
                        case _ as unreachable:
                            assert_never(unreachable)
                case SubmissionTimeout():
                    logger.warning("Status never arrived after 60 sec. Skipping.")
                    make_new_code = False
                    sessionStats.slowDownCount += 1
                case SubmissionPending():
                    logger.error("Submission remained pending unexpectedly. Please go to codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new and create an issue about this.")
                    make_new_code = False
                case _ as unreachable:
                    assert_never(unreachable)

    except KeyboardInterrupt:
        logger.critical("Stopping the program on KeyboardInterrupt!")

    timer.stop()
    sessionStats.elapsedTimeSeconds = timer.elapsed()
    logger.critical("Program finished!")
    print_session_statistics(sessionStats)


def print_session_statistics(sessionStats: SessionStats) -> None:
    logger.info("\n" + pformat(sessionStats))
