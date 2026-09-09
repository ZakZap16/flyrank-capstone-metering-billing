import bcrypt
import secrets
from functools import lru_cache


@lru_cache(maxsize=1000)
def _verify_api_key_cached(plain_key: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(plain_key.encode(), hash_str.encode())
    except Exception:
        return False


class AuthService:
    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        plain_key = secrets.token_urlsafe(32)
        hash_bytes = bcrypt.hashpw(plain_key.encode(), bcrypt.gensalt())
        hash_str = hash_bytes.decode()
        return plain_key, hash_str
    
    @staticmethod
    def verify_api_key(plain_key: str, hash_str: str) -> bool:
        return _verify_api_key_cached(plain_key, hash_str)
    
    @staticmethod
    def clear_cache() -> None:
        _verify_api_key_cached.cache_clear()
