from pathlib import Path
from typing import Final

from selenium.webdriver.common.by import By, ByType

_SCRIPTS_DIR: Final[Path] = Path(__file__).parent / "lib/js_scripts"

HARDEN_WEB_STORAGE_JS: Final[str] = (_SCRIPTS_DIR / "HardenWebStorage.js").read_text(encoding="utf-8")
AUTH_ERROR_INTERCEPTOR_JS: Final[str] = (_SCRIPTS_DIR / "AuthErrorInterceptor.js").read_text(encoding="utf-8")

IS_A_BUG_STRING: Final[str] = "If you think this is a bug, please go to codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new and create an issue."

BACKUP_CODE_FIELD: Final[tuple[ByType, str]] = (By.XPATH, "//*[@label='Enter Discord Backup Code']")
NORMAL_CODE_FIELD: Final[tuple[ByType, str]] = (By.XPATH, "//*[@label='Enter Discord Auth Code']")
NORMAL_CODE_FIELD_FALLBACK: Final[tuple[ByType, str]] = (By.XPATH, "//*[@placeholder='6-digit authentication code']")

CAPTCHA_CONTAINER_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "container__8a031")
CODE_STATUS_ELT_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "error__7c901")
HOMEPAGE_CLASS: Final[tuple[ByType, str]] = (By.CLASS_NAME, "app__160d8")
