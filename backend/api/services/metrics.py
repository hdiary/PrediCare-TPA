"""Métriques HTTP en mémoire (P3-18) : volume, erreurs et latence par route.

Portée : le processus courant, depuis son démarrage (remises à zéro au redémarrage).
Les métriques durables (prédictions, rejets, latence de scoring) viennent de la base.
Les routes sont identifiées par leur modèle (/alerts/{facture_id}), pas par l'URL réelle,
pour éviter une cardinalité infinie.
"""
import threading
import time
from collections import deque

import numpy as np

WINDOW = 1000   # latences conservées par route


class HttpMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        self._routes: dict[str, dict] = {}

    def record(self, method: str, route: str, status: int, duration_ms: float) -> None:
        key = f"{method} {route}"
        with self._lock:
            r = self._routes.setdefault(
                key, {"count": 0, "erreurs_4xx": 0, "erreurs_5xx": 0,
                      "latences": deque(maxlen=WINDOW)})
            r["count"] += 1
            if 400 <= status < 500:
                r["erreurs_4xx"] += 1
            elif status >= 500:
                r["erreurs_5xx"] += 1
            r["latences"].append(duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            routes = {}
            total = e4 = e5 = 0
            for key, r in self._routes.items():
                lat = np.asarray(r["latences"]) if r["latences"] else np.asarray([0.0])
                routes[key] = {
                    "count": r["count"],
                    "erreurs_4xx": r["erreurs_4xx"],
                    "erreurs_5xx": r["erreurs_5xx"],
                    "latence_ms": {
                        "moyenne": round(float(lat.mean()), 1),
                        "p50": round(float(np.percentile(lat, 50)), 1),
                        "p95": round(float(np.percentile(lat, 95)), 1),
                        "max": round(float(lat.max()), 1),
                    },
                }
                total += r["count"]
                e4 += r["erreurs_4xx"]
                e5 += r["erreurs_5xx"]
        return {
            "uptime_s": int(time.time() - self.started_at),
            "requetes_total": total,
            "erreurs_4xx": e4,
            "erreurs_5xx": e5,
            "taux_erreur_5xx": round(e5 / total, 4) if total else 0.0,
            "routes": routes,
        }

    def reset(self) -> None:
        with self._lock:
            self._routes.clear()
            self.started_at = time.time()


http_metrics = HttpMetrics()
