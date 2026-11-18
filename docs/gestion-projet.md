# Gestion de projet — Ymmo

Ce document sert de backlog et de journal de suivi. Il est la source de vérité du
tableau Kanban (Trello / GitHub Projects) : une carte par ligne de backlog, colonnes
**À faire → En cours → En revue → Terminé**.

## 1. Organisation

| Élément | Choix |
|---|---|
| Méthode | Itérations courtes par phase (mini-sprints), une branche Git par phase |
| Outil de suivi | Tableau Kanban (Trello ou GitHub Projects) synchronisé avec ce fichier |
| Définition de « terminé » | Code relu, tests verts (`pytest`), lint OK (`ruff`, `black`), doc mise à jour, branche mergée dans `develop` |
| Rituels | Point d'avancement à chaque fin de phase (résumé + reste à faire) |

## 2. Stratégie Git

```
main      ●───────────────────────────────●  (versions livrables, via Pull Request uniquement)
           \                             /
develop     ●──●─────●──────●──────●────●     (intégration)
                \   /  \   /  \   /
feature/*        ●─●    ●─●    ●─●             (une fonctionnalité = une branche)
```

- `main` : protégée par convention, ne reçoit que des merges de `develop` via Pull Request.
- `develop` : branche d'intégration, reçoit les branches de travail en `merge --no-ff`
  (l'historique garde la trace de chaque fonctionnalité).
- Branches de travail : `feature/...` (code), `docs/...` (documentation),
  `infra/...` (scripts INFRA), `chore/...` (outillage), `fix/...` (corrections).
- Messages au format **Conventional Commits** : `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`, `ci:`.
- Intégration continue : GitHub Actions (`.github/workflows/ci.yml`) lance ruff, black
  et pytest sur chaque push et Pull Request.

## 3. Backlog par phase

| # | Phase | Branche | Livrables | Critère de la grille | Statut |
|---|---|---|---|---|---|
| 0 | Setup | `chore/setup` | Dépôt, Docker Compose, squelette FastAPI, CI, `.env.example` | Git (×3), Posture (×3) | ✅ Terminé |
| 1 | Base de données | `feature/database` | Modèles ORM, migrations Alembic, vues SQL, index | Modéliser BDD (×3), Interroger BDD (×4) | ✅ Terminé |
| 2 | Authentification | `feature/auth` | Inscription, connexion, JWT, rôles | Application fonctionnelle (×10) | ✅ Terminé |
| 3 | Biens | `feature/properties` | CRUD agent, recherche, filtres, pagination, fiche | Application fonctionnelle (×10) | ✅ Terminé |
| 4 | Espace client | `feature/client-space` | Favoris, visites, dépôt de bien, suivi | Application fonctionnelle (×10) | ✅ Terminé |
| 5 | Espace agent | `feature/agent-space` | Dashboard, visites, offres, transactions | Application fonctionnelle (×10) | ✅ Terminé |
| 6 | Front | `feature/frontend` | Pages responsives, accessibles, performantes | Interfaces (×5 + ×3) | ✅ Terminé |
| 7 | Analytics / IA | `feature/analytics` | Nettoyage, stats, régression, tendances, dashboard, exports | Application (×10), Concevoir (×5) | ✅ Terminé |
| 8 | Docs DEV | `docs/dev` | Specs fonctionnelles, doc technique, README | Concevoir (×5), Spécifications (×5) | 🔄 En revue |
| 9 | Docs INFRA | `docs/infra` | Adressage, schéma réseau, droits, sécurité, serveurs, sauvegarde et supervision, cloud, déploiement et budget | Toute la grille INFRA | 🔄 En revue |
| 10 | Scripts INFRA | `docs/infra` (avec la doc) | PowerShell AD, partages NTFS, vérification ; GPO décrites dans le guide des serveurs ; sauvegarde de la base | Droits d'accès (×3), Serveurs (×5) | 🔄 En revue |
| 11 | Oraux | `docs/oral` | Plans d'oral intermédiaire et final, démo VM | Présenter (×5), Démo VM (×10) | ⏳ À faire |

## 4. Journal d'avancement

| Date | Phase | Fait | Reste à faire |
|---|---|---|---|
| 2026-11-16 | 0 — Setup | Dépôt Git (`main`/`develop`), structure en couches, Docker Compose (app + PostgreSQL 16), Alembic, CI, healthchecks, tests de fumée | Phases 1 à 11 |
| 2026-11-16 | 1 à 7 — Application | Modèle de données, vues SQL et index ; authentification et rôles ; biens ; espace client ; back-office ; front ; analyses et IA ; jeu de démonstration (une branche `feature/*` par phase, fusionnée dans `develop`) | Documentation, INFRA |
| 2026-11-18 | 6 — Front (finitions) | Système d'animations et finitions visuelles (`feat/motion`), version livrée sur `main` | — |
| 2026-11-18 | 9, 10 — INFRA | 7 documents INFRA, schéma draw.io, scripts PowerShell (annuaire, droits, partages, contrôle) et de sauvegarde (branche `docs/infra`) | Pull request vers `develop` ; démo VM |
| 2026-11-18 | 8 — Docs DEV | README, spécifications fonctionnelles, documentation technique (branche `docs/dev`) | Pull request vers `develop` |

## 5. Risques identifiés

| Risque | Impact | Mitigation |
|---|---|---|
| Données DVF indisponibles ou trop volumineuses | Analytics vides | Script de seed réaliste par défaut, import DVF optionnel |
| Démo VM instable le jour de l'oral | Coef. 10 | Guide pas à pas, snapshots VirtualBox, vidéo de secours |
| Dérive du périmètre | Retard | Backlog priorisé : fonctionnalités cœur d'abord, bonus ensuite |
