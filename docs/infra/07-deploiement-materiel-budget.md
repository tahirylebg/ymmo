# Guide de déploiement, liste du matériel et budget — Ymmo

Livrable INFRA · Guide de déploiement, matériel et budget. Il rassemble les choix des
documents précédents : [plan d'adressage](01-plan-adressage-ip.md),
[droits d'accès](02-gestion-droits-acces.md), [politique de sécurité](03-politique-securite.md),
[configuration des serveurs](04-guide-configuration-serveurs.md),
[sauvegarde et supervision](05-plan-sauvegarde-supervision.md),
[solution cloud](06-solution-cloud-azure.md).

## 1. Liste du matériel

**Prix indicatifs HT** : ce sont des ordres de grandeur du marché, pas des devis. Ils sont
**à confirmer par devis** avant toute commande : les remises revendeur et les variations
de prix des composants peuvent les faire bouger de ±20 %.

### 1.1 Siège (Aix-en-Provence)

| Élément | Modèle proposé | Qté | Prix unitaire | Total | Justification |
|---|---|---|---|---|---|
| Pare-feu FW-AIX | Deciso DEC2750 (OPNsense) | 1 | 1 600 € | 1 600 € | Concentre 12 tunnels + Azure, IDS Suricata : il faut des ports 10 Gb/s et de la puissance de chiffrement |
| Switch cœur SW-AIX-CORE | Aruba Instant On 1960 24G 2XGT 2SFP+ | 1 | 700 € | 700 € | VLAN 802.1Q, liens 10 Gb/s vers les serveurs et le NAS |
| Switchs d'accès | Aruba Instant On 1960 24G PoE 370 W | 2 | 750 € | 1 500 € | 30 postes, bornes Wi-Fi et téléphones alimentés par le câble (PoE) |
| Bornes Wi-Fi | Aruba Instant On AP22 (Wi-Fi 6) | 3 | 180 € | 540 € | WPA3-Entreprise, un SSID par VLAN (personnel, invités) |
| Serveurs | Dell PowerEdge T360 : Xeon E-2400, 32 Go, 2 × SSD 960 Go en RAID 1, garantie 3 ans sur site | 2 | 3 200 € | 6 400 € | Hôte 1 : SRV-AIX-01 (Hyper-V). Hôte 2 : SRV-AIX-02 (Proxmox VE, gratuit), puis hôte de secours après la migration de la plateforme vers Azure |
| Licence Windows Server 2022 Standard | 16 cœurs | 1 | 1 100 € | 1 100 € | Couvre l'hôte 1 et jusqu'à 2 VM Windows |
| Licences d'accès client (CAL) | Windows Server, par utilisateur | 100 | 45 € | 4 500 € | Environ 90 salariés (30 au siège, 60 en agence) + marge |
| NAS NAS-AIX-01 | Synology DS923+, extension à 16 Go de RAM, 4 × 8 To (RAID 5, environ 24 To utiles) | 1 | 1 750 € | 1 750 € | Sauvegardes (Active Backup, Hyper Backup), Zabbix, journaux |
| Disques de sauvegarde hors ligne | Disque USB 8 To | 3 | 180 € | 540 € | Rotation mensuelle, coffre hors site |
| Onduleur | APC Smart-UPS 1500 VA rack, carte réseau | 1 | 1 100 € | 1 100 € | 20 min d'autonomie, arrêt propre des serveurs et du NAS piloté par la carte réseau |
| Baie et câblage | Baie 24U, bandeaux de brassage, cordons, étiquetage | 1 | 900 € | 900 € | |
| **Sous-total siège** | | | | **20 630 €** | |

### 1.2 Agence type (× 12)

| Élément | Modèle proposé | Qté | Prix unitaire | Total |
|---|---|---|---|---|
| Pare-feu | Deciso DEC740 (OPNsense) | 1 | 700 € | 700 € |
| Switch | Aruba Instant On 1930 8G PoE 124 W | 1 | 220 € | 220 € |
| Borne Wi-Fi | Aruba Instant On AP22 | 1 | 180 € | 180 € |
| Onduleur | APC Back-UPS 700 VA (pare-feu, switch, box) | 1 | 120 € | 120 € |
| Coffret mural et câblage | 6U | 1 | 150 € | 150 € |
| **Sous-total par agence** | | | | **1 370 €** |
| **12 agences** | | | | **16 440 €** |
| Pare-feu de rechange (stocké au siège) | Deciso DEC740 | 1 | 700 € | **700 €** |

### 1.3 Ce qui est conservé

- **Imprimantes** : l'imprimante du siège et celles des 12 agences sont conservées. Elles reçoivent une adresse fixe `10.N.70.10` dans le VLAN Impression.
- **Postes de travail** : les 30 postes du siège et la soixantaine en agence sont conservés, s'ils supportent Windows 11 (TPM 2.0, processeur pris en charge). Windows 10 n'a plus de correctifs de sécurité depuis octobre 2025 : un poste qui ne passe pas en Windows 11 est à remplacer. En option, une provision pour 20 % du parc (§ 3).

Pourquoi ces marques :

- **OPNsense sur boîtiers Deciso**
  - C'est le pare-feu utilisé dans la maquette, sur le matériel de son éditeur : la configuration documentée se recopie telle quelle.
  - Il n'y a pas de licence par fonction : VPN, IDS et VLAN sont inclus.
  - Un même modèle partout simplifie le stock de rechange.
- **Aruba Instant On**
  - Switchs et bornes administrés depuis une seule console.
  - Ils gèrent les VLAN et le WPA3-Entreprise, et coûtent nettement moins que des gammes « entreprise » surdimensionnées pour 5 postes par agence.

## 2. Logiciels et services

| Élément | Coût | Remarque |
|---|---|---|
| OPNsense, Proxmox VE, Zabbix, Debian, Docker, PostgreSQL | 0 € | Logiciels libres ; support commercial optionnel |
| Active Backup for Business, Hyper Backup, Log Center | 0 € | Inclus avec le NAS Synology |
| Windows LAPS, Microsoft Defender (antivirus des postes), BitLocker | 0 € | Inclus dans Windows Server et Windows 11 Pro |
| Plateforme Ymmo | 0 € de licence | Développée en interne (ce dépôt) |
| Azure | ≈ 300 €/mois | Détail dans la [solution cloud](06-solution-cloud-azure.md) |

## 3. Budget

### 3.1 Investissement (une fois)

| Poste | Montant HT |
|---|---|
| Matériel et licences du siège | 20 630 € |
| Matériel des 12 agences | 16 440 € |
| Pare-feu de rechange | 700 € |
| **Total matériel et licences** | **37 770 €** |
| Mise en œuvre par un prestataire, si l'IT interne ne la réalise pas seule : 15 jours à 600 € | 9 000 € |
| Déplacements dans les 12 agences | 1 800 € |
| **Total investissement** | **48 570 €** |
| *Option : renouvellement de 18 postes non compatibles Windows 11, 800 € pièce* | *14 400 €* |

### 3.2 Fonctionnement (par an)

| Poste | Calcul | Montant HT/an |
|---|---|---|
| Accès Internet du siège | Fibre dédiée 500 Mb/s symétrique, IP fixe, garantie de rétablissement en 4 h : 350 €/mois | 4 200 € |
| Accès Internet des agences | Fibre professionnelle avec IP fixe : 60 €/mois × 12 | 8 640 € |
| Azure | ≈ 300 €/mois | 3 600 € |
| Divers | Nom de domaine, renouvellement des disques USB, petites fournitures | 300 € |
| **Total fonctionnement** | | **16 740 €/an** |

**Coût de la première année : 48 570 € + 16 740 € = 65 310 € HT** (hors option postes).

Sur 5 ans, avec l'amortissement du matériel (durée de vie des équipements, garantie des
serveurs à prolonger après la 3ᵉ année) : 48 570 € + 5 × 16 740 € = **132 270 € HT**. Cela
représente environ 1 470 € par salarié sur 5 ans, soit **moins de 300 € par salarié et par
an** pour l'ensemble du système d'information, hors postes de travail.

## 4. Déploiement

### 4.1 Principes

- **Siège d'abord** : le siège porte l'annuaire, les fichiers et le cœur du VPN. Les agences ne sont raccordées qu'une fois qu'il est stable.
- **Agence pilote** : Marseille, la plus proche du siège, est déployée seule. Les problèmes y sont corrigés avant la généralisation.
- **Préparation au siège, installation sur site**
  - Les pare-feu d'agence sont configurés au siège, depuis une configuration modèle.
  - En agence, il ne reste plus qu'à brancher et tester : une demi-journée par agence.
- **Pas de coupure en journée** : les bascules ont lieu le soir ou le week-end. L'ancien équipement est laissé en place, débranché, jusqu'à la fin de la recette.

### 4.2 Planning

| Semaine | Phase | Contenu | Validation |
|---|---|---|---|
| S1 | Préparation | Commandes du matériel, contrats des accès Internet (délai de 4 à 8 semaines pour la fibre dédiée), maquette VM | Maquette : recette complète du guide de configuration, § 7 |
| S2–S3 | Siège : infrastructure | Baie, onduleur, switchs, VLAN, FW-AIX, bornes Wi-Fi | Chaque VLAN obtient une adresse et sort sur Internet selon la matrice des flux |
| S3–S4 | Siège : serveurs | Hôtes, SRV-AIX-01 (AD, DNS, DHCP, scripts de droits, GPO), NAS, sauvegardes, supervision | `03-Test-YmmoAccess.ps1` conforme, première sauvegarde restaurée |
| S5 | Siège : migration des postes | Jonction des 30 postes au domaine, copie des fichiers existants dans les dossiers de pôle, formation | Chaque pôle ouvre ses dossiers et seulement eux |
| S6 | Agence pilote : Marseille | Pare-feu préparé, tunnel, poste joint au domaine | Recette agence (§ 4.4) |
| S7–S9 | Généralisation | 11 agences, 4 par semaine, regroupées par région (Nice, Montpellier, Toulouse… puis Lyon, Grenoble…) | Recette agence pour chacune |
| S10 | Cloud | Azure phases 1 à 3 (réseau, VPN, SRV-AZ-01, sauvegardes hors site) | `repadmin /replsummary` sans échec, Hyper Backup réussi |
| S11 | Plateforme | Azure phases 4 et 5 (bascule de la plateforme, un soir) | Site en ligne, `/api/health/db` OK, données identiques |
| S12 | Clôture | Test de restauration complet, revue de sécurité, remise de la documentation, décommissionnement de l'ancien matériel (effacement sécurisé des disques) | Procès-verbal de recette signé par la Direction |

### 4.3 Préparation d'un pare-feu d'agence

Seules ces valeurs changent d'une agence à l'autre (N = numéro de site, cf. plan
d'adressage) :

| Variable | Valeur | Exemple (Lyon, N = 3) |
|---|---|---|
| Nom | `FW-<code>` | `FW-LYS` |
| IP WAN | Fournie par l'opérateur | `203.0.113.13` |
| LAN Commercial | `10.N.20.1/24` | `10.3.20.1/24` |
| DHCP | `10.N.20.100` – `10.N.20.199`, DNS `10.0.60.10` puis le pare-feu local (remplacé par `10.100.1.10` après la phase cloud, S10) | `10.3.20.100` – `10.3.20.199` |
| Impression, invités, administration | `10.N.70.1/24`, `10.N.90.1/24`, `10.N.99.1/24` | `10.3.70.1/24` … |
| Phase 2 du tunnel | `10.N.0.0/16 ↔ 10.0.0.0/16`, puis `10.N.0.0/16 ↔ 10.100.0.0/16` ajoutée en S10 | `10.3.0.0/16 ↔ 10.0.0.0/16` |
| Clé du tunnel | 32 caractères aléatoires, propre à l'agence, enregistrée dans le coffre de l'IT | — |

Procédure au siège :

1. Mettre à jour le firmware du boîtier.
2. Importer la configuration de FW-MRS (agence pilote validée) et remplacer les valeurs ci-dessus.
3. Créer le tunnel correspondant sur FW-AIX.
4. Tester le boîtier sur un port du siège simulant l'Internet de l'agence.
5. Exporter la configuration, chiffrée, dans `D:\Partages\IT\Reseau`.
6. Étiqueter le boîtier et l'expédier.

### 4.4 Installation et recette en agence (une demi-journée)

1. Installer le coffret, l'onduleur, le pare-feu, le switch et la borne. Brancher le WAN sur la box de l'opérateur, en mode passerelle ou IP fixe transmise.
2. Vérifier que le tunnel apparaît `ESTABLISHED` sur FW-AIX et que l'agence est verte dans Zabbix.
3. Pour chaque poste :
   - DHCP en `10.N.20.1xx` ;
   - jonction au domaine dans `OU=<code>,OU=Agences,OU=Ordinateurs` ;
   - ouverture de session d'un commercial de l'agence ;
   - lecteurs `S:` et `T:` présents ;
   - impression d'une page de test.
4. Ouvrir la plateforme Ymmo et se connecter en agent.
5. Vérifier le Wi-Fi :
   - le Wi-Fi invités ne donne accès qu'à Internet (`Test-NetConnection 10.0.60.10 -Port 445` échoue) ;
   - le Wi-Fi du personnel place le poste dans le VLAN 20.
6. Faire signer la fiche de recette par le responsable d'agence ; elle est classée dans `D:\Partages\IT\Deploiement`.

**Retour arrière** : si la recette échoue et que le problème n'est pas résolu dans la
demi-journée, on rebranche l'ancienne box. L'agence repart comme avant, sans accès aux
dossiers du siège mais avec la plateforme, accessible par Internet.

### 4.5 Accompagnement des utilisateurs

- **Une semaine avant**, un courriel par pôle ou par agence : ce qui change (ouverture de session sur le domaine, nouveaux lecteurs, mot de passe de 12 caractères), la date et la personne à contacter.
- **Le jour J**, l'IT est sur place ; la première ouverture de session se fait avec chaque utilisateur.
- **Supports** :
  - une fiche d'une page (« Où sont mes dossiers ? », « Restaurer une version précédente », « Signaler un problème ») ;
  - la charte informatique, à signer.
- **Les deux semaines suivantes**, l'IT traite en priorité les demandes de l'agence nouvellement déployée.

## 5. Rôles

| Rôle | Responsable | Tâches |
|---|---|---|
| Pilotage | Direction | Validation du budget, du planning et des procès-verbaux de recette |
| Chef de projet technique | Responsable IT | Planning, commandes, coordination des opérateurs et du prestataire |
| Réalisation | Pôle IT (+ prestataire si retenu) | Installation, configuration, recettes |
| Relais en agence | Responsable de chaque agence | Accès aux locaux, présence le jour J, signature de la recette |
| Utilisateurs pilotes | Un commercial du siège, un commercial de Marseille | Tests avant la généralisation |
