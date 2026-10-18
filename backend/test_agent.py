#!/usr/bin/env python
"""
Suite de tests complète pour l'agent support Vala Bleu
Teste tous les 6 outils avec différents clients
"""

from main import executor
from conversation import ConversationManager
from tools import set_current_client_email

# Configuration des tests
# On vérifie l'outil réellement appelé (via intermediate_steps), pas des
# mots-clés dans la réponse finale : l'agent répond en français (voir le
# system prompt dans main.py), donc des mots-clés anglais ne s'y retrouveraient
# pas même quand l'outil est correctement invoqué.
test_cases = [
    {
        "name": "Tool #1 - Check Domain Expiry",
        "email": "contact@entrx.ma",
        "query": "Mon domaine expire quand ?",
        "expected_tool": "check_domain_expiry",
    },
    {
        "name": "Tool #2 - Renew Domain",
        "email": "founder@startup.ma",
        "query": "Je veux renouveler mon domaine",
        "expected_tool": "renew_domain",
    },
    {
        "name": "Tool #3 - Get Hosting Plans",
        "email": "info@agencez.ma",
        "query": "Listez-moi tous vos plans tarifaires avec les détails complets",
        "expected_tool": "get_hosting_plans",
    },
    {
        "name": "Tool #4 - Reset Password",
        "email": "admin@commercea.ma",
        "query": "J'ai oublié mon mot de passe",
        "expected_tool": "reset_password",
    },
    {
        "name": "Tool #5 - Check Service Status",
        "email": "hello@techcorp.ma",
        "query": "Vos serveurs fonctionnent ?",
        "expected_tool": "check_service_status",
    },
    {
        "name": "Tool #6 - Create Support Ticket",
        "email": "contact@entrx.ma",
        "query": "J'ai un problème, créez un ticket pour moi",
        "expected_tool": "create_support_ticket",
    },
]

def run_tests():
    """Exécuter tous les tests"""
    print("\n" + "=" * 80)
    print("🧪 SUITE DE TESTS - AGENT SUPPORT VALA BLEU")
    print("=" * 80 + "\n")

    conv_mgr = ConversationManager()
    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}/6] {test['name']}")
        print("-" * 80)
        print(f"Email: {test['email']}")
        print(f"Query: {test['query']}")
        print(f"Expected tool: {test['expected_tool']}")
        print()

        try:
            # Récupérer le contexte
            context = conv_mgr.get_context(test['email'])
            full_message = f"{context}\n\nClient message: {test['query']}"

            # Simule ce que api.py fait avant d'invoquer l'agent : sans ça, les tools
            # restreints (check_domain_expiry, renew_domain, reset_password) refusent
            # d'agir puisqu'ils ne font plus confiance qu'à cette valeur, jamais au LLM.
            set_current_client_email(test['email'])

            # Lancer l'agent
            result = executor.invoke({"input": full_message})
            response = result['output']

            # Sauvegarder la conversation
            conv_mgr.save_message(test['email'], test['query'], response)

            # Outils réellement appelés par l'agent pour cette requête
            called_tools = [
                action.tool for action, _ in result.get('intermediate_steps', [])
            ]

            print(f"Response: {response[:150]}...")
            print(f"Tools called: {called_tools or 'aucun'}\n")

            if test['expected_tool'] in called_tools:
                print(f"✅ PASSED - {test['expected_tool']} a été appelé")
                passed += 1
            else:
                print(f"❌ FAILED - {test['expected_tool']} n'a pas été appelé")
                failed += 1

        except Exception as e:
            print(f"❌ ERROR: {str(e)[:100]}")
            failed += 1

    # Rapport final
    print("\n" + "=" * 80)
    print("📊 RAPPORT FINAL")
    print("=" * 80)
    print(f"Total Tests: {len(test_cases)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Score: {passed}/{len(test_cases)} ({100*passed//len(test_cases)}%)")
    print("=" * 80 + "\n")

    if passed == len(test_cases):
        print("🎉 ALL TESTS PASSED! Agent is production-ready!\n")
    else:
        print(f"⚠️  {failed} test(s) failed. Review the results above.\n")

if __name__ == "__main__":
    run_tests()
