# Plan de sauvegarde et de supervision — Ymmo

Livrable INFRA · Plan de sauvegarde et de supervision. S'appuie sur le
[plan d'adressage](01-plan-adressage-ip.md), la [politique de sécurité](03-politique-securite.md)
et le [guide de configuration des serveurs](04-guide-configuration-serveurs.md).

## 1. Ce qu'il faut protéger

| Donnée | Où | Criticité | Remarque |
|---|---|---|---|
| Annuaire (comptes, groupes, GPO), DNS, DHCP | SRV-AIX-01 | **Critique** : sans lui, personne n'ouvre de session | Un seul contrôleur de domaine : voir § 6 |
| Dossiers partagés des pôles | SRV-AIX-01 `D:\Partages` | **Critique** : documents de travail, RH, direction | |
| Base de la plateforme (biens, clients, ventes) | SRV-AIX-02, PostgreSQL en conteneur | **Critique** : activité commerciale et données personnelles (RGPD) | |
| Photos des biens (`media`) | SRV-AIX-02, volume Docker | Importante | Re-téléversables, mais long |
| Configuration des 13 pare-feu | FW-AIX, FW-MRS … | Importante : contient le VPN et le filtrage | Fichier XML |
| Postes de travail | 30 au siège, environ 60 en agence | Faible | **Aucune donnée locale** : les documents sont redirigés vers le serveur (§ 2.4), un poste se réinstalle |

Les agences n'hébergent aucune donnée : tout est au siège ou sur la plateforme. Une agence
se reconstruit avec un pare-feu (configuration sauvegardée) et des postes neufs.

### Objectifs de reprise

- **RPO** (perte de données maximale admise) : l'âge maximal de la dernière sauvegarde utilisable.
- **RTO** (durée d'interruption maximale admise) : le temps pour remettre le service en route.

| Service | RPO | RTO | Comment on l'atteint |
|---|---|---|---|
| Annuaire, DNS, DHCP | 24 h | 4 h | Image complète nocturne, corbeille AD pour les erreurs du quotidien |
| Dossiers partagés | 5 h en journée | 1 h pour un fichier, 4 h pour le serveur | Clichés instantanés à 12 h et 17 h + sauvegarde nocturne |
| Base de la plateforme | 1 h | 2 h | Export toutes les heures de 7 h à 20 h + nocturne |
| Pare-feu | Dernière modification | 1 h (siège), J+1 (agence) | Export après chaque modification, boîtier de rechange au siège |

## 2. Dispositif : règle 3-2-1

```
            Production                    Copie 1 (siège)               Copie 2 (hors site, en ligne)      Copie 3 (hors ligne)
  SRV-AIX-01  ── Active Backup ──▶                                  ── Hyper Backup ──▶                 ── disque USB ──▶
  SRV-AIX-02  ── for Business ───▶   NAS-AIX-01  10.0.60.20        chiffré AES-256                      rotation mensuelle,
                (agents, nuit)        (Synology, RAID 5)            Azure Blob Storage                   coffre hors du siège
  Pare-feu    ── export XML ─────▶                                  (France Centre)
```

- **3 copies** : la production, le NAS du siège, puis Azure et un disque hors ligne.
- **2 supports** : les disques du serveur et ceux du NAS, puis le cloud.
- **1 copie hors site**, qui résiste à un incendie ou à un vol au siège : Azure, plus un disque déconnecté qui résiste aussi à un rançongiciel.

### 2.1 Outils

Le NAS Synology fournit les deux outils sans licence supplémentaire :

- **Active Backup for Business (ABB)** : un agent sur chaque serveur Windows et Linux. Il fait des sauvegardes incrémentales par blocs, restaure un fichier, un volume ou la machine entière (bare metal), et déduplique.
- **Hyper Backup** : il copie le NAS vers Azure Blob Storage et vers un disque USB, avec chiffrement côté NAS. La clé reste chez Ymmo : Microsoft ne voit que des données chiffrées.

### 2.2 Planning et rétention

| Tâche | Source → destination | Fréquence | Rétention |
|---|---|---|---|
| Clichés instantanés (VSS, « Versions précédentes ») | `D:` → `D:` | 12 h et 17 h, jours ouvrés | 64 versions (environ 6 semaines) |
| ABB image complète SRV-AIX-01 (système, état AD, `D:`) | SRV-AIX-01 → NAS | Chaque nuit à 22 h | 14 quotidiennes, 8 hebdomadaires, 12 mensuelles |
| Export base de données | Conteneur `db` → `/var/backups/ymmo` | Toutes les heures, 7 h–20 h | 14 jours en local |
| Export base + photos | Idem | Chaque nuit à 1 h 30 | 14 jours en local |
| ABB SRV-AIX-02 (`/opt/ymmo`, `/var/backups/ymmo`, `/etc`) | SRV-AIX-02 → NAS | Chaque nuit à 2 h | 14 quotidiennes, 8 hebdomadaires, 12 mensuelles |
| Export de configuration des pare-feu | OPNsense → `D:\Partages\IT\Reseau` | Après chaque modification | Historique OPNsense (60 versions) + sauvegardes de `D:` |
| Hyper Backup NAS → Azure | NAS → Azure Blob (niveau « Cool ») | Chaque nuit à 4 h | 30 quotidiennes, 12 mensuelles |
| Hyper Backup NAS → USB | NAS → disque USB | Le 1er lundi du mois | 3 disques en rotation : un branché, deux au coffre hors site |

La base est sauvegardée par un **export logique** (`pg_dump`) et non par une copie du
volume Docker. Une copie du volume prise pendant que PostgreSQL écrit peut être
inutilisable, alors qu'un export est toujours cohérent. Le script
[`infra/scripts/ymmo-backup-db.sh`](../../infra/scripts/ymmo-backup-db.sh) produit l'export
local, et ABB l'emporte ensuite sur le NAS.

```cron
# /etc/cron.d/ymmo-backup sur SRV-AIX-02
0  7-20 * * *  root  /opt/ymmo/infra/scripts/ymmo-backup-db.sh
30 1    * * *  root  /opt/ymmo/infra/scripts/ymmo-backup-db.sh full
```

### 2.3 Protection des sauvegardes elles-mêmes

Un rançongiciel cherche d'abord à détruire les sauvegardes.

- **NAS**
  - Un compte de service dédié par serveur, avec un mot de passe aléatoire.
  - Le NAS n'est membre d'aucun partage accessible aux utilisateurs.
  - Son interface d'administration n'est ouverte qu'au VLAN IT, avec double authentification.
  - Les sauvegardes ABB sont rendues immuables pendant 7 jours (fonction de DSM 7.2) : personne, pas même un administrateur, ne peut les supprimer avant l'échéance.
- **Azure**
  - Compte de stockage dédié, avec le versionnage des blobs et la suppression réversible à 30 jours. Un fichier écrasé ou effacé reste récupérable pendant 30 jours.
  - Verrou de ressource sur le compte.
  - Accès d'administration Azure réservé à deux comptes, avec double authentification.
- **Disque USB** : il est **déconnecté** 29 jours sur 30, c'est la seule copie qu'une attaque ne peut pas atteindre.
- **Chiffrement** : toutes les copies hors du siège sont chiffrées. La clé Hyper Backup est conservée imprimée, sous enveloppe scellée dans le coffre, et dans le coffre de mots de passe de l'IT.

### 2.4 Configuration côté Windows

```powershell
# Corbeille Active Directory : un compte ou un groupe supprimé par erreur se restaure en une commande
Enable-ADOptionalFeature 'Recycle Bin Feature' -Scope ForestOrConfigurationSet -Target 'ad.ymmo.fr' -Confirm:$false
# Restauration : Get-ADObject -Filter 'samAccountName -eq "j.roux"' -IncludeDeletedObjects | Restore-ADObject

# Clichés instantanés sur D: (12 h et 17 h)
vssadmin add shadowstorage /for=D: /on=D: /maxsize=15%
$action = New-ScheduledTaskAction -Execute 'vssadmin.exe' -Argument 'create shadow /for=D:'
$trigger = @(New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 12:00),
           (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 17:00)
Register-ScheduledTask -TaskName 'Ymmo - Cliches D' -Action $action -Trigger $trigger -User 'SYSTEM' -RunLevel Highest
```

Les clichés laissent un utilisateur restaurer lui-même une version précédente d'un fichier
(clic droit ▸ *Restaurer les versions précédentes*), sans ticket à l'IT.

**Redirection de dossiers (GPO `Ymmo - Session utilisateurs`)** : Documents et Bureau sont
redirigés vers `\\SRV-AIX-01\Profils$\%USERNAME%`. Les postes ne contiennent alors plus
aucune donnée à sauvegarder. Ce partage caché n'est pas créé par les scripts : il suit la
procédure Microsoft de redirection de dossiers (les utilisateurs peuvent créer leur dossier,
seul son propriétaire y accède ensuite).

## 3. Restauration

| Scénario | Procédure | Durée visée |
|---|---|---|
| Fichier supprimé ou écrasé | L'utilisateur : « Versions précédentes ». Sinon, l'IT restaure depuis ABB (portail de restauration) | 15 min |
| Compte AD supprimé | Corbeille AD (`Restore-ADObject`) | 5 min |
| GPO cassée | `Restore-GPO` depuis une sauvegarde `Backup-GPO`, faite avant chaque modification | 15 min |
| SRV-AIX-01 hors service | ABB : restauration bare metal sur une nouvelle VM (ou sur le serveur réparé) depuis le média de récupération ABB | 4 h |
| Base de la plateforme corrompue | Restaurer le dernier export sain (commandes ci-dessous) | 1 h |
| SRV-AIX-02 perdu | Nouvelle VM Debian (§ 6 du guide), `git clone`, restauration de `.env`, de la base et des photos | 2 h |
| Pare-feu d'agence en panne | Envoi du boîtier de rechange, import de la configuration XML de l'agence | J+1 |
| Siège détruit (incendie) | Matériel neuf, restauration depuis Azure (ou le disque USB du coffre), dans l'ordre : pare-feu, SRV-AIX-01, SRV-AIX-02 | 3 à 5 jours |

Restaurer la base de la plateforme :

```bash
cd /opt/ymmo
docker compose stop app
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
    < /var/backups/ymmo/db_AAAA-MM-JJ_HHMM.dump
docker compose start app
curl -fsS http://localhost:8000/api/health/db
```

### Tests de restauration

Une sauvegarde jamais restaurée n'est pas une sauvegarde. Chaque trimestre, l'IT déroule
ces tests et note le résultat et la durée dans un registre (`D:\Partages\IT\Sauvegardes`) :

| Test | Comment | Critère de réussite |
|---|---|---|
| Base de la plateforme | Restaurer le dernier export dans une base temporaire (`createdb restore_test`, `pg_restore`), compter les biens et les ventes | Mêmes nombres que la production à l'heure de l'export |
| Fichiers | Restaurer un dossier d'un pôle choisi au hasard depuis ABB, à un autre emplacement | Fichiers lisibles, droits NTFS conservés |
| Serveur complet | Une fois par an : restauration bare metal de SRV-AIX-01 sur une VM isolée (sans réseau) | Le domaine démarre, `dcdiag` sans erreur |
| Copie Azure | Restaurer un fichier depuis Hyper Backup (Azure) sur un poste de test | Fichier identique, déchiffré avec la clé du coffre |

## 4. Supervision

### 4.1 Outils

| Besoin | Outil | Où |
|---|---|---|
| Disponibilité et performances (serveurs, services, VPN, sites) | **Zabbix 7.0 LTS** (libre) | Conteneurs sur NAS-AIX-01 (Container Manager), interface `https://10.0.60.20:8443` |
| Centralisation des journaux (pare-feu, serveurs) | Synology **Log Center**, réception syslog | NAS-AIX-01, UDP/TCP 514, rétention 1 an |
| Disponibilité du site vu d'Internet | Test de disponibilité **Azure Monitor** | Azure : sonde HTTPS depuis plusieurs régions |
| Alertes | Courriel à `it@ymmo.fr`, et Microsoft Teams (canal « Alertes IT ») pour les alertes critiques | |

- **Pourquoi le NAS** : les deux serveurs du siège ont chacun leur rôle, et Ymmo n'a pas besoin d'un troisième serveur pour la supervision. Le NAS a la mémoire nécessaire (16 Go) et il est déjà dans le VLAN serveurs.
- **Le point faible** : si le NAS tombe, Zabbix tombe avec lui. Le NAS envoie donc lui-même ses alertes matérielles par courriel (disque, RAID, température). Zabbix envoie en plus chaque matin un rapport « tout va bien » : son absence est en soi une alerte.
- **La sonde Azure** surveille le site public de l'extérieur. Elle détecte ce que la supervision interne ne voit pas : une coupure de la connexion Internet du siège ou un certificat expiré.

### 4.2 Ce qui est surveillé

| Équipement | Méthode | Indicateurs et seuils d'alerte |
|---|---|---|
| **SRV-AIX-01** | Agent Zabbix 2, modèle *Windows by Zabbix agent active* | Processeur > 85 % pendant 15 min · mémoire > 90 % · disque `C:` ou `D:` > 85 % (avertissement), > 95 % (critique) · services `NTDS`, `DNS`, `DHCPServer`, `Netlogon`, `Kdc`, `LanmanServer` arrêtés (critique) · résolution DNS de `ad.ymmo.fr` · journal Sécurité : plus de 20 échecs d'ouverture de session (4625) en 5 min, ajout à un groupe d'administration (4728, 4732, 4756) |
| **SRV-AIX-02** | Agent Zabbix 2, modèles *Linux* et *Docker* | Processeur, mémoire, disque comme ci-dessus · conteneurs `app` et `db` arrêtés ou en redémarrage · âge de `/var/backups/ymmo/last_success` > 2 h en journée (critique) |
| **Plateforme Ymmo** | Scénario web Zabbix | `GET /api/health/db` : réponse 200 en moins de 2 s, sinon critique au bout de 3 échecs · certificat TLS qui expire dans moins de 14 jours |
| **Pare-feu** (13) | SNMP v3 (authentification et chiffrement) | Pare-feu injoignable · **chaque tunnel IPSec** (critique s'il est tombé plus de 5 min) · débit WAN > 80 % pendant 15 min · processeur, mémoire |
| **Switch cœur, bornes Wi-Fi** | SNMP v3 | Injoignable · ports montants (uplinks) tombés · erreurs d'interface |
| **Imprimantes** (13) | SNMP | Injoignable · toner < 10 % (avertissement, commande de toner) |
| **NAS-AIX-01** | SNMP + notifications Synology | État RAID, santé SMART des disques, température, volume > 85 % · **tâche de sauvegarde en échec** (ABB, Hyper Backup) : critique |
| **Accès Internet** | ICMP vers deux résolveurs publics, depuis Zabbix | Perte > 20 % ou latence > 100 ms pendant 10 min |

### 4.3 Niveaux d'alerte

| Niveau | Exemples | Notification | Délai de prise en charge |
|---|---|---|---|
| **Critique** | Contrôleur de domaine ou site injoignable, tunnel d'agence tombé, sauvegarde en échec, RAID dégradé | Courriel + Teams, relance toutes les 30 min | 30 min en heures ouvrées |
| **Avertissement** | Disque > 85 %, certificat qui expire dans moins de 14 jours, toner bas | Courriel | Jour ouvré suivant |
| **Information** | Redémarrage planifié, mise à jour appliquée | Tableau de bord seulement | — |

Les fenêtres de maintenance (mises à jour mensuelles, cf. politique de sécurité § 9) sont
déclarées dans Zabbix pour éviter les fausses alertes.

### 4.4 Tableau de bord

Le tableau de bord Zabbix « Ymmo – Vue réseau » affiche :

- la carte des 13 sites, chaque site passant au rouge si son tunnel tombe ;
- l'état des deux serveurs et de la plateforme ;
- l'heure de la dernière sauvegarde réussie de chaque élément ;
- les alertes en cours.

L'IT le consulte chaque matin, et la Direction reçoit un rapport mensuel de disponibilité
(objectif : 99,5 % en heures ouvrées pour l'annuaire et la plateforme).

### 4.5 Flux réseau supplémentaires

À ajouter à la matrice des flux de la [politique de sécurité](03-politique-securite.md) (§ 3) :

| Source | Destination | Ports | Usage |
|---|---|---|---|
| SRV-AIX-01, SRV-AIX-02 | NAS-AIX-01 `10.0.60.20` | TCP 10051 | Agents Zabbix (mode actif : le serveur n'a pas besoin de joindre les agents) |
| NAS-AIX-01 | Pare-feu, switchs, bornes, imprimantes (tous sites, via VPN) | UDP 161 | Interrogation SNMP |
| Pare-feu (tous sites), SRV-AIX-01, SRV-AIX-02 | NAS-AIX-01 | UDP/TCP 514 | Journaux (syslog) |
| NAS-AIX-01 | Internet (Azure Blob Storage) | TCP 443 | Hyper Backup |
| SRV-AIX-02 (DMZ) | NAS-AIX-01 | TCP 5510 et 10051 | Agent ABB et agent Zabbix : seule ouverture de la DMZ vers le LAN, limitée à ces deux ports |

## 5. Dans la maquette (démonstration)

La maquette n'a pas de NAS. On y montre :

- **Sauvegarde** :
  - l'installation de la fonctionnalité *Sauvegarde Windows Server* sur SRV-AIX-01 ;
  - une sauvegarde de l'état du système vers un second disque (`wbadmin start systemstatebackup -backuptarget:E:`) ;
  - la corbeille AD : suppression puis restauration de `j.roux`.
- **Supervision** (si la mémoire le permet) :
  - une VM Debian avec Zabbix en conteneurs (fichier `docker compose` officiel du dépôt `zabbix/zabbix-docker`), dans le réseau `aix-vlan60` ;
  - SRV-AIX-01 et FW-AIX ajoutés ;
  - on coupe le tunnel et on montre l'alerte.

## 6. Limites et évolutions

| Limite | Risque | Évolution proposée |
|---|---|---|
| Un seul contrôleur de domaine | S'il tombe, plus d'ouverture de session (les sessions déjà ouvertes continuent, avec les identifiants en cache) | Second contrôleur de domaine dans Azure (`10.100.0.0/16`, relié par VPN) : voir la solution cloud |
| Supervision hébergée sur le NAS | Perte simultanée des sauvegardes locales et de la supervision | Acceptable à cette taille, compensé par les alertes propres au NAS, le rapport quotidien et la sonde Azure |
| RTO du siège en cas de sinistre : plusieurs jours | Arrêt de l'activité au siège (les agences continuent la vente via la plateforme si elle est hébergée hors du siège) | Hébergement de la plateforme dans Azure : voir la solution cloud |
