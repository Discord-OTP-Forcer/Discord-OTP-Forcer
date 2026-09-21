# Import dependencies and libraries
import secrets
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import assert_never

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
from .lib.constants import (
    AUTH_ERROR_INTERCEPTOR_JS,
    BACKUP_CODE_FIELD,
    CODE_STATUS_ELT_CLASS,
    HARDEN_WEB_STORAGE_JS,
    IS_A_BUG_STRING,
    LOW_ELEMENT_LOAD_TOLERANCE_STRING,
    NORMAL_CODE_FIELD,
    NORMAL_CODE_FIELD_FALLBACK,
)
from .lib.exceptions import CodeFieldNotFound, CredentialsFieldNotFound, InvalidCredentialError, UnhandledCodeModeException
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
    ProgramConfig,
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
                {"source": HARDEN_WEB_STORAGE_JS},
            )
            logger.debug("Hardened local web storage")

            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": AUTH_ERROR_INTERCEPTOR_JS},
            )
            logger.debug("Installed auth api interceptor")
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
            return BACKUP_CODE_FIELD
        case CodeMode_Normal():
            return NORMAL_CODE_FIELD
        case _:
            raise UnhandledCodeModeException(f"Unhandled code mode: {code_mode}")


def _is_error_or_2fa_present(driver: WebDriver) -> bool:
    """Checks if Discord's API returned an error or if 2FA elements have appeared."""
    if driver.execute_script("return window.__authError;"):
        return True
    if driver.find_elements(By.XPATH, "//*[contains(text(), 'Verify with something else')]"):
        return True
    if driver.find_elements(*NORMAL_CODE_FIELD) or driver.find_elements(*NORMAL_CODE_FIELD_FALLBACK):
        return True
    return bool(driver.find_elements(*BACKUP_CODE_FIELD))


def _wait_for_auth_response_or_2fa(driver: WebDriver) -> None:
    """Wait 2 seconds for either an API error or 2FA elements to appear after submitting credentials."""
    try:
        short_wait: WebDriverWait[WebDriver] = WebDriverWait(driver, 2)
        short_wait.until(_is_error_or_2fa_present)
    except TimeoutException:
        pass


def _verify_credentials(driver: WebDriver, programMode: ProgramMode) -> None:
    """Check if Discord's API returned an error during login or reset."""

    _wait_for_auth_response_or_2fa(driver)

    if not driver.execute_script("return window.__authError;"):
        return

    err: str
    match programMode:
        case ProgramMode.Reset:
            err = "Your password reset token is invalid or it may have expired. Generate a new one and fill it in your config/account.yml file. See discord-otp-forcer.codeberg.page/en/user/setup/#how-to-get-your-reset-token for more information."
        case ProgramMode.Login:
            err = "Your login credentials are invalid. Please check again if you typed it correctly."
        case _ as unreachable:
            assert_never(unreachable)

    logger.critical(err)
    raise InvalidCredentialError(err)


def _select_2fa_method(driver: WebDriver, config: Config) -> None:
    """Selects the 2FA method on the 2FA screen."""

    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance)
    wait_longer: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance * 2)

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
                    logger.critical("Cannot use Backup mode - you likely have no backup codes left. ", IS_A_BUG_STRING)
                case CodeMode_Normal():
                    logger.critical("Cannot use Normal mode - it's likely that you DO NOT have an authenticator app linked to your Discord account. ", IS_A_BUG_STRING)
                case _:
                    logger.critical("Cannot use Backup mode with regex mode - you likely have no backup codes left. ", IS_A_BUG_STRING)
            sys.exit(1)
    except TimeoutException as only_normal_code_mode_found:
        logger.debug("Only found one TOTP method, proceeding with it")
        match config.program.codeMode:
            case CodeMode_Backup():
                logger.critical("Cannot use backup mode - you likely have no backup codes left. ", IS_A_BUG_STRING)
                sys.exit(1)
            case CodeMode_Normal():
                try:
                    wait.until(EC.presence_of_element_located(NORMAL_CODE_FIELD_FALLBACK))
                    logger.debug("Code field with '6-digit authentication code' placeholder found, no need to select mode")
                except TimeoutException:
                    # TODO: Need to test more why this could happen
                    logger.critical(
                        "Cannot use normal mode - Unknown error on exception 'only_normal_code_mode_found'. "
                        "Please report this by creating an issue at codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new "
                        "so that the developers can look into the issue and fix it."
                    )
                    sys.exit(1)
            case _:
                logger.critical("Cannot use backup mode with regex mode - you likely have no backup codes left. ", IS_A_BUG_STRING)
                sys.exit(1)


def _check_if_code_field_exists(driver: WebDriver, config: Config) -> None:
    """Checks if the code entry field exists on the page."""

    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance)

    try:
        code_field: tuple[ByType, str] = _get_code_field(config.program.codeMode)
        wait.until(EC.presence_of_element_located(code_field))
    except TimeoutException:
        msg: str = f"Could not locate the code field on the page. {LOW_ELEMENT_LOAD_TOLERANCE_STRING}"
        logger.critical(msg)
        raise CodeFieldNotFound(msg)


def bootstrap_code_page(session: BrowserSession) -> BrowserSession:
    """
    This sets up the code entry page.
    """
    driver: WebDriver = session.driver
    config: Config = session.config
    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, config.program.elementLoadTolerance)

    # Go to the appropriate starting page for the mode
    landing_url: str = _get_landing_url(config.program.programMode, config.account.resetToken)

    driver.get(landing_url)
    logger.debug(f"Gone to {config.program.programMode.name} page")

    # Log-in with credentials
    password_field: tuple[ByType, str] = (By.NAME, "password")
    try:
        match config.program.programMode:
            case ProgramMode.Login:
                email_field: tuple[ByType, str] = (By.NAME, "email")
                wait.until(EC.presence_of_element_located(email_field)).send_keys(config.account.email)
                wait.until(EC.presence_of_element_located(password_field)).send_keys(config.account.password)
            case ProgramMode.Reset:
                wait.until(EC.presence_of_element_located(password_field)).send_keys(config.account.newPassword)
            case _ as unreachable:
                assert_never(unreachable)
        wait.until(EC.presence_of_element_located(password_field)).send_keys(Keys.RETURN)
    except TimeoutException as email_or_password_field_not_located:
        msg: str = f"Could not locate the email or password field on the page. {LOW_ELEMENT_LOAD_TOLERANCE_STRING}"
        logger.critical(msg)
        raise CredentialsFieldNotFound(msg)

    logger.debug("Found and filled in basic login fields")

    captcha_detection(driver, config)

    _verify_credentials(driver, config.program.programMode)

    _select_2fa_method(driver, config)

    _check_if_code_field_exists(driver, config)

    return session


def wait_for_submission_result(driver: WebDriver) -> SubmissionResult:
    """Polls the submission result of a generated code."""

    wait: WebDriverWait[WebDriver] = WebDriverWait(driver, 0.5)
    warned_taking_long: bool = False

    condition: CheckSubmissionResult = CheckSubmissionResult(wait)

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


def _select_sleep_duration(rate_limited: bool, program: ProgramConfig) -> list[int]:
    if not rate_limited:
        return list(program.usualAttemptDelayRange)
    else:
        return list(program.ratelimitedAttemptDelayRange)


def _add_attempt_to_session(code_mode: CodeMode, sessionStats: SessionStats) -> None:
    match code_mode:
        case CodeMode_Normal():
            sessionStats.attemptedCodeCount += 1
        case CodeMode_Backup():
            sessionStats.attemptedBackupCodeCount += 1
        case _:
            raise ValueError(f"Unhandled CodeMode: {code_mode}")


def _read_used_backup_codes_file() -> list[str]:
    file_path = Path("secret/used_backup_codes.txt")
    if not file_path.exists():
        return []
    return file_path.read_text(encoding="utf-8").splitlines()


def _write_to_used_backup_codes_file(random_code: str) -> None:
    with open("secret/used_backup_codes.txt", "a") as f:
        f.write(f"{random_code}\n")


def _check_if_code_was_tested(code_mode: CodeMode, generated_code: str, make_new_code: bool) -> str:
    used_backup_codes: list[str] = _read_used_backup_codes_file()

    if make_new_code:
        while generated_code in used_backup_codes:
            logger.warning(f"Backup code {generated_code} was already tested. Will generate another code.")
            generated_code = generate_random_code(code_mode)
        _write_to_used_backup_codes_file(generated_code)
    else:
        # If rate limiting occurs, do not generate a new code
        if generated_code in used_backup_codes:
            logger.warning(f"Backup code {generated_code} wasn't tested. Will test once the ratelimiting is over.")

    return generated_code


def _get_backup_code(code_mode: CodeMode, make_new_code: bool, generated_code: str) -> str:
    if make_new_code:
        generated_code = generate_random_code(code_mode)
    return _check_if_code_was_tested(code_mode, generated_code, make_new_code)


def _get_code_for_attempt(code_mode: CodeMode, make_new_code: bool, current_code: str) -> str:
    """Gets the code for the current attempt."""
    match code_mode:
        case CodeMode_Normal():
            return generate_random_code(code_mode)
        case CodeMode_Backup():
            return _get_backup_code(code_mode, make_new_code, current_code)
        case _:
            raise ValueError(f"Unhandled CodeMode: {code_mode}")


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
    code_status_elt: tuple[ByType, str] = CODE_STATUS_ELT_CLASS

    make_new_code: bool = True
    rate_limited: bool = False
    random_code: str = ""

    logger.info("Starting a Forcer session")
    logger.debug("\n" + pformat(config.program))
    logger.log("SENSITIVE", "\n" + pformat(config.account))

    # Generate a new code.
    try:
        while True:
            sleep_duration_range = _select_sleep_duration(rate_limited, config.program)

            # Use the gen'd backup code only if it's not in the used_backup_codes.txt list. Add the code to the list if I use it.
            random_code = _get_code_for_attempt(config.program.codeMode, make_new_code, random_code)

            # Attempt the code
            try:
                code_field_element = user_wait_longer.until(EC.element_to_be_clickable(code_field))
                code_field_element.clear()
                code_field_element.send_keys(random_code)
                time.sleep(secrets.choice(sleep_duration_range))
                submit_button_element = user_wait_longer.until(EC.element_to_be_clickable(submit_button))
                submit_button_element.click()
                _add_attempt_to_session(config.program.codeMode, sessionStats)

            except TimeoutException as element_isnt_clickable:
                logger.warning(f"Element isn't clickable yet after {config.program.elementLoadTolerance * 3} sec. You may be on a slow network or ratelimited.")
                sessionStats.slowDownCount += 1
                make_new_code = False
                continue

            # Success check. Break out if it succeeded.
            submission_result: SubmissionResult = wait_for_submission_result(driver)

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
                            rate_limited = False

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
                            rate_limited = False
                        case NetworkOffline(raw_message=msg):
                            logger.error("Network disconnection detected. Trying again in 15 seconds...")
                            time.sleep(15)
                            make_new_code = False
                            rate_limited = False
                        case UnknownError(raw_message=msg):
                            logger.error(f"Encountered unimplemented status message. Tell the developers about this: {msg}")
                            make_new_code = False
                            rate_limited = False
                        case _ as unreachable:
                            assert_never(unreachable)
                case SubmissionTimeout():
                    logger.warning("Status never arrived after 60 sec. Skipping.")
                    make_new_code = False
                    rate_limited = False
                    sessionStats.slowDownCount += 1
                case SubmissionPending():
                    logger.error("Submission remained pending unexpectedly. Please go to codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new and create an issue about this.")
                    make_new_code = False
                    rate_limited = False
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
