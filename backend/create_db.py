import os
import sqlite3
import random
from datetime import datetime, timedelta
from database import db  # déclenche la création des tables (clients, conversations, tickets)

FIRST_NAMES_M = [
    "Mohamed", "Youssef", "Ahmed", "Hamza", "Karim", "Omar", "Rachid", "Said",
    "Khalid", "Anas", "Mehdi", "Yassine", "Amine", "Reda", "Bilal", "Adil",
    "Ayoub", "Soufiane", "Zakaria", "Tarik", "Nabil", "Hicham", "Younes",
    "Ismail", "Abdelkarim", "Aziz", "Fouad", "Driss", "Idir", "Massin",
]
FIRST_NAMES_F = [
    "Fatima", "Amina", "Khadija", "Salma", "Zineb", "Meryem", "Nadia", "Samira",
    "Latifa", "Hasna", "Imane", "Sara", "Loubna", "Naima", "Karima", "Widad",
    "Ghita", "Hind", "Malika", "Rajae", "Souad", "Btissam", "Ilham", "Asmaa",
    "Yasmine", "Kenza", "Assia", "Tiziri", "Nawal",
]
LAST_NAMES = [
    "El Jaouhari", "Bennani", "Alaoui", "Idrissi", "El Fassi", "Tazi", "Benjelloun",
    "Chraibi", "El Amrani", "Bencherki", "Berrada", "El Khattabi", "Ouazzani",
    "Sqalli", "El Malki", "Benkirane", "Cherkaoui", "El Yacoubi", "Bouzid",
    "Naciri", "Zaki", "Slaoui", "El Ghazali", "Bakkali", "Rifi", "Guennoun",
    "Skalli", "Bouazza", "Haddou", "Ait Ali", "Ait Ouali", "Boulahcen", "Assou",
]
COMPANY_WORDS = [
    "technomaroc", "digitalcasa", "atlashost", "medinaweb", "saharatech",
    "casadigital", "rabatsoft", "marrakechweb", "oceanhost", "atlascloud",
    "fesdigital", "tangertech", "agadirweb", "innovma", "webmaroc", "hostatlas",
]

def random_name():
    first = random.choice(FIRST_NAMES_M if random.random() < 0.5 else FIRST_NAMES_F)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"

def random_email(name, used_emails):
    tokens = name.lower().replace("-", " ").split(" ")
    first, last = tokens[0], "".join(tokens[1:])
    roll = random.random()
    if roll < 0.35:
        local, domain = f"{first}.{last}", "gmail.com"
    elif roll < 0.55:
        local, domain = f"{first}{last[:1]}", "hotmail.com"
    elif roll < 0.70:
        local, domain = first, "outlook.com"
    else:
        company = random.choice(COMPANY_WORDS)
        local, domain = random.choice(["contact", "info", "admin", first]), f"{company}.ma"

    email = f"{local}@{domain}"
    while email in used_emails:
        email = f"{local}{random.randint(1, 999)}@{domain}"
    used_emails.add(email)
    return email

def random_expiry():
    start, end = datetime(2026, 1, 1), datetime(2027, 12, 31)
    return (start + timedelta(days=random.randint(0, (end - start).days))).strftime("%Y-%m-%d")

def random_created_at():
    return (datetime.now() - timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d %H:%M:%S")

def build_clients():
    # 40% basic, 35% pro, 25% premium sur 100 clients
    plans = ["basic"] * 40 + ["pro"] * 35 + ["premium"] * 25
    random.shuffle(plans)

    used_emails = set()
    clients = []

    # Client fixe demandé explicitement
    fixed_email = os.getenv("DEMO_CLIENT_EMAIL", "demo@example.com")
    clients.append(("Zakariya Sahid", fixed_email, "pro", 5, 65, "2026-12-31", random_created_at()))
    used_emails.add(fixed_email)
    plans.remove("pro")  # déjà comptabilisé dans les 35% pro

    for plan in plans:
        name = random_name()
        email = random_email(name, used_emails)
        clients.append((
            name, email, plan,
            random.randint(1, 20),   # domains_count
            random.randint(10, 95),  # usage_percent
            random_expiry(),
            random_created_at(),
        ))

    return clients

clients_data = build_clients()

conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()

# Repart d'une base propre pour garantir exactement 100 lignes au COUNT(*)
cursor.execute("DELETE FROM clients")

inserted = 0
for name, email, plan, domains, usage, expires, created_at in clients_data:
    try:
        cursor.execute('''
        INSERT INTO clients (name, email, plan, domains_count, usage_percent, expires_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, plan, domains, usage, expires, created_at))
        inserted += 1
    except sqlite3.IntegrityError:
        pass

conn.commit()
print(f"✅ {inserted} clients inserted")
conn.close()
