import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "phi")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "clients.db")

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Optimisations for 8GB RAM
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "5"))
MAX_TOKENS_OUTPUT = int(os.getenv("MAX_TOKENS_OUTPUT", "200"))

# Email
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "mailtrap")  # "mailtrap" ou "gmail"
EMAIL_MODE = os.getenv("EMAIL_MODE", "production")  # "production" ou "dev" (affiche dans le terminal, n'envoie rien)

# Mailtrap
MAILTRAP_API_TOKEN = os.getenv("MAILTRAP_API_TOKEN", "")

# Gmail SMTP
def _env_bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "30"))  # secondes
SMTP_USE_SSL = _env_bool("SMTP_USE_SSL", False)  # True = SSL direct (port 465) au lieu de STARTTLS (587)
SMTP_FALLBACK_SSL = _env_bool("SMTP_FALLBACK_SSL", True)  # si STARTTLS échoue, retente en SSL sur le port 465
SMTP_SSL_FALLBACK_PORT = 465

# Commun
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "")
RENEWAL_URL = os.getenv("RENEWAL_URL", "")
RESET_URL = os.getenv("RESET_URL", "")
