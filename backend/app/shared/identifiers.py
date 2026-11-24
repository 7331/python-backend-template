import secrets

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
RANDOM_PART_LENGTH = 22


def generate_public_id(prefix: str) -> str:
    return prefix + "".join(secrets.choice(BASE58_ALPHABET) for _ in range(RANDOM_PART_LENGTH))
