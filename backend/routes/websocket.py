"""
routes/websocket.py
Endpoint WebSocket pour les notifications temps réel du pipeline de traitement.

Protocole :
  - Connexion : ws://host/ws/{user_id}?token=<jwt>
  - Événements envoyés au client :
      { "status": "processing", "document_id": int, "message": str }
      { "status": "completed",  "document_id": int, "message": str,
        "subject": str, "doc_type": str, "language": str, "num_chunks": int }
      { "status": "error",      "document_id": int, "message": str }
"""

import logging
import asyncio
from typing import Dict, List

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# ─── Connection Manager ───────────────────────────────────────────────────────

class ConnectionManager:
    """
    Gestionnaire de connexions WebSocket par user_id.
    Supporte plusieurs onglets simultanés pour un même utilisateur.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self) -> None:
        # user_id (str) → liste de WebSocket actives
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, []).append(websocket)
        logger.info(
            "WS connected: user_id=%s (connexions actives=%d)",
            user_id,
            len(self._connections[user_id]),
        )

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self._connections.pop(user_id, None)
        logger.info("WS disconnected: user_id=%s", user_id)

    async def notify(self, user_id: int, payload: dict) -> None:
        """
        Envoie un payload JSON à toutes les connexions de l'utilisateur.
        Nettoie silencieusement les connexions mortes.
        """
        uid = str(user_id)
        async with self._lock:
            conns = list(self._connections.get(uid, []))

        dead: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(uid, ws)

        if conns:
            logger.debug(
                "WS notify user_id=%s status=%s doc_id=%s",
                uid,
                payload.get("status"),
                payload.get("document_id"),
            )


# Singleton partagé à travers toute l'application
manager = ConnectionManager()


# ─── Auth helper ─────────────────────────────────────────────────────────────

def _verify_token(token: str) -> str | None:
    """
    Décode le JWT et retourne le user_id (str), ou None si invalide.
    Le claim 'sub' est stocké comme str(user.id) (voir auth/auth.py).
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None


# ─── Endpoint WebSocket ───────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT Bearer token"),
) -> None:
    """
    WebSocket de notifications de traitement documentaire.

    Authentification par query param `token` (les navigateurs ne permettent
    pas d'envoyer des headers personnalisés lors du handshake WS).

    Le serveur ferme la connexion avec 1008 (Policy Violation) si :
      - le token est absent / invalide / expiré
      - le user_id dans l'URL ne correspond pas au token
    """
    verified_id = _verify_token(token)
    if verified_id is None or verified_id != str(user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(
            "WS auth rejected: user_id=%s (token valide pour user_id=%s)",
            user_id,
            verified_id,
        )
        return

    await manager.connect(user_id, websocket)
    try:
        # Boucle de keep-alive : le client peut envoyer des pings texte
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
