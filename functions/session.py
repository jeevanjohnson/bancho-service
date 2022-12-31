import uuid


def generate_token() -> str:
    return str(uuid.uuid4())
