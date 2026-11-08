import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LaravelBCryptHasher(BasePasswordHasher):
    """Permet une connexion avec un hash bcrypt importé ; Django le renouvelle ensuite."""

    algorithm = "laravel_bcrypt"

    def verify(self, password, encoded):
        try:
            return bcrypt.checkpw(password.encode(), encoded.split("$", 1)[1].encode())
        except (ValueError, TypeError):
            return False

    def encode(self, password, salt=None, iterations=None):
        return (
            self.algorithm
            + "$"
            + bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        )

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm, "hash": mask_hash(encoded)}

    def must_update(self, encoded):
        return True
