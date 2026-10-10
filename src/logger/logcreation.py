import re


def obfuscate_message(message: str) -> str:
    obfuscation_patterns: list[tuple[str, str]] = [
        (r"email=.*", "email: ******"),
        (r"password=.*", "password: ******"),
        (r"newPassword=.*", "newPassword: ******"),
        (r"resetToken=.*", "resetToken: ******"),
        (r"authToken=.*", "authToken: ******"),
        (r"#token=.*", "#token=******"),
    ]
    for pattern, replacement in obfuscation_patterns:
        message = re.sub(pattern, replacement, message)

    return message


def formatter(record) -> str:
    record["extra"]["obfuscated_message"] = record["message"]
    return "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}]</level> - <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{extra[obfuscated_message]}</level>\n{exception}"


def formatter_sensitive(record) -> str:
    record["extra"]["obfuscated_message"] = obfuscate_message(record["message"])
    return "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}]</level> - <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{extra[obfuscated_message]}</level>\n{exception}"
