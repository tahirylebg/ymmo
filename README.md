# Ymmo

Plateforme immobilière centralisée et architecture réseau multi-sites pour le groupe Ymmo :
un siège à Aix-en-Provence et 12 agences.
Projet fil rouge du Bachelor 2 Ynov Informatique, UF INFRA & DEV.

- **DEV** : un site d'achat et de vente pour les clients et les agents, avec analyse du marché et estimation des prix par apprentissage automatique.
- **INFRA** : le réseau des 13 sites (VLAN, VPN IPSec), l'annuaire Active Directory et les droits d'accès, la sécurité, les sauvegardes, la supervision et l'extension cloud Azure.

## Fonctionnalités

| Espace | Ce qu'on y fait |
|---|---|
| **Public** | Rechercher des biens (résidentiels et professionnels) avec filtres et tris, consulter une fiche, découvrir les agences |
| **Client** | Favoris, demandes de visite, offres d'achat, estimation de son bien avec un prix immédiat, suivi dans « Mon espace » |
| **Back-office** (agent, responsable d'agence, direction) | Publier et gérer les biens, traiter visites, offres et demandes d'estimation, conclure les ventes ; chacun dans son périmètre |
| **Analyses** | Prix au m² par ville, biens populaires, durées de vente, performance des agences, prévision des ventes sur 12 mois, score des zones où investir, exports CSV et PDF |

Détail dans les [spécifications fonctionnelles](docs/dev/specifications-fonctionnelles.md).

## Pile technique

Python 3.12 · FastAPI · Jinja2 · SQLAlchemy 2 + Alembic · PostgreSQL 16 ·
pandas, scikit-learn, matplotlib · Docker Compose · pytest, ruff, black · GitHub Actions.

Architecture en couches (routes → services → dépôts → modèles), expliquée dans la
[documentation technique](docs/dev/documentation-technique.md).

## Démarrage rapide

Prérequis : Docker Desktop (ou Docker Engine avec le plugin Compose).

```bash
git clone https://github.com/tahirylebg/ymmo.git
cd ymmo
cp .env.example .env          # facultatif en local : les valeurs par défaut suffisent
docker compose up -d --build
```

Au premier démarrage, le conteneur applique les migrations, charge un jeu de
démonstration (13 agences, 2 400 biens dont 2 000 vendus sur 3 ans, environ 250 comptes)
et entraîne le modèle de prix. Comptez une à deux minutes, puis ouvrez :

| Adresse | Contenu |
|---|---|
| http://localhost:8000 | Site |
| http://localhost:8000/docs | Documentation interactive de l'API (OpenAPI) |
| http://localhost:8000/api/health/db | Contrôle de santé |

### Comptes de démonstration

Mot de passe commun : `Ymmo-Demo-2026`

| Compte | Rôle | À essayer |
|---|---|---|
| `client@ymmo.fr` | Client | Mon espace : favoris, visites, offres, estimations déjà remplis |
| `agent@ymmo.fr` | Agent (siège) | Back-office : ses biens, visites et offres à traiter |
| `manager@ymmo.fr` | Responsable d'agence (siège) | Tous les biens de l'agence |
| `admin@ymmo.fr` | Direction | Tout le réseau, analyses, réentraînement du modèle |

Ces comptes et ce mot de passe n'existent que dans les données de démonstration : en
production, `SEED_ON_STARTUP=false`.

## Développement

```bash
docker compose logs -f app                        # journaux
docker compose exec app pytest                    # tests
docker compose exec app alembic upgrade head      # migrations (déjà faites au démarrage)
docker compose down -v                            # tout arrêter et repartir d'une base vide
```

Sans Docker, avec une base PostgreSQL locale :

```bash
python -m venv .venv && . .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head && python -m scripts.seed && python -m analytics.train
uvicorn app.main:app --reload
ruff check . && black --check . && pytest
```

## Structure du dépôt

```
app/            application web : routes API (routers), pages (web), services, dépôts, modèles, gabarits
analytics/      nettoyage des données, statistiques, modèles prédictifs, graphiques, rapport PDF
alembic/        migrations du schéma et des vues SQL
scripts/        démarrage du conteneur, jeu de démonstration
tests/          tests automatisés (pytest)
infra/scripts/  scripts PowerShell (annuaire, droits, partages) et de sauvegarde
docs/dev/       spécifications fonctionnelles, documentation technique
docs/infra/     livrables INFRA (adressage, schéma réseau, sécurité, serveurs, sauvegarde, cloud, budget)
```

## Documentation

| Partie | Documents |
|---|---|
| DEV | [Spécifications fonctionnelles](docs/dev/specifications-fonctionnelles.md) · [Documentation technique](docs/dev/documentation-technique.md) |
| INFRA | [Sommaire des livrables INFRA](docs/infra/README.md) |
| Projet | [Gestion de projet](docs/gestion-projet.md) (backlog, Git, journal) · [Crédits des photos](docs/photos-libres.md) |

## Déploiement en production

- **Au siège** : serveur Debian en DMZ, avec Docker et un proxy inverse HTTPS. Voir le [guide de configuration des serveurs](docs/infra/04-guide-configuration-serveurs.md), § 6.
- **Dans le cloud** : Azure App Service et PostgreSQL managé. Voir la [solution cloud](docs/infra/06-solution-cloud-azure.md).

En production, il faut :

- `APP_ENV=production` et `APP_DEBUG=false` ;
- une `SECRET_KEY` aléatoire (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) ;
- un mot de passe PostgreSQL fort ;
- `SEED_ON_STARTUP=false`.

## Méthode de travail

- **Branches** : Git-flow simplifié. `main` porte les versions livrables, `develop` sert à l'intégration, et une branche `feature/…`, `docs/…` ou `fix/…` est créée par sujet.
- **Fusions** : vers `develop` en `--no-ff`, par pull request.
- **Commits** : messages au format Conventional Commits.
- **CI** : lint, format et tests à chaque push.

Détails dans la [gestion de projet](docs/gestion-projet.md).
