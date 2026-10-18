import logging
import smtplib
import socket
from email.mime.text import MIMEText
import requests
from config import (
    EMAIL_SERVICE, EMAIL_MODE,
    MAILTRAP_API_TOKEN,
    SMTP_HOST, SMTP_PORT, SMTP_PASSWORD,
    SMTP_EMAIL, SMTP_TIMEOUT, SMTP_USE_SSL, SMTP_FALLBACK_SSL, SMTP_SSL_FALLBACK_PORT,
)

logger = logging.getLogger(__name__)

MAILTRAP_ENDPOINT = "https://send.mailtrap.io/api/send"
SENDER_NAME = "Support Vala"
SIGNATURE = "\n\nCordialement,\nL'équipe support Vala\nSolution Hébergement Web"


def _send_dev(to: str, subject: str, body: str) -> bool:
    """Mode dev : n'envoie rien, affiche l'email dans le terminal."""
    print("\n----- 📧 EMAIL (mode dev, non envoyé) -----")
    print(f"À     : {to}")
    print(f"Sujet : {subject}")
    print(f"Corps :\n{body}")
    print("--------------------------------------------\n")
    logger.info(f"[dev] Email simulé vers {to} — sujet : {subject}")
    return True


def _send_via_mailtrap(to: str, subject: str, body: str) -> bool:
    try:
        response = requests.post(
            MAILTRAP_ENDPOINT,
            headers={
                "Authorization": f"Bearer {MAILTRAP_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "from": {"email": SMTP_EMAIL, "name": SENDER_NAME},
                "to": [{"email": to}],
                "subject": subject,
                "text": body,
                "category": "vala-support",
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Email envoyé (Mailtrap) à {to} — sujet : {subject}")
        return True
    except requests.RequestException as e:
        logger.error(f"Échec de l'envoi Mailtrap à {to} : {e}")
        return False


def _connect_ipv4(host: str, port: int, timeout: float) -> socket.socket:
    """Connexion TCP en IPv4 uniquement. Par défaut smtplib essaie aussi les adresses IPv6,
    et sur un réseau sans IPv6 fonctionnel chaque tentative consomme tout le timeout."""
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    last_error = None
    for family, socktype, proto, _canon, addr in infos:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(addr)
            return sock
        except OSError as e:
            sock.close()
            last_error = e
    raise last_error or OSError(f"Aucune adresse IPv4 trouvée pour {host}")


class _IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _connect_ipv4(host, port, timeout)


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        sock = _connect_ipv4(host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=self._host)


def _build_message(to: str, subject: str, body: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    return msg


def _smtp_send(mode: str, port: int, msg: MIMEText) -> None:
    """Un envoi SMTP complet : connexion → (starttls) → login → envoi. Lève une exception en cas d'échec.
    mode = "STARTTLS" (port 587) ou "SSL" (port 465)."""
    if mode == "SSL":
        server = _IPv4SMTP_SSL(SMTP_HOST, port, timeout=SMTP_TIMEOUT)
    else:
        server = _IPv4SMTP(SMTP_HOST, port, timeout=SMTP_TIMEOUT)

    with server:
        if mode == "STARTTLS":
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)


def _send_via_smtp(to: str, subject: str, body: str) -> bool:
    """Envoie via Gmail SMTP. Ne lève jamais : retourne False et logue l'erreur (type + message,
    jamais le mot de passe) pour que l'agent puisse répondre même si l'email échoue."""
    msg = _build_message(to, subject, body)

    if SMTP_USE_SSL:
        attempts = [("SSL", SMTP_PORT)]
    else:
        attempts = [("STARTTLS", SMTP_PORT)]
        if SMTP_FALLBACK_SSL:
            attempts.append(("SSL", SMTP_SSL_FALLBACK_PORT))

    for mode, port in attempts:
        try:
            _smtp_send(mode, port, msg)
            logger.info(f"Email envoyé (SMTP/Gmail, {mode} port {port}) à {to} — sujet : {subject}")
            return True
        except Exception as e:
            logger.error(
                f"Échec de l'envoi SMTP ({mode}, {SMTP_HOST}:{port}, timeout {SMTP_TIMEOUT}s) "
                f"à {to} : {type(e).__name__}: {e}"
            )

    return False


def send_email(to: str, subject: str, body: str) -> bool:
    """Point d'entrée unique : route vers dev / gmail / mailtrap selon la config.
    Ne lève jamais d'exception : un échec d'email ne doit pas faire planter /chat."""
    try:
        if EMAIL_MODE == "dev":
            return _send_dev(to, subject, body)
        if EMAIL_SERVICE == "gmail":
            return _send_via_smtp(to, subject, body)
        if EMAIL_SERVICE == "mailtrap":
            return _send_via_mailtrap(to, subject, body)
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi à {to} : {type(e).__name__}: {e}")
        return False

    logger.error(f"EMAIL_SERVICE inconnu : {EMAIL_SERVICE!r} (attendu 'gmail' ou 'mailtrap')")
    return False


def send_reset_password_link(email: str, reset_url: str, token: str) -> bool:
    """Envoie le lien de réinitialisation de mot de passe. Le lien ne contient qu'un
    token opaque — jamais l'email en clair (évite qu'il fuite via logs, historique, referrer)."""
    subject = "Réinitialisation de votre mot de passe Vala"
    body = (
        f"Réinitialiser votre mot de passe\n"
        f"Cliquez ici: {reset_url}?token={token}\n"
        f"Valide 24 heures."
        f"{SIGNATURE}"
    )
    return send_email(email, subject, body)


def send_renewal_link(email: str, domain: str, renewal_url: str, token: str) -> bool:
    """Envoie le lien de renouvellement d'un domaine. Même principe : seul le token
    figure dans le lien, le domaine est résolu côté serveur via verify_token()."""
    subject = f"Renouvelez votre domaine {domain}"
    body = (
        f"Renouvellement de domaine: {domain}\n"
        f"Cliquez ici: {renewal_url}?token={token}\n"
        f"Valide 7 jours."
        f"{SIGNATURE}"
    )
    return send_email(email, subject, body)


def send_support_ticket_notification(ticket_id, support_email: str, client_email: str) -> bool:
    """Notifie l'équipe support (support_email) qu'un nouveau ticket a été ouvert par client_email."""
    subject = f"Nouveau ticket support #{ticket_id}"
    body = (
        f"Ticket #{ticket_id} créé par {client_email}. Nous contacterons bientôt."
        f"{SIGNATURE}"
    )
    return send_email(support_email, subject, body)
