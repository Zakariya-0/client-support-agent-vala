import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from main import executor
from conversation import ConversationManager
from database import db
from tools import set_current_client_email
from config import FRONTEND_ORIGIN
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vala Support Agent")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware : uniquement le frontend connu, pas n'importe quel site (allow_origins=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

conv_mgr = ConversationManager()

# Models Pydantic
class SupportQuery(BaseModel):
    client_email: str
    message: str

class ChatResponse(BaseModel):
    status: str
    response: str
    timestamp: str

# Endpoints
@app.get("/health")
async def health():
    """Vérifier que l'API fonctionne"""
    return {"status": "✅ Online", "model": "qwen2.5:3b"}

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, query: SupportQuery) -> ChatResponse:
    """Endpoint principal : recevoir message du client, retourner réponse"""
    try:
        # Récupérer le contexte du client
        context = conv_mgr.get_context(query.client_email)

        # Construire le message complet avec contexte
        full_message = f"{context}\n\nClient message: {query.message}"

        # Rendre l'email du client disponible aux tools (create_support_ticket,
        # reset_password, renew_domain — jamais l'email fourni par le LLM)
        set_current_client_email(query.client_email)

        # Lancer l'agent
        result = executor.invoke({"input": full_message})
        response = result['output']

        # Sauvegarder la conversation
        conv_mgr.save_message(
            query.client_email,
            query.message,
            response
        )

        return ChatResponse(
            status="success",
            response=response,
            timestamp=datetime.now().isoformat()
        )

    except Exception:
        # Le détail complet part dans les logs serveur, jamais dans la réponse au client
        logger.exception(f"Erreur lors du traitement de /chat pour {query.client_email}")
        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue. Veuillez réessayer plus tard."
        )

@app.get("/status/{client_email}")
async def get_status(client_email: str):
    """Récupérer les infos d'un client"""
    client = db.get_client(client_email)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    name, plan, domains, usage, expires = client
    return {
        "name": name,
        "plan": plan,
        "domains": domains,
        "usage_percent": usage,
        "expires": expires
    }

# Run with: python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
