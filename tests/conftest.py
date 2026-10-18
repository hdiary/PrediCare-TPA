import os
import pathlib
import sys

from cryptography.fernet import Fernet

# Variables d'environnement AVANT l'import de l'application
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "x" * 40)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("IDENTITY_ENCRYPTION_KEY", Fernet.generate_key().decode())

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
