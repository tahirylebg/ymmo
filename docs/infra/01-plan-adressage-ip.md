# Plan d'adressage IP — réseau Ymmo

Livrable INFRA · Architecture réseau multi-sites. Schéma associé :
[`schema-reseau.drawio`](schema-reseau.drawio) (ouvrir avec draw.io / app.diagrams.net),
export image [`schema-reseau.png`](schema-reseau.png).

## 1. Principes

| Choix | Valeur | Pourquoi |
|---|---|---|
| Plage privée | `10.0.0.0/8` (RFC 1918) | Assez large pour 13 sites et l'extension cloud, sans chevauchement avec les box des employés en télétravail (souvent en `192.168.x.x`) |
| Un site = un `/16` | `10.<site>.0.0/16` | Une seule route (et un seul réseau IPSec) par agence : `10.0.0.0/16 ↔ 10.N.0.0/16` |
| Un VLAN = un `/24` | `10.<site>.<VLAN>.0/24` | L'adresse se lit : `10.4.20.37` = site 4 (Lyon), VLAN 20 (commercial). Le 3ᵉ octet est le numéro de VLAN partout |
| Segmentation | Un VLAN par pôle au siège | Applique la matrice des droits au niveau réseau aussi : les pôles ne se voient pas entre eux, le pare-feu filtre ce qui passe |
| Taille | `/24` (254 hôtes) même pour 5 postes | Scalabilité demandée : une agence peut tripler sans renuméroter. L'espace n'est pas une contrainte en `10/8` |
| Réservé cloud | `10.100.0.0/16` | VNet Azure (solution cloud hybride, VPN site à site avec le siège) |

### Convention dans chaque `/24`

| Plage | Usage |
|---|---|
| `.1` | Passerelle : interface VLAN du pare-feu du site |
| `.2` – `.9` | Équipements réseau (switchs, bornes Wi-Fi) |
| `.10` – `.49` | Adresses fixes (serveurs, imprimantes, NAS) |
| `.50` – `.99` | Réservations DHCP (postes qui doivent garder leur adresse) |
| `.100` – `.199` | Pool DHCP dynamique (100 baux) |
| `.200` – `.254` | Réserve |

## 2. Numéros de site

| Site | Code | Ville | Réseau | IP publique WAN¹ |
|---|---|---|---|---|
| 0 | AIX | Aix-en-Provence (siège) | `10.0.0.0/16` | `203.0.113.10` |
| 1 | MRS | Marseille Prado | `10.1.0.0/16` | `203.0.113.11` |
| 2 | NCE | Nice | `10.2.0.0/16` | `203.0.113.12` |
| 3 | LYS | Lyon Part-Dieu | `10.3.0.0/16` | `203.0.113.13` |
| 4 | PAR | Paris Bastille | `10.4.0.0/16` | `203.0.113.14` |
| 5 | BOD | Bordeaux | `10.5.0.0/16` | `203.0.113.15` |
| 6 | TLS | Toulouse Capitole | `10.6.0.0/16` | `203.0.113.16` |
| 7 | MPL | Montpellier | `10.7.0.0/16` | `203.0.113.17` |
| 8 | NTE | Nantes | `10.8.0.0/16` | `203.0.113.18` |
| 9 | LIL | Lille | `10.9.0.0/16` | `203.0.113.19` |
| 10 | SXB | Strasbourg | `10.10.0.0/16` | `203.0.113.20` |
| 11 | RNS | Rennes | `10.11.0.0/16` | `203.0.113.21` |
| 12 | GNB | Grenoble | `10.12.0.0/16` | `203.0.113.22` |
| — | Azure | VNet cloud (évolution) | `10.100.0.0/16` | passerelle VPN Azure |

¹ Adresses de documentation (RFC 5737) : elles seront remplacées par les IP fixes
fournies par l'opérateur de chaque site. La maquette VM utilise exactement ces valeurs
(§ 6), ce qui rend la démonstration fidèle au plan.

## 3. Siège — Aix-en-Provence (`10.0.0.0/16`)

| VLAN | Nom | Réseau | Passerelle | Hôtes prévus | Adressage |
|---|---|---|---|---|---|
| 10 | Direction | `10.0.10.0/24` | `10.0.10.1` | ≈ 4 postes | DHCP |
| 20 | Commercial | `10.0.20.0/24` | `10.0.20.1` | ≈ 10 postes | DHCP |
| 30 | Communication & Marketing | `10.0.30.0/24` | `10.0.30.1` | ≈ 6 postes | DHCP |
| 40 | Administration / RH | `10.0.40.0/24` | `10.0.40.1` | ≈ 6 postes | DHCP |
| 50 | IT & Support | `10.0.50.0/24` | `10.0.50.1` | ≈ 4 postes | DHCP |
| 60 | Serveurs | `10.0.60.0/24` | `10.0.60.1` | 2 serveurs internes + NAS | Fixe |
| 70 | Impression | `10.0.70.0/24` | `10.0.70.1` | 1 imprimante | Fixe |
| 90 | Wi-Fi invités | `10.0.90.0/24` | `10.0.90.1` | visiteurs | DHCP, Internet seul |
| 99 | Administration réseau | `10.0.99.0/24` | `10.0.99.1` | switchs, bornes Wi-Fi | Fixe |
| 100 | DMZ | `10.0.100.0/24` | `10.0.100.1` | serveur web public | Fixe |

Total : environ 30 postes, comme dans le brief client.

### Adresses fixes du siège

| Équipement | Rôle | Adresse |
|---|---|---|
| FW-AIX | Pare-feu / routeur, VPN IPSec (hub), NAT | `.1` de chaque VLAN · WAN `203.0.113.10` |
| SW-AIX-CORE | Switch cœur de niveau 3 (VLAN trunk) | `10.0.99.2` |
| SW-AIX-01 / 02 | Switchs d'accès | `10.0.99.3` / `10.0.99.4` |
| AP-AIX-01 / 02 | Bornes Wi-Fi | `10.0.99.5` / `10.0.99.6` |
| **SRV-AIX-01** | Windows Server : AD DS, DNS, DHCP, serveur de fichiers | `10.0.60.10` |
| NAS-AIX-01 | Sauvegardes (copie locale) | `10.0.60.20` |
| PRN-AIX-01 | Imprimante du siège | `10.0.70.10` |
| **SRV-AIX-02** | Linux + Docker : plateforme web Ymmo, PostgreSQL | `10.0.100.10` (DMZ) |

Les deux serveurs du brief sont SRV-AIX-01 (interne) et SRV-AIX-02 (DMZ). Le serveur
web est isolé en DMZ : il est exposé sur Internet (HTTPS) et ne doit pas pouvoir initier
de connexion vers le LAN.

## 4. Agences (`10.N.0.0/16`, N = 1 à 12)

Les 12 agences ont toutes le même gabarit : seul le 2ᵉ octet change.

| VLAN | Nom | Réseau | Passerelle | Hôtes | Adressage |
|---|---|---|---|---|---|
| 20 | Commercial | `10.N.20.0/24` | `10.N.20.1` | ≈ 5 postes | DHCP |
| 70 | Impression | `10.N.70.0/24` | `10.N.70.1` | 1 imprimante (`10.N.70.10`) | Fixe |
| 90 | Wi-Fi invités | `10.N.90.0/24` | `10.N.90.1` | visiteurs | DHCP, Internet seul |
| 99 | Administration réseau | `10.N.99.0/24` | `10.N.99.1` | switch `10.N.99.2`, borne Wi-Fi `10.N.99.5` | Fixe |

Les agences n'ont que des commerciaux : un seul VLAN de postes, numéroté 20 comme le
VLAN commercial du siège (mêmes règles de pare-feu partout).

Exemple Lyon (site 3) : postes `10.3.20.100` – `10.3.20.199`, imprimante `10.3.70.10`,
pare-feu `10.3.20.1`, tunnel IPSec `10.0.0.0/16 ↔ 10.3.0.0/16`.

## 5. Services réseau

| Service | Où | Détail |
|---|---|---|
| **DNS** | SRV-AIX-01 (`10.0.60.10`) | Zone Active Directory `ad.ymmo.fr` (sous-domaine du domaine public de l'entreprise, NetBIOS `YMMO`). Redirecteurs vers les résolveurs du pare-feu pour Internet. Les pare-feu d'agence relaient les requêtes `ad.ymmo.fr` au DC à travers le VPN |
| **DHCP siège** | SRV-AIX-01 | Une étendue par VLAN (10 à 50, 90), relais DHCP (`ip helper`) sur les interfaces VLAN du pare-feu. Options : passerelle `.1`, DNS `10.0.60.10`, domaine `ad.ymmo.fr` |
| **DHCP agences** | Pare-feu de l'agence | Servi localement : une agence garde le réseau si le VPN tombe. DNS distribué : `10.0.60.10` puis le pare-feu local en secours |
| **NAT** | Chaque pare-feu | NAT sortant (masquerade) des VLAN vers le WAN. Siège : redirection `443/tcp` (et `80` → redirection HTTPS) de `203.0.113.10` vers `10.0.100.10` |
| **VPN** | Topologie en étoile (hub = siège) | IPSec IKEv2, AES-256-GCM, SHA-256, DH groupe 14 minimum, clé pré-partagée par site (certificats en cible). Phase 2 : `10.0.0.0/16 ↔ 10.N.0.0/16`. Pas de trafic direct entre agences : elles n'en ont pas besoin, et tout passe par le filtrage du siège |
| **Internet des agences** | Sortie locale (split tunnel) | Seul le trafic vers `10.0.0.0/16` passe dans le tunnel ; la navigation sort par la ligne de l'agence, ce qui ne sature pas le lien du siège |

## 6. Maquette VM (démonstration)

Même plan, réduit au minimum demandé (1 serveur, 1 à 2 postes, routeur) : deux pare-feu
sont nécessaires pour monter un vrai tunnel IPSec entre deux sites.

| VM | Système | Réseaux (cartes) | Adresses |
|---|---|---|---|
| FW-AIX | pfSense / OPNsense | `net-internet`, `aix-vlan60`, `aix-vlan20` | `203.0.113.10/24`, `10.0.60.1/24`, `10.0.20.1/24` |
| FW-MRS | pfSense / OPNsense | `net-internet`, `mrs-vlan20` | `203.0.113.11/24`, `10.1.20.1/24` |
| SRV-AIX-01 | Windows Server 2022 | `aix-vlan60` | `10.0.60.10/24`, passerelle `10.0.60.1` |
| PC-AIX-01 | Windows 10/11 | `aix-vlan20` | DHCP (relais vers SRV-AIX-01) |
| PC-MRS-01 | Windows 10/11 | `mrs-vlan20` | DHCP de FW-MRS |

`net-internet` est un réseau interne VirtualBox (ou un switch privé Hyper-V) qui joue le
rôle d'Internet entre les deux pare-feu. Démonstrations possibles : PC-MRS-01 joint le
domaine `ad.ymmo.fr` à travers le tunnel, ouvre une session et reçoit ses GPO et ses
lecteurs réseau, tandis que l'accès au VLAN serveurs depuis un pôle non autorisé est
bloqué par le pare-feu.
