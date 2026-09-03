import bcrypt
import secrets

class AuthService:
    """API key generation and verification."""
    
    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """
        Generate a new API key and its hash.
        Returns (plain_key, hash).
        Plain key is only shown once - store hash in database.
        """
        plain_key = secrets.token_urlsafe(32)
        hash_bytes = bcrypt.hashpw(plain_key.encode(), bcrypt.gensalt())
        hash_str = hash_bytes.decode()
        return plain_key, hash_str
    
    @staticmethod
    def verify_api_key(plain_key: str, hash_str: str) -> bool:
        """Verify a plain API key against stored hash."""
        try:
            return bcrypt.checkpw(plain_key.encode(), hash_str.encode())
        except Exception:
            return False