# Vala Support Agent

Agent de support client pour Vala, hébergeur web basé à Agadir (Maroc). Un client écrit sa question dans une interface de chat, un modèle de langage exécuté en local choisit l'outil adapté (vérifier l'expiration d'un domaine, envoyer un lien de réinitialisation, ouvrir un ticket, etc.) et répond en français.

Le projet a été réalisé pendant un stage de deuxième année à l'ENSIAS. Il tourne entièrement en local : le modèle est servi par Ollama, la base est un simple fichier SQLite et les emails partent par SMTP depuis un compte Gmail.

## Fonctionnalités

Le client saisit son adresse email et pose sa question en langage naturel. L'agent identifie l'intention, appelle l'un des six outils et reformule le résultat en deux ou trois phrases. Les cinq derniers échanges de chaque client sont conservés et les deux plus récents sont réinjectés dans le contexte de la conversation suivante.

Trois outils envoient de vrais emails : la réinitialisation de mot de passe, le renouvellement de domaine et la création de ticket (notification à l'équipe support). Les liens contenus dans ces emails ne portent jamais l'adresse du client ni le nom de domaine, seulement un jeton aléatoire à usage unique. Les offres d'hébergement proposées par l'agent ne sont pas écrites en dur : elles proviennent de la page publique de vala.ma, récupérée par un script de scraping et stockée dans la base.

## Architecture

```
  Navigateur                   Backend FastAPI                    Services
 +-----------+                +--------------------+
 |  React    |  POST /chat    |  api.py            |  lecture    +----------+
 |  (port    | -------------> |  1. contexte du    | ----------> |  SQLite  |
 |  3000)    |                |     client         |  écriture   | clients  |
 |           | <------------- |  2. agent LangChain|             |   .db    |
 +-----------+    réponse     |     (main.py)      |             +----------+
                              |  3. outil appelé   |
                              |     (tools.py)     |  inférence  +----------+
                              |  4. sauvegarde de  | ----------> |  Ollama  |
                              |     l'échange      |             | qwen2.5  |
                              +--------------------+             |   :3b    |
                                        |                        +----------+
                                        |  envoi d'email
                                        v
                                  +------------+
                                  | SMTP Gmail |
                                  +------------+
```

Quand le client envoie un message, le frontend appelle `POST /chat` avec l'adresse email et le texte. Le backend lit en base les informations du client et ses derniers échanges, les place devant le message et transmet le tout à l'agent. Le modèle décide s'il doit appeler un outil. L'outil s'exécute en Python (lecture ou écriture SQLite, envoi d'email), son résultat revient au modèle, qui rédige la réponse finale. L'échange est ensuite enregistré et la réponse renvoyée au navigateur.

L'adresse du client est fixée côté serveur avant l'appel à l'agent. Les outils qui agissent sur un compte (mot de passe, domaine, ticket) utilisent cette valeur et non celle que le modèle pourrait extraire du texte.

## Structure du projet

```
vala-support-agent/
├── docker-compose.yml        Trois services : ollama, backend, frontend
├── .dockerignore
├── backend/
│   ├── api.py                Application FastAPI : /chat, /health, /status
│   ├── main.py               Assemblage de l'agent : modèle, prompt, outils
│   ├── tools.py              Les six outils de l'agent
│   ├── conversation.py       Construction du contexte (client + historique)
│   ├── database.py           Accès SQLite, tables, jetons sécurisés
│   ├── email_service.py      Envoi d'emails (Gmail SMTP, Mailtrap, mode dev)
│   ├── scrape_vala_website.py  Récupération des offres sur vala.ma
│   ├── create_db.py          Création de 100 clients fictifs
│   ├── config.py             Lecture des variables d'environnement
│   ├── test_agent.py         Test des six outils
│   ├── test_smtp.py          Diagnostic de la connexion SMTP
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example          Modèle de configuration (sans valeurs réelles)
└── frontend/
    ├── src/
    │   ├── App.js            Interface de chat
    │   ├── App.css           Styles
    │   └── index.js
    ├── public/
    ├── package.json
    └── Dockerfile            Build React puis service par nginx
```

## Prérequis

Pour lancer le projet avec Docker, il faut Docker Desktop avec Docker Compose v2. Le modèle `qwen2.5:3b` occupe environ 2 Go et le build du frontend est gourmand : prévoir 8 Go de mémoire vive au minimum, et vérifier que Docker Desktop n'est pas limité à moins de 4 Go.

Pour le lancement sans Docker, il faut Python 3.12, Node.js 18 ou plus récent, et Ollama installé sur la machine.

Pour envoyer de vrais emails avec Gmail, il faut un mot de passe d'application, qui suppose la validation en deux étapes sur le compte. Sans cela, le mode `EMAIL_MODE=dev` affiche les emails dans le terminal au lieu de les envoyer, ce qui suffit pour tester.

## Installation et lancement avec Docker

Copier le modèle de configuration et le remplir (voir la section Configuration) :

```bash
cp backend/.env.example backend/.env
```

Le fichier `backend/clients.db` est monté dans le conteneur. Il n'est pas versionné, donc sur une copie neuve du dépôt il faut le créer vide avant le premier lancement, sinon Docker crée un dossier à sa place et SQLite ne peut pas l'ouvrir :

```bash
touch backend/clients.db
```

Sous PowerShell, la commande équivalente est `New-Item backend/clients.db -ItemType File`.

Construire et démarrer les trois services :

```bash
docker compose up --build -d
```

Télécharger le modèle dans le conteneur Ollama (environ 2 Go, à faire une seule fois, le volume `ollama_data` le conserve) :

```bash
docker compose exec ollama ollama pull qwen2.5:3b
```

Remplir la base avec les clients fictifs et les offres d'hébergement :

```bash
docker compose exec backend python create_db.py
docker compose exec backend python scrape_vala_website.py
```

L'interface est alors disponible sur http://localhost:3000 et l'API sur http://localhost:8000. Si Ollama tourne déjà sur la machine, le port 11434 est occupé et le service `ollama` ne démarre pas : arrêter l'Ollama local ou changer le mapping de port dans `docker-compose.yml`. L'adresse de l'API utilisée par le frontend est fixée au moment du build (`REACT_APP_API_URL`) ; après l'avoir modifiée, relancer `docker compose build frontend`.

## Lancement sans Docker

Trois terminaux sont nécessaires. Dans le premier, démarrer Ollama et télécharger le modèle la première fois :

```bash
ollama pull qwen2.5:3b
ollama serve
```

Dans le deuxième, préparer et lancer le backend (sous Windows, activer l'environnement avec `venv\Scripts\activate` à la place de la commande `source`) :

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python create_db.py
python scrape_vala_website.py
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Dans le troisième, lancer le frontend :

```bash
cd frontend
npm install
npm start
```

Attention, `create_db.py` vide la table `clients` avant de la remplir : ne pas le relancer sur une base dont on veut garder les clients.

## Configuration (.env)

Toutes les variables se règlent dans `backend/.env`, copié depuis `backend/.env.example`. Ce fichier contient des secrets et n'est jamais versionné. Les valeurs ci-dessous sont des exemples.

| Variable | Exemple | Rôle |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Adresse d'Ollama. Avec Docker Compose, elle est remplacée par `http://ollama:11434`. |
| `LLM_MODEL` | `qwen2.5:3b` | Modèle utilisé. La valeur par défaut du code est `phi` : toujours la définir. |
| `LLM_TEMPERATURE` | `0.3` | Température du modèle. |
| `MAX_TOKENS_OUTPUT` | `200` | Longueur maximale d'une réponse. |
| `MAX_CONVERSATION_HISTORY` | `5` | Nombre d'échanges conservés par client. |
| `DATABASE_PATH` | `clients.db` | Chemin du fichier SQLite. Avec Docker Compose : `/app/clients.db`. |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Seule origine autorisée par CORS. |
| `API_HOST`, `API_PORT` | `0.0.0.0`, `8000` | Définies dans `config.py` mais non utilisées : l'adresse et le port se règlent dans la commande `uvicorn`. |
| `EMAIL_MODE` | `dev` | `dev` affiche les emails dans le terminal sans les envoyer, `production` les envoie. |
| `EMAIL_SERVICE` | `gmail` | `gmail` (SMTP) ou `mailtrap` (API HTTP). |
| `SMTP_HOST`, `SMTP_PORT` | `smtp.gmail.com`, `587` | Serveur SMTP. |
| `SMTP_USE_SSL` | `false` | `true` pour SSL direct (mettre alors `SMTP_PORT=465`). |
| `SMTP_FALLBACK_SSL` | `true` | Si STARTTLS échoue, réessaie en SSL sur le port 465. |
| `SMTP_TIMEOUT` | `30` | Délai maximal en secondes pour chaque étape SMTP. |
| `SMTP_EMAIL` | `your-email@example.com` | Adresse expéditrice. |
| `SMTP_PASSWORD` | `your-app-password` | Mot de passe d'application Gmail, pas le mot de passe du compte. |
| `MAILTRAP_API_TOKEN` | `your-mailtrap-token` | Uniquement si `EMAIL_SERVICE=mailtrap`. |
| `SUPPORT_EMAIL` | `support@example.com` | Destinataire des notifications de ticket. |
| `RESET_URL`, `RENEWAL_URL` | `https://vala.ma/reset`, `https://vala.ma/renew` | Adresses de base des liens envoyés par email. Le jeton y est ajouté en paramètre. |
| `DEMO_CLIENT_EMAIL` | `demo@example.com` | Adresse du client de démonstration créé par `create_db.py`. |

Si `docker compose` démarre mais que l'envoi d'email échoue avec un service inconnu, vérifier les fins de ligne du fichier `.env` : un fichier au format Windows (CRLF) peut se convertir avec `sed -i 's/\r$//' backend/.env`.

## Outils de l'agent

| Outil | Rôle | Exemple de question |
|---|---|---|
| `check_domain_expiry` | Donne la date d'expiration d'un domaine du client connecté. | « Mon domaine expire quand ? » |
| `renew_domain` | Envoie par email un lien de renouvellement valable 7 jours. Ne renouvelle pas le domaine lui-même. | « Je veux renouveler mon domaine. » |
| `reset_password` | Envoie par email un lien de réinitialisation valable 24 heures. | « J'ai oublié mon mot de passe. » |
| `create_support_ticket` | Enregistre un ticket en base et prévient l'équipe support par email. | « J'ai un problème, créez un ticket pour moi. » |
| `check_service_status` | Renvoie l'état des services. Le texte est fixe, il ne reflète pas l'état réel des serveurs. | « Vos serveurs fonctionnent ? » |
| `get_hosting_plans` | Liste les quatre offres (Essential, Pro, Expert, Premium) lues dans la base. | « Quels sont vos plans d'hébergement ? » |

Les jetons sont générés avec `secrets.token_urlsafe(32)`. Seul leur hash SHA-256 est stocké, chaque jeton ne peut servir qu'une fois, et les jetons expirés ou utilisés sont supprimés à chaque nouvelle création. Le lien envoyé pointe vers vala.ma : la vérification du jeton existe dans `database.py` (`verify_token`), mais aucune route de ce projet ne l'appelle.

## API

`POST /chat` reçoit l'adresse du client et son message, et renvoie la réponse de l'agent. La route est limitée à 10 requêtes par minute et par adresse IP.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"client_email": "demo@example.com", "message": "Quels sont vos plans ?"}'
```

```json
{
  "status": "success",
  "response": "Voici nos plans d'hébergement : Essential, Pro, Expert et Premium. ...",
  "timestamp": "2026-10-19T14:32:08.412905"
}
```

La formulation de la réponse varie d'un appel à l'autre. En cas d'erreur interne, l'API renvoie un code 500 avec un message générique (le détail est écrit dans les logs du serveur), et un code 429 si la limite de débit est dépassée.

`GET /health` indique que l'API répond. Il renvoie un objet JSON avec un champ `status` (texte indiquant que le service est en ligne) et un champ `model` (nom du modèle, `qwen2.5:3b`) :

```bash
curl http://localhost:8000/health
```

Une troisième route, `GET /status/{client_email}`, renvoie le nom, l'offre, le nombre de domaines, le taux d'utilisation et la date d'expiration d'un client, ou un code 404 s'il n'existe pas.

## Tests

```bash
cd backend
python test_agent.py
```

Le script pose une question par outil et vérifie que le bon outil a été appelé, en lisant les étapes intermédiaires de l'agent plutôt que le texte de la réponse. Ollama doit être lancé. Avec `EMAIL_MODE=production`, les tests de réinitialisation, de renouvellement et de création de ticket envoient réellement un email : passer en `dev` pour éviter cela.

Pour diagnostiquer un problème d'envoi d'email, `python test_smtp.py` teste la résolution DNS, la connexion sur les ports 587 et 465 et l'authentification, sans rien envoyer. L'option `--send` envoie un message de test à `SUPPORT_EMAIL`.

## Limites connues

Le modèle de 3 milliards de paramètres se trompe parfois : il peut choisir le mauvais outil, ne pas en appeler du tout ou mal remplir un argument, par exemple le nom de domaine. Le prompt système associe donc explicitement chaque type de demande à un outil, ce qui améliore le résultat sans le garantir. Sur un portable avec 8 Go de mémoire, une réponse prend de 40 à 70 secondes.

L'identité du client n'est pas vérifiée : l'adresse saisie dans l'interface est acceptée telle quelle, sans authentification. Le projet n'est donc pas conçu pour être exposé sur Internet en l'état. L'adresse du client courant est conservée dans une variable de module, ce qui ne convient pas à des requêtes simultanées. Le lien entre un domaine et un client repose sur la présence du domaine dans l'adresse email, faute de table de domaines.

L'envoi d'emails dépend du réseau. Un pare-feu qui bloque le SMTP sortant ou coupe les connexions longues fait échouer l'envoi ; l'agent répond alors normalement mais l'email n'est pas parti. SQLite convient pour une démonstration avec un seul processus et ne convient pas à une utilisation en production.

## Pistes d'amélioration

La première étape serait d'ajouter une vraie authentification et une route qui valide les jetons, pour que les liens envoyés par email aboutissent sur une page du projet. Viendraient ensuite une table de domaines rattachés à des clients, le passage à PostgreSQL, l'appel de l'agent dans un thread séparé pour ne pas bloquer le serveur, et un modèle plus grand si le matériel le permet. Le scraping des offres pourrait être planifié au lieu d'être lancé à la main, et les tests complétés par une suite automatique qui ne dépend pas d'un modèle de langage.

## Auteur

Zakariya Sahid, ENSIAS.

## Licence

TODO : à compléter.
