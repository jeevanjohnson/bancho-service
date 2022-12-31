from passlib.hash import argon2


def encrypt_password_md5(password_md5: str) -> str:
    return argon2.hash(password_md5)
