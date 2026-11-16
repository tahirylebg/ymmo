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
| 1 | Base de données | `feature/database` | Modèles ORM, migrations Alembic, vues SQL, index | Modéliser BDD (×3), Interroger BDD (×4) | ⏳ À faire |
| 2 | Authentification | `feature/auth` | Inscription, connexion, JWT, rôles | Application fonctionnelle (×10) | ⏳ À faire |
| 3 | Biens | `feature/properties` | CRUD agent, recherche, filtres, pagination, fiche | Application fonctionnelle (×10) | ⏳ À faire |
| 4 | Espace client | `feature/client-space` | Favoris, visites, dépôt de bien, suivi | Application fonctionnelle (×10) | ⏳ À faire |
| 5 | Espace agent | `feature/agent-space` | Dashboard, visites, offres, transactions | Application fonctionnelle (×10) | ⏳ À faire |
| 6 | Front | `feature/frontend` | Pages responsives, accessibles, performantes | Interfaces (×5 + ×3) | ⏳ À faire |
| 7 | Analytics / IA | `feature/analytics` | Nettoyage, stats, régression, tendances, dashboard, exports | Application (×10), Concevoir (×5) | ⏳ À faire |
| 8 | Docs DEV | `docs/dev` | Specs fonctionnelles, doc technique, README | Concevoir (×5), Spécifications (×5) | ⏳ À faire |
| 9 | Docs INFRA | `docs/infra` | 11 documents INFRA | Toute la grille INFRA | ⏳ À faire |
| 10 | Scripts INFRA | `infra/scripts` | PowerShell AD, partages NTFS, GPO, vérification | Droits d'accès (×3), Serveurs (×5) | ⏳ À faire |
| 11 | Oraux | `docs/oral` | Plans d'oral intermédiaire et final | Présenter (×5) | ⏳ À faire |

## 4. Journal d'avancement

| Date | Phase | Fait | Reste à faire |
|---|---|---|---|
| 2026-11-16 | 0 — Setup | Dépôt Git (`main`/`develop`), structure en couches, Docker Compose (app + PostgreSQL 16), Alembic, CI, healthchecks, tests de fumée | Phases 1 à 11 |

## 5. Risques identifiés

| Risque | Impact | Mitigation |
|---|---|---|
| Données DVF indisponibles ou trop volumineuses | Analytics vides | Script de seed réaliste par défaut, import DVF optionnel |
| Démo VM instable le jour de l'oral | Coef. 10 | Guide pas à pas, snapshots VirtualBox, vidéo de secours |
| Dérive du périmètre | Retard | Backlog priorisé : fonctionnalités cœur d'abord, bonus ensuite |
