from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tools import TOOLS
from config import OLLAMA_BASE_URL, LLM_MODEL, LLM_TEMPERATURE, MAX_TOKENS_OUTPUT

# Initialiser le LLM Phi (chat model requis pour le tool calling)
llm = ChatOllama(
    model=LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=LLM_TEMPERATURE,
    num_predict=MAX_TOKENS_OUTPUT,
)

# Système prompt pour l'agent
system_prompt = """Tu es un agent support client pour Vala Bleu (hébergement web & domaines).

Règles IMPORTANTES:
1. Réponds TOUJOURS en français
2. Sois bref et utile (max 2-3 phrases)
3. Tu DOIS appeler l'outil correspondant dès que la demande du client correspond à l'un des cas ci-dessous. Ne réponds jamais de mémoire à sa place.
4. Si aucun outil ne correspond et que tu ne peux pas aider, appelle create_support_ticket

Quel outil appeler selon l'intention du client :
- "mon domaine expire quand", "date d'expiration" → check_domain_expiry
- "renouveler mon domaine", "renouvellement" → renew_domain
- "vos plans", "tarifs", "prix", "offres" → get_hosting_plans
- "mot de passe oublié", "réinitialiser mon mot de passe" → reset_password
- "vos serveurs fonctionnent", "panne", "statut des services" → check_service_status
- tout problème que les outils ci-dessus ne résolvent pas → create_support_ticket
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Créer l'agent
agent = create_tool_calling_agent(llm, TOOLS, prompt)

# Créer l'executor
executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    verbose=False,
    handle_parsing_errors=True,
    max_iterations=5,
    return_intermediate_steps=True,
)

# Test simple
if __name__ == "__main__":
    from tools import set_current_client_email

    print("🤖 Support Agent Ready\n")

    # check_domain_expiry / renew_domain / reset_password ne font confiance qu'à cette
    # valeur (jamais à un email deviné par le LLM) — il faut la fixer avant d'invoquer.
    set_current_client_email("contact@entrx.ma")

    queries = [
        "Mon domaine entrx.ma expire quand ?",
        "J'ai oublié mon mot de passe",
        "Quels sont vos plans ?",
    ]

    for q in queries:
        print(f"Q: {q}")
        result = executor.invoke({"input": q})
        print(f"A: {result['output']}\n")
