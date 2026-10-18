#!/usr/bin/env python
"""
Diagnostic SMTP pour l'envoi d'emails Gmail.

    python test_smtp.py          # teste réseau + connexion + login, n'envoie AUCUN email
    python test_smtp.py --send   # envoie en plus un email de test vers SUPPORT_EMAIL uniquement

Le mot de passe SMTP n'est jamais affiché.
"""

import socket
import sys
import time

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD, SMTP_TIMEOUT,
    SMTP_USE_SSL, SMTP_FALLBACK_SSL, SMTP_SSL_FALLBACK_PORT, SUPPORT_EMAIL,
)
from email_service import _connect_ipv4, _IPv4SMTP, _IPv4SMTP_SSL, _build_message, _send_via_smtp

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def step(label, fn):
    """Exécute une étape, affiche ✓/✗ avec la durée et le type d'erreur. Retourne True si OK."""
    start = time.time()
    try:
        detail = fn()
        suffix = f" — {detail}" if detail else ""
        print(f"    ✓ {label} ({time.time() - start:.1f}s){suffix}")
        return True
    except Exception as e:
        print(f"    ✗ {label} ({time.time() - start:.1f}s) — {type(e).__name__}: {e}")
        return False


def test_dns():
    print(f"\n[1] Résolution DNS de {SMTP_HOST}")

    def ipv4():
        addrs = sorted({i[4][0] for i in socket.getaddrinfo(SMTP_HOST, None, socket.AF_INET)})
        return ", ".join(addrs)

    def ipv6():
        addrs = sorted({i[4][0] for i in socket.getaddrinfo(SMTP_HOST, None, socket.AF_INET6)})
        return ", ".join(addrs) + " (non utilisé : le code force IPv4)"

    step("Adresses IPv4", ipv4)
    step("Adresses IPv6", ipv6)


def test_tcp():
    print("\n[2] Connexion TCP (IPv4)")
    results = {}
    for port in (587, 465):
        def connect(p=port):
            sock = _connect_ipv4(SMTP_HOST, p, 10)
            sock.close()
            return f"port {p} joignable"
        results[port] = step(f"TCP {SMTP_HOST}:{port} (timeout 10s)", connect)
    return results


def test_smtp(mode, port):
    print(f"\n[{'3' if mode == 'STARTTLS' else '4'}] SMTP {mode} sur le port {port} (timeout {SMTP_TIMEOUT}s)")
    holder = {}

    def connect():
        cls = _IPv4SMTP_SSL if mode == "SSL" else _IPv4SMTP
        holder["server"] = cls(SMTP_HOST, port, timeout=SMTP_TIMEOUT)
        return "bannière reçue"

    if not step("Connexion", connect):
        return False
    server = holder["server"]

    ok = True
    try:
        if mode == "STARTTLS":
            ok = step("EHLO", lambda: server.ehlo()[1].decode().splitlines()[0])
            ok = ok and step("STARTTLS", lambda: server.starttls()[1].decode())
            ok = ok and step("EHLO (après TLS)", lambda: server.ehlo()[1].decode().splitlines()[0])
        ok = ok and step(f"Login ({SMTP_EMAIL})", lambda: server.login(SMTP_EMAIL, SMTP_PASSWORD)[1].decode())
    finally:
        step("QUIT", lambda: server.quit()[1].decode())
    return ok


def test_send():
    print(f"\n[5] Envoi d'un email de test vers {SUPPORT_EMAIL}")
    if not SUPPORT_EMAIL:
        print("    ✗ SUPPORT_EMAIL est vide dans .env — rien envoyé")
        return False
    return step(
        "Envoi (chemin réel de l'application, avec repli éventuel)",
        lambda: _check(_send_via_smtp(
            SUPPORT_EMAIL,
            "Test SMTP Vala Support Agent",
            "Ceci est un email de test envoyé par test_smtp.py.",
        )),
    )


def _check(sent):
    if not sent:
        raise RuntimeError("l'envoi a échoué — voir le log d'erreur ci-dessus")
    return "email accepté par Gmail"


def main():
    send = "--send" in sys.argv
    print("=" * 70)
    print("DIAGNOSTIC SMTP — Vala Support Agent")
    print("=" * 70)
    print(f"Serveur      : {SMTP_HOST}")
    print(f"Port         : {SMTP_PORT} (SSL direct : {SMTP_USE_SSL}, repli SSL {SMTP_SSL_FALLBACK_PORT} : {SMTP_FALLBACK_SSL})")
    print(f"Timeout      : {SMTP_TIMEOUT}s")
    print(f"Compte       : {SMTP_EMAIL or '(vide)'}")
    print(f"Mot de passe : {'défini (' + str(len(SMTP_PASSWORD)) + ' caractères)' if SMTP_PASSWORD else '(VIDE)'}")
    print(f"Envoi réel   : {'OUI (--send)' if send else 'non (ajouter --send pour envoyer un test)'}")

    test_dns()
    tcp = test_tcp()
    ok_starttls = test_smtp("STARTTLS", 587) if tcp.get(587) else _skip("STARTTLS", 587)
    ok_ssl = test_smtp("SSL", 465) if tcp.get(465) else _skip("SSL", 465)
    if send:
        test_send()

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    if not tcp.get(587) and not tcp.get(465):
        print("Ni le port 587 ni le 465 ne sont joignables : le réseau (pare-feu, antivirus, FAI, Wi-Fi")
        print("d'entreprise ou d'école) bloque probablement le SMTP sortant. Essaie un autre réseau")
        print("(partage de connexion mobile) ou utilise EMAIL_SERVICE=mailtrap (HTTPS, port 443).")
    elif ok_starttls or ok_ssl:
        print("Connexion + authentification Gmail OK : l'envoi SMTP fonctionne.")
    else:
        print("Le réseau est joignable mais la connexion/le login échoue : vérifie SMTP_EMAIL et que")
        print("SMTP_PASSWORD est bien un mot de passe d'application Gmail (validation en 2 étapes requise).")


def _skip(mode, port):
    print(f"\n[{'3' if mode == 'STARTTLS' else '4'}] SMTP {mode} sur le port {port}")
    print("    – ignoré (port TCP injoignable)")
    return False


if __name__ == "__main__":
    main()
