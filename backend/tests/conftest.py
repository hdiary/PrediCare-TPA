"""Configuration commune des tests.

Les tests d'intégration (test_integration_frontend.py) s'exécutent contre un vrai PostgreSQL si la
variable TEST_DATABASE_URL est définie (ex. postgresql://postgres:pw@127.0.0.1:5432/postgres) ;
sinon ils sont ignorés. Les autres tests n'ont besoin d'aucune base.
"""
import os

os.environ.setdefault("JWT_SECRET", "x" * 40)
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"].rsplit("/", 1)[0] + "/predicare_it"
else:
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
