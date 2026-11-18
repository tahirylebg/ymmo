# Plan de gestion des droits d'accès — Ymmo

Livrable INFRA · Gestion des droits d'accès. S'appuie sur le
[plan d'adressage](01-plan-adressage-ip.md) (un VLAN par pôle au siège). Mise en œuvre
automatisée par les scripts de [`infra/scripts/`](../../infra/scripts/).

## 1. La matrice du brief

Lecture : **chaque ligne est un pôle (qui accède), chaque colonne un dossier (à quoi)**.
C'est la seule lecture cohérente : dans l'autre sens, la Direction n'aurait pas accès au
dossier Commercial alors que l'IT y aurait accès.

| Pôle ↓ / Dossier → | Direction | Commercial | Comm. & Mktg | Admin / RH | IT & Support |
|---|---|---|---|---|---|
| **Direction** | **RW** | R | R | R | R |
| **Commercial** | — | **RW** | R | — | — |
| **Comm. & Mktg** | — | R | **RW** | — | — |
| **Admin / RH** | — | R | R | **RW** | — |
| **IT & Support** | — | R | R | — | **RW** |

RW = lecture / écriture · R = lecture seule · — = interdit.

Les commerciaux des 12 agences appartiennent au pôle Commercial : ils ont les mêmes droits
que les commerciaux du siège, à travers le VPN.

## 2. Le modèle : AGDLP

Les droits ne sont jamais donnés à une personne, mais à des groupes, en deux niveaux :

```
A  Comptes            l.bernard, j.roux …
G  Groupes globaux    GG_Commercial  ⊃  GG_Commercial_MRS … GG_Commercial_GNB     « qui »
DL Groupes locaux     DL_Commercial_RW, DL_CommMarketing_R …                        « quoi »
P  Permissions NTFS   D:\Partages\Commercial : DL_Commercial_RW = modification
```

- Les **groupes globaux** (`GG_`) décrivent l'organisation : un par pôle, un par agence.
- Les **groupes de domaine local** (`DL_`) décrivent les ressources : un par dossier et
  par niveau de droit.
- La **matrice** se résume aux appartenances `GG_` → `DL_` (§ 4).

Conséquences pratiques :

| Événement | Action | Ce qu'on ne touche pas |
|---|---|---|
| Arrivée d'un salarié | Créer le compte dans l'OU de son pôle, l'ajouter à `GG_<pôle>` (ou `GG_Commercial_<agence>`) | Les ACL des dossiers |
| Changement de pôle | Changer son groupe global | Les ACL |
| Départ | Désactiver le compte, le retirer des groupes, le déplacer dans une OU d'archive | Les ACL |
| Nouvelle agence | Créer `GG_Commercial_<code>` et l'imbriquer dans `GG_Commercial` | Les ACL |
| Évolution de la matrice | Modifier `YmmoAccessMatrix.psd1`, relancer les scripts | Les comptes |

## 3. Annuaire Active Directory

Domaine `ad.ymmo.fr` (NetBIOS `YMMO`), contrôleur de domaine SRV-AIX-01 (`10.0.60.10`).

```
ad.ymmo.fr
└── Ymmo
    ├── Utilisateurs
    │   ├── Direction · Commercial · CommMarketing · AdminRH · IT     (siège, une OU par pôle)
    │   └── Agences
    │       └── MRS · NCE · LYS · PAR · BOD · TLS · MPL · NTE · LIL · SXB · RNS · GNB
    ├── Groupes
    │   ├── Globaux          GG_<pôle>, GG_Commercial_<agence>
    │   └── DomaineLocal     DL_<dossier>_RW, DL_<dossier>_R
    ├── Ordinateurs
    │   ├── Siege
    │   └── Agences / <code>                       (GPO par site : imprimante, lecteurs)
    ├── Serveurs
    └── Comptes-admin                              (comptes d'administration séparés)
```

Une OU par pôle et par agence permet de cibler les stratégies de groupe (GPO) : lecteurs
réseau, imprimante de l'agence, restrictions par profil.

## 4. Groupes

### Groupes globaux (qui)

| Groupe | Membres |
|---|---|
| `GG_Direction` | Comptes du pôle Direction |
| `GG_Commercial` | Commerciaux du siège + les 12 groupes `GG_Commercial_<agence>` |
| `GG_Commercial_MRS` … `GG_Commercial_GNB` | Commerciaux de chaque agence |
| `GG_CommMarketing` | Comptes du pôle Communication & Marketing |
| `GG_AdminRH` | Comptes du pôle Administration / RH |
| `GG_IT` | Comptes du pôle IT & Support |

### Groupes de domaine local (quoi) : la matrice

| Dossier | `DL_<dossier>_RW` (modification) | `DL_<dossier>_R` (lecture) | Interdit |
|---|---|---|---|
| Direction | `GG_Direction` | — | tous les autres |
| Commercial | `GG_Commercial` | `GG_Direction`, `GG_CommMarketing`, `GG_AdminRH`, `GG_IT` | — |
| CommMarketing | `GG_CommMarketing` | `GG_Direction`, `GG_Commercial`, `GG_AdminRH`, `GG_IT` | — |
| AdminRH | `GG_AdminRH` | `GG_Direction` | Commercial, Comm. & Mktg, IT |
| IT | `GG_IT` | `GG_Direction` | Commercial, Comm. & Mktg, Admin / RH |

## 5. Dossiers partagés

Sur SRV-AIX-01, un dossier par pôle, tous publiés par **un seul partage**,
`\\SRV-AIX-01\Partages` (`D:\Partages`) :

| Dossier | Chemin réseau |
|---|---|
| Direction | `\\SRV-AIX-01\Partages\Direction` |
| Commercial | `\\SRV-AIX-01\Partages\Commercial` |
| CommMarketing | `\\SRV-AIX-01\Partages\CommMarketing` |
| AdminRH | `\\SRV-AIX-01\Partages\AdminRH` |
| IT | `\\SRV-AIX-01\Partages\IT` |

Pourquoi un seul partage : l'énumération basée sur l'accès masque les dossiers **à
l'intérieur** d'un partage, pas la liste des partages du serveur. Avec un seul partage,
un commercial qui ouvre `\\SRV-AIX-01\Partages` ne voit que Commercial et CommMarketing.
La racine `D:\Partages` est seulement listable : personne ne peut y déposer de fichier.

Les lecteurs réseau sont connectés par GPO (préférences de lecteur, ciblées par groupe
global). Ce point est détaillé dans le guide de configuration des serveurs.

### Permissions

| Niveau | Règle |
|---|---|
| **Partage (SMB)** | Utilisateurs authentifiés : modifier · Administrateurs : contrôle total. Le filtrage fin est fait par NTFS (une seule source de vérité) |
| **NTFS** | Héritage coupé sur chaque dossier de pôle. SYSTEM et Administrateurs : contrôle total. `DL_…_RW` : **modification** du contenu (ils créent, modifient, suppriment les fichiers et sous-dossiers, mais ne peuvent ni supprimer ni renommer le dossier du pôle). `DL_…_R` : **lecture et exécution** |
| **Interdit** | Aucune autorisation, **pas de refus explicite** (Deny) : un refus l'emporte sur tout, et bloquerait par exemple un directeur qui serait aussi dans un autre groupe |
| **Énumération basée sur l'accès (ABE)** | Activée sur le partage : un utilisateur ne voit même pas les dossiers qu'il ne peut pas ouvrir |
| **Contrôle total** | Jamais donné aux utilisateurs : ils ne peuvent pas modifier les permissions |

## 6. Comptes d'administration et pôle IT

La matrice s'applique aux **comptes de travail**, y compris ceux du pôle IT : un technicien
n'a pas accès au dossier RH avec son compte quotidien.

- Chaque administrateur a un second compte nominatif `adm.<nom>` (OU `Comptes-admin`),
  utilisé seulement pour administrer, jamais pour la messagerie ou le web.
- Le compte `Administrateur` intégré est renommé, avec un mot de passe long conservé au coffre.
- Les accès aux dossiers sensibles (Direction, RH) sont audités (stratégie d'audit des accès
  aux objets, journal de sécurité de SRV-AIX-01).

## 7. Cohérence avec le réseau

Les droits sur les fichiers sont doublés par la segmentation réseau (détaillée dans la
politique de sécurité) :

- chaque VLAN de pôle et chaque agence atteint SRV-AIX-01 sur les seuls ports Active
  Directory, DNS et partage de fichiers (SMB 445) ;
- les VLAN de pôles ne communiquent pas entre eux ;
- le VLAN d'administration réseau (99) n'est joignable que depuis le VLAN IT.

## 8. Mise en œuvre et vérification

Sur SRV-AIX-01 (Windows Server, rôles AD DS et serveur de fichiers), en administrateur du
domaine, depuis `infra/scripts/` :

```powershell
# 1. OU, groupes globaux et locaux, appartenances de la matrice, comptes de démonstration
.\01-New-YmmoAdStructure.ps1 -DemoPassword (Read-Host -AsSecureString 'Mot de passe démo')
# 2. Dossiers, permissions NTFS, partage SMB avec ABE
.\02-New-YmmoShares.ps1            # -ShareRoot C:\Partages si la VM n'a pas de disque D:
# 3. Contrôle : affiche la matrice réellement en place, code de sortie 1 en cas d'écart
.\03-Test-YmmoAccess.ps1
```

- Les trois scripts lisent la même source, `YmmoAccessMatrix.psd1` : la matrice n'est
  écrite qu'une fois.
- Ils sont idempotents : on peut les relancer sans risque.
- Les comptes intégrés sont désignés par leur SID, si bien que les scripts fonctionnent
  aussi sur un Windows Server en français.

Comptes de démonstration (un par pôle, plus une commerciale d'agence) :

| Compte | Pôle | Démonstration |
|---|---|---|
| `c.martin` | Direction | Ouvre et lit tous les dossiers, n'écrit que dans Direction |
| `l.bernard` | Commercial (siège) | Écrit dans Commercial, lit CommMarketing, ne voit pas AdminRH (ABE) |
| `e.petit` | Comm. & Marketing | Écrit dans CommMarketing, lit Commercial |
| `s.durand` | Admin / RH | Écrit dans AdminRH, lit Commercial et CommMarketing |
| `n.moreau` | IT & Support | Écrit dans IT, ne voit ni Direction ni AdminRH |
| `j.roux` | Commercial, agence MRS | Depuis le poste de l'agence (via le VPN) : mêmes droits que `l.bernard` |
