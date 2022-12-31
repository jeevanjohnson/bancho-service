from passlib.hash import argon2


def verify_password(password_md5: str, password_argon2: str) -> bool:
    return argon2.verify(password_md5, password_argon2)
