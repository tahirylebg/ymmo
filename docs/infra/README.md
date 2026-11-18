# Livrables INFRA — Ymmo

Infrastructure du siège d'Aix-en-Provence et des 12 agences, reliés par VPN IPSec, avec une
extension cloud Azure.

| # | Livrable | Document |
|---|---|---|
| 1 | Plan d'adressage IP | [01-plan-adressage-ip.md](01-plan-adressage-ip.md) |
| 2 | Schéma réseau | [schema-reseau.png](schema-reseau.png) (source draw.io : [schema-reseau.drawio](schema-reseau.drawio)) |
| 3 | Plan de gestion des droits d'accès | [02-gestion-droits-acces.md](02-gestion-droits-acces.md) + scripts [`infra/scripts/`](../../infra/scripts/) |
| 4 | Politique de sécurité | [03-politique-securite.md](03-politique-securite.md) |
| 5 | Guide de configuration des serveurs (et recette de la démo) | [04-guide-configuration-serveurs.md](04-guide-configuration-serveurs.md) |
| 6 | Plan de sauvegarde et de supervision | [05-plan-sauvegarde-supervision.md](05-plan-sauvegarde-supervision.md) |
| 7 | Solution cloud (Azure) | [06-solution-cloud-azure.md](06-solution-cloud-azure.md) |
| 8 | Guide de déploiement, matériel et budget | [07-deploiement-materiel-budget.md](07-deploiement-materiel-budget.md) |

## En bref

- **Adressage** : `10.<site>.<VLAN>.0/24`. Siège = site 0, agences = 1 à 12 (mêmes codes que la plateforme), Azure = `10.100.0.0/16`.
- **Réseau** : un VLAN par pôle au siège, une DMZ, un réseau invités isolé. VPN IPSec IKEv2 en étoile autour du pare-feu du siège.
- **Annuaire** : domaine `ad.ymmo.fr`. Droits selon le modèle AGDLP, générés et vérifiés par script à partir d'une seule matrice ([`YmmoAccessMatrix.psd1`](../../infra/scripts/YmmoAccessMatrix.psd1)).
- **Sécurité** : tout est refusé par défaut, avec une matrice des flux justifiée ; comptes d'administration séparés, LAPS, double authentification sur les pare-feu et Azure.
- **Sauvegarde** : règle 3-2-1, avec le NAS du siège, Azure et un disque hors ligne ; tests de restauration chaque trimestre. **Supervision** : Zabbix, journaux centralisés, sonde Azure.
- **Cloud** : modèle hybride, avec la plateforme Ymmo en PaaS et un second contrôleur de domaine dans Azure.
- **Budget** : environ 48 600 € d'investissement et 16 700 €/an de fonctionnement (HT, estimations à confirmer par devis).
