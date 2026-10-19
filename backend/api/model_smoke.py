"""Container executable check for seed artefact/schema coherence."""
from api.model_seed import check_seed_coherence


if __name__ == "__main__":
    check_seed_coherence()
    print("model seed feature schemas: OK")
