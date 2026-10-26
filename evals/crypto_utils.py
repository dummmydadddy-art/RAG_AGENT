import base64
import json
import os
from pathlib import Path
from typing import Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_LEN = 16


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_evals(checks: Dict[str, str], passphrase: str, output_path: Path) -> None:
    """Encrypts hidden evaluation test codes into a password-protected binary file."""
    salt = os.urandom(SALT_LEN)
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    payload = json.dumps(checks).encode("utf-8")
    ciphertext = fernet.encrypt(payload)

    with open(output_path, "wb") as f:
        f.write(salt + ciphertext)


def decrypt_evals(archive_path: Path, passphrase: str) -> Dict[str, str]:
    """Decrypts hidden evaluation test codes from the password-protected binary file."""
    if not archive_path.exists():
        raise FileNotFoundError(f"Encrypted evaluation archive not found at: {archive_path}")

    with open(archive_path, "rb") as f:
        data = f.read()

    if len(data) < SALT_LEN:
        raise ValueError("Invalid evaluation archive data (too short).")

    salt = data[:SALT_LEN]
    ciphertext = data[SALT_LEN:]
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)

    decrypted_bytes = fernet.decrypt(ciphertext)
    return json.loads(decrypted_bytes.decode("utf-8"))
