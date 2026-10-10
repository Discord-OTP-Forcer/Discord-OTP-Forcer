import sys
import time
from time import strftime
from types import FunctionType

from loguru import logger

from src.lib.types import ProgramConfig
from src.logger.logcreation import formatter, formatter_sensitive


def intialize_config_validator_logger() -> None:
    """
    Removes the default loguru sink and adds a custom one for the logs
    of the config validator.
    """
    logger.remove()

    logger.add(
        sys.stderr,
        format=formatter,
        colorize=True,
        backtrace=True,
        level="INFO",
    )


def _setup_file_logging(format: FunctionType) -> None:
    logger.add(
        "log/{}.log".format(strftime("%d-%m-%Y-%H_%M_%S", time.localtime(time.time()))),
        colorize=False,
        backtrace=True,
        format=format,
    )


def _setup_terminal_logging(format: FunctionType, logLevel: str) -> None:
    logger.add(
        sys.stderr,
        colorize=True,
        backtrace=True,
        format=format,
        level=logLevel,
    )


def initialize_program_logger(config: ProgramConfig) -> None:
    """
    Removes the default loguru sink and adds a custom one for the logs
    of the rest of the program.
    """
    logger.remove()

    # Change the format of success level messages to green background and black text
    logger.level("SUCCESS", color="<bold><black><bg green>")

    formatting: FunctionType = formatter_sensitive if config.sensitiveDebug else formatter

    if config.logCreation:
        _setup_file_logging(formatting)

    _setup_terminal_logging(formatting, config.logLevel)
