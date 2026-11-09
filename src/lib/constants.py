from pathlib import Path
from typing import Final

from selenium.webdriver.common.by import By, ByType

_SCRIPTS_DIR: Final[Path] = Path(__file__).parent / "js_scripts"

HARDEN_WEB_STORAGE_JS: Final[str] = (_SCRIPTS_DIR / "HardenWebStorage.js").read_text(encoding="utf-8")
AUTH_ERROR_INTERCEPTOR_JS: Final[str] = (_SCRIPTS_DIR / "AuthErrorInterceptor.js").read_text(encoding="utf-8")

IS_A_BUG_STRING: Final[str] = "If you think this is a bug, please go to codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new and create an issue."
LOW_ELEMENT_LOAD_TOLERANCE_STRING: Final[str] = (
    "This may be caused by a low 'elementLoadTolerance' value in your config/program.yml file. Try increasing it to 5 or 7. (Or even higher if your internet connection or computer is slow.)\n If that does not fix the issue, please create a new issue at codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new to ask for help."
)

BACKUP_CODE_FIELD_FALLBACK_STRINGS: Final[set[str]] = {
    "//*[@placeholder='8-digit backup code']",
    "//*[@label='Enter Discord Backup Code']",
}
NORMAL_CODE_FIELD_FALLBACK_STRINGS: Final[set[str]] = {
    "//*[@placeholder='6-digit authentication code']",
    "//*[@label='Enter Discord Auth Code']",
}

BACKUP_CODE_FIELD_FALLBACK: Final[tuple[ByType, str]] = (
    By.XPATH,
    " | ".join(BACKUP_CODE_FIELD_FALLBACK_STRINGS),
)
NORMAL_CODE_FIELD_FALLBACK: Final[tuple[ByType, str]] = (
    By.XPATH,
    " | ".join(NORMAL_CODE_FIELD_FALLBACK_STRINGS),
)

CAPTCHA_CONTAINER_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "container_dvN-MP")
INPUT_CODE_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "input_0PLWhS")
CODE_STATUS_ELT_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "error_b5g7JS")
HOMEPAGE_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "app_QbT-Jy")
