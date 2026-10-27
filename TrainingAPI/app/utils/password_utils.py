import hashlib
import secrets


def hash_password(password):
    salt = secrets.token_bytes(16)
    iterations = 600000
    digest = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, iterations
    )
    return f'pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}'


def verify_password(password, password_hash):
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
        if len(salt) != 16 or len(expected_digest) != 32:
            return False
        digest = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt, int(iterations)
        )
        return secrets.compare_digest(digest, expected_digest)
    except (AttributeError, TypeError, ValueError):
        return False
