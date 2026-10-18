from database import db
from config import MAX_CONVERSATION_HISTORY

class ConversationManager:
    def save_message(self, client_email: str, user_msg: str, agent_response: str):
        """Sauvegarder un message dans la conversation"""
        db.save_conversation(client_email, user_msg, agent_response)

    def get_context(self, client_email: str) -> str:
        """Récupérer le contexte du client (infos + historique)"""
        client_info = db.get_client(client_email)
        history = db.get_conversation_history(client_email)

        if not client_info:
            return f"Client email: {client_email} (Nouveau client)"

        name, plan, domains, usage, expires = client_info
        context = f"""Client: {name} ({client_email})
Plan: {plan} | Domaines: {domains} | Usage: {usage}% | Expire: {expires}"""

        if history:
            context += "\nRecent: "
            # history est trié du plus récent au plus ancien (ORDER BY timestamp DESC)
            for user_msg, agent_resp in history[:2]:
                context += f"\n  Q: {user_msg[:50]}..."

        return context

conv_manager = ConversationManager()
