from src.auth.token_login import login_with_discord_auth_token
from src.backend import bootstrap_browser, bootstrap_code_page, try_codes
from src.config.config_parser import load_configuration
from src.lib.check_updates import check_for_updates
from src.lib.types import (
    BrowserSession,
    CensoredStr,
    TokenFound,
)
from src.logger.log_init import initialize_check_logger, initialize_logger

if __name__ == "__main__":
    initialize_check_logger()
    config = load_configuration("config/account.yml", "config/program.yml")
    initialize_logger(config.program)
    session: BrowserSession | None = None

    if config.program.checkUpdates:
        check_for_updates()

    try:
        session = bootstrap_browser(config)
        if config.account.authToken:
            login_with_discord_auth_token(session, TokenFound(token=CensoredStr(config.account.authToken)))
        else:
            session = bootstrap_code_page(session)
            try_codes(session)
    except Exception as error:
        if config.program.logLevel in ("SENSITIVE", "DEBUG"):
            import stackprinter

            print(stackprinter.format(error, style="darkbg2"))
        else:
            import traceback

            import pygments
            from pygments.formatters import TerminalTrueColorFormatter
            from pygments.lexers import PythonTracebackLexer

            tb = traceback.format_exc()
            print(pygments.highlight(tb, PythonTracebackLexer(), TerminalTrueColorFormatter(style="native")))

    finally:
        if session:
            input("Press Enter to close the browser...")
            session.driver.quit()
