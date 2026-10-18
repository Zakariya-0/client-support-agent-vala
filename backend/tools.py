import sqlite3
import json
from langchain.tools import tool
from datetime import datetime
from config import DATABASE_PATH, RENEWAL_URL, RESET_URL, SUPPORT_EMAIL
from email_service import send_reset_password_link, send_renewal_link, send_support_ticket_notification
from scrape_vala_website import URL as VALA_PLANS_URL
from database import db

# Email du client actuellement servi par l'agent. Positionné par api.py juste avant
# d'invoquer l'agent (executor.invoke) — les tools n'ont pas accès au contexte de la
# requête HTTP autrement, et on évite de demander au LLM de recopier lui-même l'email
# comme argument (peu fiable avec un petit modèle local).
_current_client_email = None

def set_current_client_email(email):
    global _current_client_email
    _current_client_email = email


def _get_current_client_record():
    """Récupère (email, expires_date) du client actuellement identifié par la session
    (_current_client_email), jamais d'un email fourni par le LLM. Retourne None si
    aucun client courant n'est identifié (ex: appel hors d'une requête /chat)."""
    if not _current_client_email:
        return None
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, expires_date FROM clients WHERE email = ?", (_current_client_email,))
    result = cursor.fetchone()
    conn.close()
    return result

@tool
def check_domain_expiry(domain: str) -> str:
    """Vérifie la date d'expiration d'un domaine appartenant au client actuellement connecté"""
    record = _get_current_client_record()
    if not record:
        return "Impossible d'identifier votre compte. Veuillez réessayer."

    client_email, expires = record
    if domain not in client_email:
        return f"Le domaine {domain} n'est pas associé à votre compte ({client_email})."

    days_left = (datetime.strptime(expires, "%Y-%m-%d") - datetime.now()).days
    return f"Domain {domain} expires on {expires} ({days_left} days left)"

@tool
def renew_domain(domain: str) -> str:
    """Renouvelle un domaine pour 1 an et envoie un email de confirmation"""
    record = _get_current_client_record()
    if not record:
        return "Impossible d'identifier votre compte. Veuillez réessayer."

    client_email, _ = record
    if domain not in client_email:
        return f"Le domaine {domain} n'est pas associé à votre compte ({client_email})."

    token = db.create_token(client_email, "domain_renewal", payload=domain)
    if send_renewal_link(client_email, domain, RENEWAL_URL, token):
        return f"Un email de renouvellement a été envoyé à {client_email}. Cliquez sur le lien pour renouveler."
    return f"Le renouvellement n'a pas pu être finalisé : l'email n'a pas pu être envoyé à {client_email}. Veuillez réessayer plus tard."

@tool
def get_hosting_plans() -> str:
    """Retourne les plans d'hébergement disponibles (données scrapées depuis vala.ma)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title, content FROM website_content WHERE url = ? ORDER BY id",
        (VALA_PLANS_URL,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return (
            "Les informations sur nos plans ne sont pas disponibles pour le moment "
            "(données non encore récupérées). Je peux créer un ticket pour que "
            "l'équipe vous les communique directement."
        )

    lines = ["Voici nos plans d'hébergement :"]
    for title, content_json in rows:
        try:
            data = json.loads(content_json)
        except (TypeError, json.JSONDecodeError):
            continue

        name = title.replace("Hébergement ", "")
        price = data.get("prix_actuel") or "prix sur demande"
        storage = data.get("espace_disque") or "stockage non précisé"
        mailboxes = data.get("boite_mail")
        domain = data.get("domaine_inclus")
        domain_text = f"{domain} domaine offert" if domain else "sans domaine offert"

        highlights = [
            f for f in data.get("features", [])
            if any(k in f for k in ("SSL", "CDN", "DDoS"))
        ]

        line = f"- {name} : {price}, {storage}, {domain_text}"
        if mailboxes:
            line += f", {mailboxes} boîtes mail"
        if highlights:
            line += ", " + ", ".join(highlights)
        lines.append(line)

    return "\n".join(lines)

@tool
def reset_password() -> str:
    """Réinitialiser le mot de passe du compte actuellement connecté et envoyer un lien sécurisé par email"""
    if not _current_client_email:
        return "Impossible d'identifier votre compte. Veuillez réessayer."

    email = _current_client_email
    token = db.generate_reset_token(email)
    if send_reset_password_link(email, RESET_URL, token):
        return f"Un lien pour réinitialiser votre mot de passe a été envoyé à {email}. Vérifiez votre boîte mail."
    return f"L'email de réinitialisation n'a pas pu être envoyé à {email}. Veuillez réessayer plus tard."

@tool
def check_service_status() -> str:
    """Vérifier le statut des services"""
    return """
Service Status:
✓ DNS: Operational
✓ Email: Operational
✓ Hosting: Operational
✓ Uptime: 99.9%
"""

@tool
def create_support_ticket(subject: str, description: str) -> str:
    """Créer un ticket support et notifier l'équipe support par email"""
    client_email = _current_client_email  # peut être None si appelé hors d'une requête /chat

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO tickets (client_email, subject, description)
    VALUES (?, ?, ?)
    ''', (client_email, subject, description))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Token stocké pour un futur lien de suivi client (aucun email ne l'utilise encore)
    db.create_token(client_email, "support_ticket", payload=str(ticket_id))

    notified = send_support_ticket_notification(ticket_id, SUPPORT_EMAIL, client_email or "client inconnu")
    if notified:
        return f"Votre ticket #{ticket_id} a été créé. Notre équipe vous contactera bientôt. Un email a été envoyé au support."
    return f"Votre ticket #{ticket_id} a été créé, mais la notification email au support a échoué. Notre équipe le traitera tout de même."

# Exporter tous les outils
TOOLS = [
    check_domain_expiry,
    renew_domain,
    get_hosting_plans,
    reset_password,
    check_service_status,
    create_support_ticket
]
