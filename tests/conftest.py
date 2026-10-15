import os
import pathlib
import sys

# Variables d'environnement AVANT l'import de l'application
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "x" * 40)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
