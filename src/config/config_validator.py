import re
from collections.abc import Sequence
from re import Match, Pattern
from typing import Any, assert_never

import yaml
from loguru import logger

from src.lib.types import (
    Browser,
    FileRead,
    FileReadError,
    FileReadResult,
    FileRef,
    ProgramMode,
    ValidationError,
    ValidationOk,
    ValidationResult,
    YamlParsed,
    YamlParseError,
    YamlParseResult,
)

EXPECTED_PROGRAM_FIELDS: frozenset[str] = frozenset(
    {
        "programMode",
        "codeMode",
        "browser",
        "sensitiveDebug",
        "logCreation",
        "checkUpdates",
        "headless",
        "logLevel",
        "elementLoadTolerance",
        "usualAttemptDelayMin",
        "usualAttemptDelayMax",
        "ratelimitedAttemptDelayMin",
        "ratelimitedAttemptDelayMax",
    }
)

_EXPECTED_ACCOUNT_FIELDS: frozenset[str] = frozenset({"email", "password", "newPassword", "resetToken", "authToken"})
_INVALID_TOKEN_PREFIXES: frozenset[str] = frozenset({"https://", "http://", "discord.com", "#token="})


def _read_yaml_file(path: str, ref: FileRef) -> FileReadResult:
    """
    Read a YAML file and return its raw content and lines.
    Returns a FileRead on success, or FileReadError if the file is missing or cannot be opened.
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            raw: str = file.read()
        return FileRead(raw=raw, lines=raw.splitlines())
    except FileNotFoundError:
        match ref:
            case FileRef.config:
                return FileReadError(f"Config file not found on path: '{path}'")
            case FileRef.account:
                return FileReadError(f"Account file not found on path: '{path}'")
            case _ as unreachable:
                assert_never(unreachable)
    except OSError as e:
        return FileReadError(f"Could not open '{path}': {e}")


def _parse_yaml(path: str, raw: str, lines: Sequence[str]) -> YamlParseResult:
    """
    Parse a raw YAML string into a dictionary.
    Returns YamlParsed on success, or YamlParseError with details about formatting problems
    """
    try:
        data = yaml.safe_load(raw)
    except yaml.MarkedYAMLError:
        for i, line in enumerate(lines, start=1):
            stripped: str = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            bad_key_value: Match[str] | None = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*):(\S+)").match(stripped)
            if bad_key_value:
                key, val = bad_key_value.group(1), bad_key_value.group(2)
                return YamlParseError(f"'{path}' line {i}: '{key}' missing a space after colon. Change '{key}:{val}' to '{key}: {val}'")
        return YamlParseError(
            f"'{path}' has invalid formatting and could not be read. Report this here: https://codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new, and provide as much information as possible."
        )
    except yaml.YAMLError:
        return YamlParseError(
            f"'{path}' has invalid formatting and could not be read. Report this here: https://codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new, and provide as much information as possible."
        )

    if not isinstance(data, dict):
        return YamlParseError(f"'{path}' does not contain a valid YAML mapping.")
    return YamlParsed(data)


def _find_key_line(lines: Sequence[str], key: str) -> int | None:
    """
    Return the line number where th key first appears in the given lines, or None if not found.
    """
    pattern: Pattern[str] = re.compile(rf"^\s*{re.escape(key)}\s*:")
    for i, line in enumerate(lines, start=1):
        if pattern.match(line):
            return i
    return None


def _location(lines: Sequence[str], key: str) -> str:
    """
    Return a string like " (line n)" if the key is found in the lines, otherwise an empty string.
    """
    line_number: int | None = _find_key_line(lines, key)
    return f" (line {line_number})" if line_number else ""


def _is_empty(value: object) -> bool:
    """
    Check if a value is None or an empty/whitespace-only string.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _collect_errors(results: Sequence[ValidationResult]) -> list[str]:
    """
    Extract error messages from a sequence of ValidationResult, returning only ValidationError messages.
    """
    return [error.message for error in results if isinstance(error, ValidationError)]


def _log_and_exit_on_errors(errors: Sequence[str]) -> None:
    """
    Log each error message and exit the program with code 1 if any errors are present.
    """
    for msg in errors:
        logger.error(msg)
    if errors:
        raise SystemExit(1)


def _validate_program_mode(path: str, lines: Sequence[str], parsed: dict) -> ValidationResult:
    """
    Check that 'programMode' is one of the valid ProgramModes available.
    Returns ValidationOk or ValidationError with a list of the allowed options.
    """
    key_value = parsed.get("programMode")
    valid = ", ".join(mode.name for mode in ProgramMode)
    if _is_empty(key_value):
        return ValidationError(f"'{path}'{_location(lines, 'programMode')}: 'programMode' is empty. Valid options are: {valid}")
    if key_value not in ProgramMode._member_names_:
        return ValidationError(f"'{path}'{_location(lines, 'programMode')}: '{key_value}' is not a valid programMode. Valid options are: {valid}")
    return ValidationOk()


def _validate_browser(path: str, lines: Sequence[str], parsed: dict) -> ValidationResult:
    """
    Check that 'browser' is one of the valid valid Browsers available.
    Returns ValidationOk or ValidationError with a list of the allowed options.
    """
    key_value = parsed.get("browser")
    valid = ", ".join(browser.name for browser in Browser)
    if _is_empty(key_value):
        return ValidationError(f"'{path}'{_location(lines, 'browser')}: 'browser' is empty. Valid options are: {valid}")
    if key_value not in Browser._member_names_:
        return ValidationError(f"'{path}'{_location(lines, 'browser')}: '{key_value}' is not a valid browser. Valid options are: {valid}")
    return ValidationOk()


def _validate_code_mode(path: str, lines: Sequence[str], parsed: dict) -> ValidationResult:
    """
    Check that 'codeMode' is not empty.
    Returns ValidationOk or ValidationError explaining the expected format.
    """
    key_value = parsed.get("codeMode")
    if _is_empty(key_value):
        return ValidationError(
            f"'{path}'{_location(lines, 'codeMode')}: 'codeMode' is empty. Valid options are: Normal, Backup, or a custom regex in double quotes. e.g. \"aqzi[a-z0-9]{{4}}\""
        )
    return ValidationOk()


def _validate_boolean_field(path: str, lines: Sequence[str], parsed: dict, key: str) -> ValidationResult:
    """
    Verify that the key exists, is not empty, and is a boolean.
    Returns ValidationOk or a ValidationError describing describing the problem.
    """
    if key not in parsed:
        return ValidationError(f"'{path}': '{key}' is missing. Must be True or False.")
    if _is_empty(parsed[key]):
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' is empty. Must be True or False.")
    if not isinstance(parsed[key], bool):
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' must be True or False, got '{parsed[key]}'.")
    return ValidationOk()


def _validate_number_field(path: str, lines: Sequence[str], parsed: dict, key: str) -> ValidationResult:
    """
    Verify that the key is not a negative number (int or float) and not a boolean.
    Returns ValidationOk or a ValidationError describing the problem.
    """
    if key not in parsed:
        return ValidationError(f"'{path}': '{key}' is missing. Must be a positive number.")
    if _is_empty(parsed[key]):
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' is empty. Must be a positive number.")
    if isinstance(parsed[key], bool) or not isinstance(parsed[key], (int, float)) or parsed[key] < 0:
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' must be a positive number, got '{parsed[key]}'.")
    return ValidationOk()


def _validate_account_field(path: str, lines: Sequence[str], parsed: dict, key: str, description: str, program_mode: str) -> ValidationResult:
    """
    Check that an account field is not empty.
    The 'description' explains the field’s role, and 'program_mode' indicates the current mode.
    """
    if _is_empty(parsed.get(key)):
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' is empty. {description} is required for programMode '{program_mode}'.")
    return ValidationOk()


def _validate_password_length(path: str, lines: Sequence[str], parsed: dict, key: str) -> ValidationResult:
    """Checks that the password is at least 8 characters long."""
    min_length: int = 8
    val = parsed.get(key)

    if _is_empty(val):
        return ValidationOk()

    if isinstance(val, str) and len(val) < min_length:
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' must be at least {min_length} characters long.")
    return ValidationOk()


def _validate_password_complexity(path: str, lines: Sequence[str], parsed: dict, key: str) -> ValidationResult:
    """
    Checks that the password includes at least 3 of 4 character types:
    uppercase, lowercase, numbers, and symbols.
    """
    val = parsed.get(key)

    if _is_empty(val) or not isinstance(val, str):
        return ValidationOk()

    has_upper = bool(re.search(r"[A-Z]", val))
    has_lower = bool(re.search(r"[a-z]", val))
    has_digit = bool(re.search(r"[0-9]", val))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", val))

    types_count = sum([has_upper, has_lower, has_digit, has_symbol])
    if types_count < 3:
        return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' must include 3 of these 4 character types: uppercase, lowercase, number and symbols.")
    return ValidationOk()


def _validate_reset_token(path: str, lines: Sequence[str], parsed: dict, key: str) -> ValidationResult:
    """
    Checks if resetToken contains a full URL instead of just the token.
    The user must provide only the raw token string without the full URL path.
    """
    val = parsed.get(key)

    if _is_empty(val):
        return ValidationOk()

    if isinstance(val, str):
        clean_val = val.strip()
        if any(prefix in clean_val for prefix in _INVALID_TOKEN_PREFIXES):
            return ValidationError(f"'{path}'{_location(lines, key)}: '{key}' must be the token only, not the full URL. Use the value after '#token='.")
    return ValidationOk()


def validate_program_config(path: str) -> None:
    """
    Validate the program configuration file.
    Reads and parses the file, checks all required fields, warns about unknown or missing keys,
    and exits the program if any errors are found.
    """
    logger.debug(f"Validating '{path}'...")

    file_result: FileReadResult = _read_yaml_file(path, FileRef.config)
    if isinstance(file_result, FileReadError):
        logger.error(file_result.message)
        raise SystemExit(1)

    parse_result: YamlParseResult = _parse_yaml(path, file_result.raw, file_result.lines)
    if isinstance(parse_result, YamlParseError):
        logger.error(parse_result.message)
        raise SystemExit(1)

    parsed_yaml: dict[Any, Any] = parse_result.data
    raw_lines: list[str] = file_result.lines

    # TODO: do this better
    for key in sorted(parsed_yaml.keys() - EXPECTED_PROGRAM_FIELDS):
        logger.warning(f"'{path}': unrecognised key '{key}'. Check for typos.")
    for key in sorted(EXPECTED_PROGRAM_FIELDS - parsed_yaml.keys()):
        logger.warning(f"'{path}': missing key '{key}'. The program may crash.")

    errors: Sequence[str] = _collect_errors(
        results=[
            _validate_program_mode(path, raw_lines, parsed_yaml),
            _validate_browser(path, raw_lines, parsed_yaml),
            _validate_code_mode(path, raw_lines, parsed_yaml),
            _validate_boolean_field(path, raw_lines, parsed_yaml, "checkUpdates"),
            _validate_boolean_field(path, raw_lines, parsed_yaml, "headless"),
            _validate_boolean_field(path, raw_lines, parsed_yaml, "logCreation"),
            _validate_boolean_field(path, raw_lines, parsed_yaml, "sensitiveDebug"),
            _validate_number_field(path, raw_lines, parsed_yaml, "elementLoadTolerance"),
            _validate_number_field(path, raw_lines, parsed_yaml, "ratelimitedAttemptDelayMax"),
            _validate_number_field(path, raw_lines, parsed_yaml, "ratelimitedAttemptDelayMin"),
            _validate_number_field(path, raw_lines, parsed_yaml, "usualAttemptDelayMax"),
            _validate_number_field(path, raw_lines, parsed_yaml, "usualAttemptDelayMin"),
        ]
    )

    _log_and_exit_on_errors(errors)
    logger.debug(f"'{path}' passed validation.")


def validate_account_config(path: str, program_mode: ProgramMode) -> None:
    """
    Validate the account configuration file for the given program mode.
    Checks that all required fields (email/password for Login, resetToken/newPassword for Reset)
    are not empty, warns about unknown or missing keys, and exits the program if any errors are found.
    """
    logger.debug(f"Validating '{path}' for programMode='{program_mode}'...")

    file_result: FileReadResult = _read_yaml_file(path, FileRef.account)
    if isinstance(file_result, FileReadError):
        logger.error(file_result.message)
        raise SystemExit(1)

    parse_result: YamlParseResult = _parse_yaml(path, file_result.raw, file_result.lines)
    if isinstance(parse_result, YamlParseError):
        logger.error(parse_result.message)
        raise SystemExit(1)

    parsed_yaml = parse_result.data
    raw_lines = file_result.lines

    # TODO: do this better
    for key in sorted(parsed_yaml.keys() - _EXPECTED_ACCOUNT_FIELDS):
        logger.warning(f"'{path}': unrecognised key '{key}'. Check for typos.")
    for key in sorted(_EXPECTED_ACCOUNT_FIELDS - parsed_yaml.keys()):
        logger.warning(f"'{path}': missing key '{key}'. The program may crash.")

    field_results: list[ValidationResult]
    match program_mode:
        case ProgramMode.Login:
            field_results = [
                _validate_account_field(path, raw_lines, parsed_yaml, "email", "An email address", program_mode.name),
                _validate_account_field(path, raw_lines, parsed_yaml, "password", "A password", program_mode.name),
            ]
        case ProgramMode.Reset:
            field_results = [
                _validate_account_field(path, raw_lines, parsed_yaml, "resetToken", "A reset token", program_mode.name),
                _validate_account_field(path, raw_lines, parsed_yaml, "newPassword", "A new password", program_mode.name),
                _validate_reset_token(path, raw_lines, parsed_yaml, "resetToken"),
                _validate_password_length(path, raw_lines, parsed_yaml, "newPassword"),
                _validate_password_complexity(path, raw_lines, parsed_yaml, "newPassword"),
            ]
        case _ as unreachable:
            assert_never(unreachable)

    _log_and_exit_on_errors(_collect_errors(field_results))
    logger.debug(f"'{path}' passed validation.")
