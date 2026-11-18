# Solution cloud — Microsoft Azure

Livrable INFRA · Solution cloud. S'appuie sur le [plan d'adressage](01-plan-adressage-ip.md)
(plage réservée `10.100.0.0/16`), la [politique de sécurité](03-politique-securite.md) et le
[plan de sauvegarde et de supervision](05-plan-sauvegarde-supervision.md), dont elle traite
les limites (§ 6 de ce plan).

## 1. Pourquoi le cloud, et pour quoi faire

Ymmo ne déménage pas tout dans le cloud. Le siège garde ses serveurs pour ce qui doit
rester proche des utilisateurs : l'ouverture de session, les dossiers partagés et
l'impression. Azure prend en charge ce qui gagne à être hors du siège :

| Besoin | Problème aujourd'hui | Réponse Azure |
|---|---|---|
| **Plateforme Ymmo** (site public, espace client, outils des agents) | Hébergée dans la DMZ du siège : si le siège perd Internet ou brûle, les 12 agences et les clients perdent la plateforme | Hébergement PaaS : App Service + PostgreSQL managé, disponibilité 99,95 % garantie par contrat (SLA), sans dépendre du siège |
| **Annuaire** | Un seul contrôleur de domaine | Second contrôleur de domaine dans Azure, relié par VPN : les agences continuent d'ouvrir leur session si SRV-AIX-01 tombe |
| **Sauvegardes hors site** | Il fallait une copie hors du siège | Stockage Blob pour Hyper Backup (déjà prévu dans le plan de sauvegarde) |
| **Supervision externe** | La supervision interne ne voit pas une coupure Internet du siège | Test de disponibilité Azure Monitor |

Le modèle est donc **hybride** : un réseau Azure relié au siège comme une 14ᵉ agence.

### Pourquoi Azure plutôt qu'AWS

| Critère | Azure | AWS |
|---|---|---|
| Annuaire Windows existant | Intégration naturelle (Entra ID, Entra Connect), licences Windows Server réutilisables (Azure Hybrid Benefit) | Possible, mais moins intégré |
| Région en France | France Central (Paris), secours France South (Marseille) | Paris (eu-west-3) |
| Compétences de l'IT d'Ymmo | Windows Server, PowerShell : la console et les outils sont les mêmes | Nouvel écosystème à apprendre |
| PostgreSQL managé, conteneurs managés | Oui (Flexible Server, App Service) | Oui (RDS, App Runner / ECS) |

Les deux conviennent techniquement. L'environnement Windows d'Ymmo fait pencher pour Azure.

### RGPD

- Toutes les ressources sont en **France Central**, avec la France South comme région de secours pour les sauvegardes géo-redondantes. Les données des clients restent donc en France.
- Microsoft est sous-traitant au sens du RGPD : son avenant de protection des données (DPA) est inclus dans le contrat Azure.

## 2. Architecture

```
                                    Internet
                   clients, agents ─────┼──────────── HTTPS ────────────┐
                                        │                               ▼
  ┌─ Siège (Aix) ───────────────┐       │        ┌─ Azure · France Central · rg-ymmo-prod ─────────────────────┐
  │ FW-AIX 203.0.113.10         │  IPSec IKEv2   │  app-ymmo (App Service, conteneur)  ──▶ psql-ymmo (PostgreSQL)│
  │  ├ 10.0.0.0/16 (siège)      ├────────────────┤        │ intégration VNet                 accès privé       │
  │  └ transit vers les agences │                │  vnet-ymmo-hub 10.100.0.0/16                                  │
  └─────────────▲───────────────┘                │   ├ GatewaySubnet   10.100.0.0/27   vpngw-ymmo                │
                │ IPSec (existants)              │   ├ snet-identity   10.100.1.0/24   SRV-AZ-01 10.100.1.10 (DC) │
   12 agences 10.1–12.0.0/16                     │   ├ snet-app        10.100.2.0/24   (sortie de app-ymmo)      │
                                                 │   ├ snet-data       10.100.3.0/24   psql-ymmo (délégué)       │
                                                 │   └ snet-endpoints  10.100.4.0/24   points de terminaison privés│
                                                 │  stymmobackup (Blob : Hyper Backup) · stymmoapp (Files : photos)│
                                                 │  kv-ymmo (secrets) · log-ymmo (journaux) · Azure Backup        │
                                                 └───────────────────────────────────────────────────────────────┘
```

### 2.1 Ressources

Convention de nommage Microsoft (*Cloud Adoption Framework*) : `<type>-ymmo-<rôle>`.
Groupe de ressources unique : `rg-ymmo-prod`.

| Ressource | Nom | Offre (SKU) | Rôle |
|---|---|---|---|
| Réseau virtuel | `vnet-ymmo-hub` | — | `10.100.0.0/16`, sous-réseaux ci-dessus, DNS = `10.100.1.10`, `10.0.60.10` |
| Passerelle VPN | `vpngw-ymmo` | VpnGw1AZ (redondante entre zones) | Tunnel IPSec vers FW-AIX |
| Passerelle de réseau local | `lgw-aix` | — | Représente le siège : IP `203.0.113.10`, réseaux `10.0.0.0/12` (siège et 12 agences) |
| Machine virtuelle | `SRV-AZ-01` | B2s (2 vCPU, 4 Go), Windows Server 2022, disque SSD standard | Second contrôleur de domaine, DNS ; **aucune IP publique** |
| Plan App Service | `asp-ymmo` | Linux B2 (2 cœurs, 3,5 Go) | Héberge la plateforme |
| Application web | `app-ymmo` | Conteneur Docker | L'image construite depuis le `Dockerfile` du dépôt |
| Registre de conteneurs | `acrymmo` | Basic | Images de la plateforme, alimentées par la CI GitHub |
| PostgreSQL | `psql-ymmo` | Flexible Server, Burstable B1ms, 32 Go, PostgreSQL 16 | Base de la plateforme, accès privé uniquement |
| Stockage | `stymmoapp` | Standard LRS, partage Azure Files `media` | Photos des biens, monté dans le conteneur |
| Stockage | `stymmobackup` | Standard GRS, niveau Cool | Cible Hyper Backup du NAS |
| Coffre de clés | `kv-ymmo` | Standard | `SECRET_KEY`, mot de passe PostgreSQL |
| Espace Log Analytics | `log-ymmo` | Paiement à l'usage, rétention 90 jours | Journaux d'App Service, de PostgreSQL et de la VM |
| Coffre Recovery Services | `rsv-ymmo` | — | Azure Backup de `SRV-AZ-01` |

### 2.2 Réseau et VPN

Le VPN reprend les paramètres de la politique de sécurité (§ 5). Azure les accepte en
« stratégie IPsec personnalisée » :

```bash
RG=rg-ymmo-prod; LOC=francecentral
az group create -n $RG -l $LOC
az network vnet create -g $RG -n vnet-ymmo-hub --address-prefixes 10.100.0.0/16 \
    --subnet-name GatewaySubnet --subnet-prefixes 10.100.0.0/27 --dns-servers 10.100.1.10 10.0.60.10
for s in "snet-identity 10.100.1.0/24" "snet-app 10.100.2.0/24" "snet-data 10.100.3.0/24" "snet-endpoints 10.100.4.0/24"; do
    set -- $s; az network vnet subnet create -g $RG --vnet-name vnet-ymmo-hub -n $1 --address-prefixes $2
done
az network public-ip create -g $RG -n pip-vpngw-ymmo --sku Standard --zone 1 2 3
az network vnet-gateway create -g $RG -n vpngw-ymmo --vnet vnet-ymmo-hub --public-ip-addresses pip-vpngw-ymmo \
    --gateway-type Vpn --vpn-type RouteBased --sku VpnGw1AZ        # environ 30 à 45 min
az network local-gateway create -g $RG -n lgw-aix --gateway-ip-address 203.0.113.10 \
    --local-address-prefixes 10.0.0.0/12
az network vpn-connection create -g $RG -n cn-aix --vnet-gateway1 vpngw-ymmo --local-gateway2 lgw-aix \
    --shared-key "$(openssl rand -base64 24)"
az network vpn-connection ipsec-policy add -g $RG --connection-name cn-aix \
    --ike-encryption GCMAES256 --ike-integrity SHA256 --dh-group ECP256 \
    --ipsec-encryption GCMAES256 --ipsec-integrity GCMAES256 --pfs-group ECP256 \
    --sa-lifetime 3600 --sa-max-size 102400000
```

- **Le préfixe `10.0.0.0/12`** couvre `10.0.0.0` à `10.15.255.255`, soit le siège et les 12 agences, en une seule entrée. Il laisse de la place pour 3 agences de plus.
- **Côté FW-AIX** : une connexion IPSec de plus vers l'IP publique de `vpngw-ymmo`, avec les mêmes paramètres. Phase 2 : `10.0.0.0/12 ↔ 10.100.0.0/16`.
- **Côté agences** : une phase 2 de plus dans le tunnel existant vers le siège, `10.N.0.0/16 ↔ 10.100.0.0/16`. FW-AIX fait transiter le trafic, et les agences n'ont pas de tunnel direct vers Azure.
- **Filtrage**
  - Un groupe de sécurité réseau (NSG) par sous-réseau.
  - `snet-identity` n'accepte que les ports Active Directory (cf. politique de sécurité, règle 2) depuis `10.0.0.0/12`, et le RDP depuis le VLAN IT `10.0.50.0/24`.
  - Tout le reste venant d'Internet est refusé. La VM n'a pas d'IP publique : on l'administre à travers le VPN, sans Azure Bastion (environ 130 €/mois de plus).

> Dans la maquette VM, le tunnel vers Azure ne peut pas être monté : `203.0.113.10` est une
> adresse de documentation, non routable sur Internet. La démonstration du cloud se fait
> donc sur la plateforme, voir § 5.

### 2.3 Second contrôleur de domaine (SRV-AZ-01)

```powershell
# Sur SRV-AZ-01 (IP fixe 10.100.1.10 définie dans Azure, DNS 10.0.60.10 pour la promotion)
Install-WindowsFeature AD-Domain-Services, DNS -IncludeManagementTools
Install-ADDSDomainController -DomainName 'ad.ymmo.fr' -InstallDns -SiteName 'Azure' `
    -Credential (Get-Credential 'YMMO\Administrateur') `
    -SafeModeAdministratorPassword (Read-Host -AsSecureString 'Mot de passe DSRM')
```

- **Avant la promotion**, sur SRV-AIX-01 : créer le site AD et son sous-réseau, pour que les postes s'authentifient sur le contrôleur le plus proche.

  ```powershell
  New-ADReplicationSite Azure
  New-ADReplicationSubnet -Name '10.100.0.0/16' -Site Azure
  New-ADReplicationSiteLink -Name 'Aix-Azure' -SitesIncluded 'Default-First-Site-Name', 'Azure' -Cost 100 -ReplicationFrequencyInMinutes 15
  ```

- **DHCP** : la deuxième adresse DNS distribuée devient `10.100.1.10`, au siège comme en agence. Une agence peut ainsi ouvrir des sessions même si SRV-AIX-01 est arrêté, tant que son tunnel vers le siège fonctionne.
- **Disques de la VM** : sur un contrôleur de domaine Azure, le disque de données qui porte la base AD (`NTDS`) doit avoir le **cache d'hôte désactivé** (recommandation Microsoft).
- **Vérification** :

  ```powershell
  repadmin /replsummary      # 0 échec
  dcdiag /s:SRV-AZ-01        # tous les tests réussis
  ```

### 2.4 Plateforme Ymmo (PaaS)

| Paramètre de `app-ymmo` | Valeur |
|---|---|
| Image | `acrymmo.azurecr.io/ymmo:<version>`, tirée avec l'identité managée de l'application (pas de mot de passe de registre) |
| Port | `WEBSITES_PORT=8000` |
| Variables | `APP_ENV=production`, `APP_DEBUG=false`, `SEED_ON_STARTUP=false`, `POSTGRES_HOST=psql-ymmo.postgres.database.azure.com`, `POSTGRES_USER`, `POSTGRES_DB` |
| Secrets | `SECRET_KEY` et `POSTGRES_PASSWORD` en références Key Vault : `@Microsoft.KeyVault(SecretUri=https://kv-ymmo.vault.azure.net/secrets/…)`. Ils n'apparaissent ni dans le dépôt, ni dans la configuration |
| Stockage | Partage Azure Files `stymmoapp/media` monté sur `/app/media`, pour que les photos survivent aux redéploiements |
| Contrôle d'intégrité | `/api/health/db` : une instance qui ne répond plus est remplacée automatiquement |
| Réseau | Intégration VNet sur `snet-app`, pour joindre PostgreSQL en privé. HTTPS uniquement, TLS 1.2 minimum, certificat managé gratuit pour le domaine personnalisé |
| Déploiement | Emplacement *staging* + échange (*swap*) : la nouvelle version est testée avant de recevoir le trafic, sans coupure. Retour arrière par un nouvel échange |

- **PostgreSQL**
  - Accès privé : `psql-ymmo` est dans `snet-data`, sans adresse publique. Seule l'application peut l'atteindre.
  - Le chiffrement TLS est imposé par Azure, et l'application le négocie automatiquement.
  - Sauvegardes automatiques gérées par Azure, avec rétention de 14 jours et restauration à la minute près (*point-in-time restore*). Cela remplace le script `ymmo-backup-db.sh` utilisé sur SRV-AIX-02.
- **Chaîne de déploiement** : la CI GitHub existante (ruff, pytest) gagne une étape. À chaque fusion sur `main`, elle construit l'image, la pousse dans `acrymmo`, puis déploie sur l'emplacement *staging*. L'échange vers la production reste manuel.

## 3. Sécurité et administration

| Sujet | Mesure |
|---|---|
| Comptes Azure | Comptes Entra ID nominatifs, **double authentification obligatoire** (exigée par Microsoft pour le portail Azure) |
| Rôles (RBAC) | *Propriétaire* : 2 comptes (DSI et son suppléant) · *Contributeur* sur `rg-ymmo-prod` : le pôle IT · *Lecteur* des coûts : la Direction. Aucun droit à un compte personnel non nominatif |
| Secrets | Key Vault uniquement ; l'application y accède avec son identité managée |
| Réseau | VM et base sans IP publique, NSG par sous-réseau, journaux de flux des NSG dans `log-ymmo` |
| Protection | Microsoft Defender for Cloud (niveau gratuit) : score de sécurité et recommandations ; verrou « suppression interdite » sur le groupe de ressources |
| Budget | Budget mensuel Azure avec alerte à 80 % et 100 % envoyée à l'IT et à la Direction |

## 4. Coûts estimés

Ordre de grandeur mensuel, région France Central, sans engagement, hors TVA. Ces chiffres
sont **à recalculer avec la calculatrice de prix Azure** au moment de la commande : les
tarifs évoluent.

| Ressource | Offre | €/mois (environ) |
|---|---|---|
| Passerelle VPN | VpnGw1AZ | 140 |
| SRV-AZ-01 | B2s Windows + disque 128 Go | 50 |
| App Service | Linux B2 | 25 |
| PostgreSQL | Flexible B1ms, 32 Go, sauvegardes | 20 |
| Stockage sauvegardes | Blob Cool GRS, environ 1 To | 25 |
| Azure Files + registre de conteneurs | 100 Go + ACR Basic | 10 |
| Azure Backup (SRV-AZ-01) | 1 instance | 15 |
| Key Vault, Log Analytics, Azure Monitor | Faible volume | 10 |
| **Total** | | **≈ 300 €/mois, soit ≈ 3 600 €/an** |

Leviers d'économie :

- **Engagement sur 1 ou 3 ans** (instances réservées, *savings plan*) : de −30 à −60 % sur la VM, l'App Service et PostgreSQL.
- **Azure Hybrid Benefit** : si Ymmo possède des licences Windows Server avec Software Assurance, la licence Windows de la VM n'est plus facturée.
- **Passerelle VPN** : c'est près de la moitié de la facture. On peut la remplacer par une VM OPNsense dans Azure (environ 15 €/mois), au prix d'un équipement de plus à maintenir. C'est à réévaluer après un an.

## 5. Migration et démonstration

### Étapes

| Phase | Contenu | Coupure |
|---|---|---|
| 1 | Groupe de ressources, réseau, passerelle VPN, tunnel avec FW-AIX | Aucune |
| 2 | SRV-AZ-01 promu contrôleur de domaine, site AD, deuxième DNS en DHCP | Aucune |
| 3 | Stockage des sauvegardes, Hyper Backup vers Azure | Aucune |
| 4 | Plateforme : PostgreSQL, App Service, registre ; recette sur l'emplacement *staging* avec une copie de la base | Aucune |
| 5 | Bascule : site en maintenance, `pg_dump` de SRV-AIX-02, `pg_restore` dans `psql-ymmo`, copie des photos vers Azure Files, DNS public pointé vers App Service | Environ 30 min, un soir |
| 6 | SRV-AIX-02 conservé 1 mois en secours, puis décommissionné : la DMZ du siège n'héberge plus rien d'exposé | Aucune |

### Pendant la soutenance

- **Plateforme** : si un abonnement Azure étudiant (Azure for Students, 100 $ de crédit) est disponible, déployer `app-ymmo` et `psql-ymmo` (phase 4) et montrer :
  - le site en ligne en HTTPS ;
  - le contrôle d'intégrité `/api/health/db` ;
  - les secrets dans Key Vault ;
  - la base sans accès public.
- **Sinon** : le portail Azure, la calculatrice de prix et ce document.
- **VPN et second contrôleur de domaine** : ils ne sont pas démontrables avec la maquette, qui n'a pas d'adresse publique routable. On les présente avec le schéma et les commandes ci-dessus.
