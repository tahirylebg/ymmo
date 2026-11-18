# Politique de sécurité — Ymmo

Livrable INFRA · Politique de sécurité. S'appuie sur le
[plan d'adressage](01-plan-adressage-ip.md) et le
[plan de gestion des droits](02-gestion-droits-acces.md).

## 1. Principes

| Principe | Traduction chez Ymmo |
|---|---|
| **Tout est interdit sauf ce qui est autorisé** | Chaque pare-feu bloque par défaut ; chaque flux autorisé a une règle et une justification (§ 3) |
| **Moindre privilège** | Droits par groupes (AGDLP), comptes d'administration séparés, aucun utilisateur administrateur de son poste |
| **Défense en profondeur** | Un accès aux fichiers RH doit franchir : le pare-feu (VLAN), l'authentification AD, les droits NTFS, l'audit |
| **Segmentation** | Un VLAN par pôle, une DMZ pour le serveur exposé, un réseau invités isolé, un réseau d'administration |
| **Traçabilité** | Journaux des pare-feu, du contrôleur de domaine et des accès aux dossiers sensibles, centralisés et conservés (plan de supervision) |

## 2. Zones de confiance

| Zone | Réseaux | Confiance | Exposition |
|---|---|---|---|
| Internet | — | Aucune | — |
| **DMZ** | `10.0.100.0/24` | Faible : serveur exposé, présumé attaquable | HTTPS depuis Internet |
| Wi-Fi invités | `10.S.90.0/24` (S = numéro de site) | Aucune | Internet seulement |
| Postes des pôles | `10.0.10–50.0/24`, `10.N.20.0/24` | Moyenne | Aucune entrante |
| Impression | `10.S.70.0/24` | Moyenne | Aucune entrante |
| **Serveurs** | `10.0.60.0/24` | Élevée | Aucune depuis Internet |
| **Administration réseau** | `10.S.99.0/24` | Élevée | Depuis le VLAN IT uniquement |

## 3. Matrice des flux (pare-feu)

Règle finale de chaque interface : **refus et journalisation**. Les flux ci-dessous sont
les seuls autorisés ; le pare-feu étant à états, les réponses sont acceptées automatiquement.

### Siège (FW-AIX)

| # | Source | Destination | Ports | Pourquoi |
|---|---|---|---|---|
| 1 | Internet | SRV-AIX-02 `10.0.100.10` (NAT depuis `203.0.113.10`) | TCP 443, TCP 80 (redirigé vers HTTPS) | Site public Ymmo |
| 2 | VLAN 10–50, agences `10.N.20.0/24` | SRV-AIX-01 `10.0.60.10` | Services AD : TCP/UDP 53, 88, 464, 389 ; UDP 123 ; TCP 135, 445, 636, 3268–3269, 49152–65535 | Ouverture de session, GPO, DNS, partages de fichiers |
| 3 | VLAN 10–50 | Passerelle `.1` | UDP 67 | DHCP (relais vers SRV-AIX-01) |
| 4 | VLAN 10–50 | PRN-AIX-01 `10.0.70.10` | TCP 9100, TCP 631 | Impression |
| 5 | VLAN 10–50, agences | SRV-AIX-02 `10.0.100.10` | TCP 443 | Plateforme Ymmo (accès agents) |
| 6 | VLAN 10–50 | Internet | TCP 80, 443 | Navigation (DNS résolu par le contrôleur de domaine uniquement) |
| 7 | SRV-AIX-01 | Internet | UDP/TCP 53, UDP 123, TCP 443 | Redirecteurs DNS, heure, mises à jour |
| 8 | SRV-AIX-02 (DMZ) | Internet | TCP 443, UDP 123 | Mises à jour, images Docker |
| 9 | VLAN 50 (IT) | SRV-AIX-02 | TCP 22 | Administration SSH (clé uniquement) |
| 10 | VLAN 50 (IT) | SRV-AIX-01 | TCP 3389 | Bureau à distance (NLA) |
| 11 | VLAN 50 (IT) | VLAN 99, interfaces d'admin des pare-feu (tous sites, via VPN) | TCP 22, 443 | Administration réseau |
| 12 | SRV-AIX-01, SRV-AIX-02 | NAS-AIX-01 `10.0.60.20` | TCP 5510, TCP 10051, UDP/TCP 514 | Agents de sauvegarde et de supervision, journaux (détail dans le [plan de sauvegarde et de supervision](05-plan-sauvegarde-supervision.md), § 4.5) |
| 13 | VLAN 90 (invités) | Internet | TCP 80, 443 ; UDP/TCP 53 vers un résolveur public | Visiteurs, **toute destination `10.0.0.0/8` refusée** |

Explicitement interdits (règles de refus journalisées, placées avant les autorisations
larges) :
- de la DMZ vers le LAN (seule exception : la règle 12, vers le NAS et sur ces ports) ;
- d'un VLAN de pôle vers un autre ;
- d'une agence vers une autre ;
- de tout réseau, sauf le VLAN IT, vers les interfaces d'administration ;
- des postes vers Internet en SMB, RDP ou SSH ;
- d'Internet vers tout ce qui n'est pas la règle 1.

### Agences (FW-MRS … FW-GNB)

| Source | Destination | Ports | Pourquoi |
|---|---|---|---|
| VLAN 20 | `10.0.0.0/16` via le tunnel | Règles 2, 5 et 6 du siège (le filtrage fin est fait par FW-AIX) | Annuaire, fichiers, plateforme |
| VLAN 20 | PRN de l'agence `10.N.70.10` | TCP 9100, 631 | Impression locale |
| VLAN 20 | Internet (sortie locale) | TCP 80, 443 | Navigation |
| VLAN 90 | Internet | TCP 80, 443, DNS public | Visiteurs, `10.0.0.0/8` refusé |
| VLAN 50 du siège (via le tunnel) | Pare-feu, VLAN 99 de l'agence | TCP 22, 443 | Administration à distance |

## 4. Pare-feu (pfSense / OPNsense)

- **Administration**
  - Interface web et SSH accessibles seulement depuis le VLAN IT, jamais depuis le WAN.
  - Un compte nominatif par administrateur, double authentification (TOTP).
  - Configuration sauvegardée après chaque modification.
- **Filtrage d'entrée**
  - Les réseaux privés et les plages non attribuées sont refusés sur le WAN (anti-usurpation).
  - Pas de réponse au ping sur le WAN.
- **Détection d'intrusion** : Suricata sur le WAN du siège.
  - Mode alerte pendant un mois, pour écarter les faux positifs.
  - Puis blocage, avec les règles ET Open.
- **DNS** : les postes ne peuvent résoudre qu'auprès du contrôleur de domaine. Le pare-feu bloque le TCP/UDP 53 sortant des VLAN utilisateurs, ce qui empêche de contourner le filtrage.
- **Journaux** : envoyés en syslog vers le serveur de supervision et conservés 1 an (la CNIL recommande 6 mois à 1 an pour les journaux de sécurité).

## 5. VPN IPSec site à site

| Paramètre | Valeur |
|---|---|
| Version | IKEv2 |
| Phase 1 | AES-256-GCM, PRF SHA-256, Diffie-Hellman groupe 19 (ECP 256) ou 14 au minimum, durée de vie 8 h |
| Phase 2 | ESP AES-256-GCM, PFS groupe 19, durée de vie 1 h, réseaux `10.0.0.0/16 ↔ 10.N.0.0/16` |
| Authentification | Clé pré-partagée de 32 caractères aléatoires, différente par site, stockée dans le coffre de mots de passe de l'IT. Cible : certificats émis par une autorité interne |
| Surveillance | Détection des pairs morts (DPD) ; alerte de supervision si un tunnel tombe |
| Accès à distance | Pas de VPN nomade dans le périmètre actuel. Si besoin : WireGuard ou OpenVPN sur FW-AIX, avec double authentification, vers un VLAN dédié filtré comme une agence |

## 6. Comptes et mots de passe (GPO de domaine)

| Règle | Valeur |
|---|---|
| Longueur minimale | 12 caractères, complexité activée (recommandations ANSSI) ; 16 pour les comptes `adm.*` |
| Historique / durée | 12 derniers mots de passe mémorisés ; pas d'expiration périodique forcée pour les utilisateurs (recommandation ANSSI et NIST), changement immédiat en cas de doute |
| Verrouillage | 5 échecs, verrouillage 15 minutes (freine les attaques par force brute sans permettre un déni de service durable) |
| Comptes d'administration | Séparés (`adm.<nom>`), membres du groupe « Protected Users », interdits d'ouverture de session sur les postes utilisateurs |
| Administrateur local des postes | Mot de passe unique par poste, renouvelé automatiquement (Windows LAPS) |
| Comptes de service | Comptes de service gérés (gMSA) quand c'est possible |
| Départs | Compte désactivé le jour du départ (procédure RH → IT), supprimé après 90 jours |

## 7. Postes et serveurs Windows (GPO)

- **Protection du poste**
  - Microsoft Defender actif, pare-feu Windows actif sur tous les profils.
  - BitLocker sur les portables, clés de récupération sauvegardées dans AD.
  - Verrouillage de session après 10 minutes d'inactivité.
- **Protocoles désactivés** : SMBv1, LLMNR, NetBIOS sur TCP/IP et NTLMv1. Signature SMB exigée.
- **Supports amovibles** : clés USB en lecture seule, sauf pour le pôle IT.
- **Droits utilisateur** : personne n'est administrateur de son poste. Les logiciels sont déployés par l'IT.
- **Serveurs**
  - Bureau à distance depuis le VLAN IT uniquement, avec NLA.
  - Rôles limités au nécessaire.
  - Audit des ouvertures de session et des accès aux dossiers Direction et AdminRH.

## 8. Serveur web (DMZ) et plateforme

- **Système**
  - Linux minimal, SSH par clé uniquement (mot de passe et root interdits), depuis le VLAN IT seulement.
  - Pare-feu local (nftables) en plus du pare-feu périmétrique.
  - Fail2ban sur SSH.
- **Conteneurs**
  - L'application et PostgreSQL tournent sous Docker.
  - La base n'est jamais exposée : elle n'écoute que sur le réseau Docker interne.
  - Les secrets sont dans un fichier `.env` hors du dépôt Git.
- **Application** (déjà en place dans le code)
  - Mots de passe hachés en Argon2id.
  - Session par JWT dans un cookie `HttpOnly` et `SameSite=Lax`, avec une vérification d'origine contre les requêtes intersites (CSRF).
  - En-têtes de sécurité : CSP stricte, `X-Frame-Options: DENY`, entre autres.
  - Les rôles (client, agent, manager, admin) sont vérifiés côté serveur.
- **HTTPS**
  - Certificat Let's Encrypt renouvelé automatiquement, TLS 1.2 minimum.
  - HSTS activé une fois le domaine définitif en place.
- **Tentatives de connexion** :
  - l'application bloque un couple adresse IP / adresse e-mail après 5 échecs en 15 minutes ;
  - le compteur est en mémoire, donc propre à chaque instance de l'application. Si la plateforme tourne sur plusieurs instances (montée en charge dans Azure), il faut le déplacer dans un stockage partagé, par exemple Redis.

## 9. Mises à jour

| Élément | Méthode | Rythme |
|---|---|---|
| Postes Windows | Windows Update pour entreprises (GPO), deux anneaux : pôle IT d'abord, tous les postes 7 jours après | Mensuel (Patch Tuesday) ; correctifs critiques sous 72 h |
| Serveurs Windows | Fenêtre de maintenance, après instantané de la VM et sauvegarde | Mensuel, le week-end suivant le Patch Tuesday |
| Serveur Linux (DMZ) | `unattended-upgrades` pour les correctifs de sécurité ; images Docker reconstruites | Quotidien (sécurité) · hebdomadaire (images) |
| Pare-feu | Mise à jour du firmware, sauvegarde de configuration avant | Mensuel, ou sous 72 h pour une faille critique |
| Switchs, bornes Wi-Fi, imprimantes | Firmware | Trimestriel |

Suivi des vulnérabilités : abonnement aux bulletins du CERT-FR et des éditeurs ; inventaire
des versions tenu par l'IT.

## 10. Wi-Fi

- **Réseau du personnel** : WPA3-Entreprise. Authentification 802.1X par compte AD, via le rôle NPS de SRV-AIX-01 (serveur RADIUS de Windows). Les postes placés dans le VLAN de leur pôle.
- **Réseau invités** :
  - WPA2/WPA3 avec une clé changée chaque mois, ou un portail captif ;
  - isolation entre les appareils connectés ;
  - débit limité, Internet uniquement.

## 11. Sauvegarde et continuité

Résumé, détaillé dans le plan de sauvegarde et de supervision :
- **Règle 3-2-1** : 3 copies, sur 2 supports, dont 1 hors site. Les copies sont la production, le NAS du siège, puis Azure (versionnage et suppression réversible à 30 jours) et un disque USB conservé déconnecté, hors du siège.
- **Restauration** : un test de restauration chaque trimestre.
- **Pare-feu** : configuration exportée à chaque modification.

## 12. Utilisateurs et incidents

- **Charte informatique** signée à l'arrivée, avec une sensibilisation annuelle (hameçonnage, mots de passe, verrouillage du poste).
- **Procédure d'incident**, à suivre dans l'ordre :
  1. Isoler le poste ou le port réseau concerné.
  2. Prévenir l'IT et la Direction.
  3. Conserver les journaux.
  4. Changer les secrets exposés.
  5. Restaurer depuis une sauvegarde saine.
  6. Notifier la CNIL sous 72 h si des données personnelles sont touchées (RGPD).
- **Revue annuelle** : la matrice des droits, les règles de pare-feu et cette politique sont relues chaque année, ainsi qu'après chaque incident.
