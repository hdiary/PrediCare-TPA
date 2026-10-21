"""Limite la taille des corps de requête (protection contre l'envoi de volumes absurdes)."""
import json


class BodySizeLimitMiddleware:
    """Répond 413 si l'en-tête Content-Length dépasse la limite.

    Limite connue : un corps envoyé en « chunked » sans Content-Length n'est pas arrêté ici ;
    à compléter par la limite du reverse proxy (client_max_body_size) en production.
    """

    def __init__(self, app, max_bytes: int, path_limits: dict[str, int] | None = None):
        self.app = app
        self.max_bytes = max_bytes
        self.path_limits = path_limits or {}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            raw = dict(scope["headers"]).get(b"content-length")
            max_bytes = self.path_limits.get(scope.get("path"), self.max_bytes)
            if raw and raw.isdigit() and int(raw) > max_bytes:
                body = json.dumps({"detail": "Requête trop volumineuse"}).encode()
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
