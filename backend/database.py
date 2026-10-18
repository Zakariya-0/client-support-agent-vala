import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta
from config import DATABASE_PATH

TOKEN_TTL_HOURS = 24  # défaut général (password_reset)
TOKEN_TTL_BY_PURPOSE = {
    "domain_renewal": 24 * 7,  # 7 jours : fenêtre plus longue que le reset de mot de passe
}

def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

class ClientDB:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_db()

    def init_db(self):
        """Initialiser la base de données avec les tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table clients
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            plan TEXT NOT NULL,
            domains_count INTEGER,
            usage_percent INTEGER,
            expires_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Table conversations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            client_email TEXT NOT NULL,
            user_message TEXT,
            agent_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Table tickets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY,
            client_email TEXT,
            subject TEXT,
            description TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Table website_content (contenu scrapé du site vala.ma)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS website_content (
            id INTEGER PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            content TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Table secure_tokens (liens sécurisés à usage unique : reset password,
        # renouvellement de domaine, suivi de ticket — purpose+payload distinguent l'usage)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS secure_tokens (
            id INTEGER PRIMARY KEY,
            email TEXT,
            purpose TEXT NOT NULL,
            payload TEXT,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP,
            expires_at TIMESTAMP,
            used BOOLEAN DEFAULT FALSE
        )
        ''')

        conn.commit()
        conn.close()
        print("✅ Database initialized")

    def get_client(self, email):
        """Récupérer les infos d'un client"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, plan, domains_count, usage_percent, expires_date FROM clients WHERE email = ?", (email,))
        result = cursor.fetchone()
        conn.close()
        return result

    def save_conversation(self, client_email, user_msg, agent_response):
        """Sauvegarder une conversation"""
        from config import MAX_CONVERSATION_HISTORY

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO conversations (client_email, user_message, agent_response)
        VALUES (?, ?, ?)
        ''', (client_email, user_msg, agent_response))

        # Garder que les 5 derniers messages DE CE CLIENT
        # (client_email = ? est requis aussi sur le DELETE externe, sinon
        # ça supprime l'historique des AUTRES clients par erreur)
        cursor.execute('''
        DELETE FROM conversations WHERE client_email = ? AND id NOT IN (
            SELECT id FROM conversations WHERE client_email = ?
            ORDER BY id DESC LIMIT ?
        )
        ''', (client_email, client_email, MAX_CONVERSATION_HISTORY))

        conn.commit()
        conn.close()

    def get_conversation_history(self, client_email):
        """Récupérer l'historique des conversations"""
        from config import MAX_CONVERSATION_HISTORY

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT user_message, agent_response
        FROM conversations
        WHERE client_email = ?
        ORDER BY timestamp DESC LIMIT ?
        ''', (client_email, MAX_CONVERSATION_HISTORY))

        history = cursor.fetchall()
        conn.close()
        return history

    def create_token(self, email, purpose, payload=None, ttl_hours=None):
        """Génère un token opaque à usage unique. Seul son hash SHA-256 est stocké ;
        le token en clair n'est retourné qu'une fois, pour être mis dans le lien envoyé par email.
        La durée de validité dépend du purpose (TOKEN_TTL_BY_PURPOSE) sauf si explicitement fournie."""
        if ttl_hours is None:
            ttl_hours = TOKEN_TTL_BY_PURPOSE.get(purpose, TOKEN_TTL_HOURS)
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        now = datetime.now()
        expires_at = now + timedelta(hours=ttl_hours)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Purge légère : supprime les tokens expirés ou déjà utilisés à chaque création,
        # pour éviter que la table ne grossisse indéfiniment (pas de job planifié séparé)
        cursor.execute('''
        DELETE FROM secure_tokens WHERE used = 1 OR expires_at < ?
        ''', (now.strftime("%Y-%m-%d %H:%M:%S"),))

        cursor.execute('''
        INSERT INTO secure_tokens (email, purpose, payload, token_hash, created_at, expires_at, used)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (
            email, purpose, payload, token_hash,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()
        conn.close()
        return token

    def verify_token(self, token):
        """Vérifie un token : existe, pas expiré, pas déjà utilisé. Le marque comme utilisé
        et retourne {email, purpose, payload} si valide, sinon None."""
        token_hash = _hash_token(token)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT id, email, purpose, payload, expires_at, used FROM secure_tokens WHERE token_hash = ?
        ''', (token_hash,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        token_id, email, purpose, payload, expires_at, used = row
        if used or datetime.now() > datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S"):
            conn.close()
            return None

        cursor.execute("UPDATE secure_tokens SET used = 1 WHERE id = ?", (token_id,))
        conn.commit()
        conn.close()
        return {"email": email, "purpose": purpose, "payload": payload}

    def generate_reset_token(self, email):
        """Alias spécifique pour le cas password reset (nom demandé)."""
        return self.create_token(email, "password_reset")

    def verify_reset_token(self, token):
        """Alias spécifique : retourne l'email si le token est valide ET a le bon purpose, sinon None."""
        result = self.verify_token(token)
        if result and result["purpose"] == "password_reset":
            return result["email"]
        return None

    def generate_secure_token(self, email, domain=None, token_type='reset'):
        """Alias générique demandé : token_type='reset' ou 'renewal'. domain n'est utilisé
        (et stocké) que pour 'renewal'."""
        purpose = "domain_renewal" if token_type == "renewal" else "password_reset"
        return self.create_token(email, purpose, payload=domain)

    def verify_secure_token(self, token, token_type='reset'):
        """Alias générique demandé. Retourne l'email (reset) ou {'email','domain'} (renewal)
        si le token est valide et correspond au token_type attendu, sinon None."""
        result = self.verify_token(token)
        if not result:
            return None
        expected_purpose = "domain_renewal" if token_type == "renewal" else "password_reset"
        if result["purpose"] != expected_purpose:
            return None
        if token_type == "renewal":
            return {"email": result["email"], "domain": result["payload"]}
        return result["email"]

# Instance globale
db = ClientDB()
