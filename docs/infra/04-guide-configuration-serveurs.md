# Guide de configuration des serveurs — Ymmo

Livrable INFRA · Guide de configuration des serveurs. Il suit l'ordre de montage de la
maquette VM (§ 6 du [plan d'adressage](01-plan-adressage-ip.md)) ; en production, on
applique les mêmes étapes avec les VLAN 802.1Q au lieu de cartes réseau séparées.
Documents liés : [droits d'accès](02-gestion-droits-acces.md),
[politique de sécurité](03-politique-securite.md).

## 0. Vue d'ensemble

| Ordre | VM | Système | vCPU / RAM / disque | Cartes réseau (VirtualBox, « réseau interne ») |
|---|---|---|---|---|
| 1 | FW-AIX | OPNsense 24.x | 1 / 2 Go / 20 Go | 1 `net-internet` · 2 `aix-vlan60` · 3 `aix-vlan20` · (4 `aix-vlan100`, option) · (5 NAT VirtualBox, option : vrai Internet) |
| 2 | SRV-AIX-01 | Windows Server 2022 Standard | 2 / 4 Go / 60 Go (+ disque D: 20 Go) | `aix-vlan60` |
| 3 | PC-AIX-01 | Windows 10/11 Pro | 2 / 4 Go / 50 Go | `aix-vlan20` |
| 4 | FW-MRS | OPNsense 24.x | 1 / 2 Go / 20 Go | 1 `net-internet` · 2 `mrs-vlan20` |
| 5 | PC-MRS-01 | Windows 10/11 Pro | 2 / 4 Go / 50 Go | `mrs-vlan20` |
| option | SRV-AIX-02 | Debian 12 + Docker | 2 / 2 Go / 20 Go | `aix-vlan100` |

- **Minimum demandé par le sujet** : un serveur, une ou deux VM de site et un routeur. Il faut pourtant deux pare-feu, car un tunnel IPSec a besoin d'une extrémité de chaque côté.
- **Mémoire** : environ 14 Go pour les cinq VM. Avec moins, éteins PC-AIX-01 et ne montre que l'agence.
- **Windows 11** demande un TPM virtuel (VirtualBox 7 le propose). Windows 10 évite la question.
- **Instantanés** : un par VM après chaque étape validée (« FW configuré », « AD installé »…). Ils évitent de tout reprendre si la démo casse.

## 1. FW-AIX — pare-feu du siège (OPNsense)

### 1.1 Installation et interfaces

1. Installer OPNsense (image DVD), se connecter en `installer` / `opnsense`, installer sur
   le disque, changer le mot de passe root.
2. En console, option 1 *Assign interfaces* : WAN = carte 1, LAN = carte 2 ; option 2
   *Set interface IP address* :

| Interface | Nom | Adresse | Remarque |
|---|---|---|---|
| WAN | `WAN` | `203.0.113.10/24` | Pas de passerelle tant qu'il n'y a pas d'Internet réel |
| LAN | `SERVEURS` | `10.0.60.1/24` | Pas de DHCP (le DHCP est sur SRV-AIX-01) |
| OPT1 | `COMMERCIAL` | `10.0.20.1/24` | À assigner ensuite dans l'interface web |

3. Depuis une VM du réseau `aix-vlan60`, ouvrir `https://10.0.60.1` :
   - **Interfaces ▸ Assignments** : ajouter la 3ᵉ carte, la renommer `COMMERCIAL`, l'activer en `10.0.20.1/24` ;
   - **Interfaces ▸ WAN** : **décocher « Block bogon networks »**. `203.0.113.0/24` est une plage de documentation, classée « bogon » : sans ce décochage, le tunnel ne monte jamais dans la maquette. Laisser « Block private networks » coché.
   - **System ▸ Settings ▸ General** : nom `FW-AIX`, domaine `ad.ymmo.fr`, fuseau `Europe/Paris`.

> En production : une seule carte LAN en trunk, et un VLAN par pôle dans **Interfaces ▸
> Other Types ▸ VLAN** (tag 10, 20, 30, 40, 50, 60, 70, 90, 99, 100), chacun assigné avec
> l'adresse `10.0.<VLAN>.1/24`.

### 1.2 Sécurisation de l'administration

- **System ▸ Settings ▸ Administration** :
  - HTTPS uniquement ;
  - *Listen interfaces* = `SERVEURS` (en production : le VLAN IT) ;
  - SSH désactivé, ou par clé seulement.
- **System ▸ Access ▸ Servers** : ajouter un serveur *Local + Timebased One Time Password*. Puis **System ▸ Settings ▸ Administration ▸ Authentication** : utiliser ce serveur, pour imposer la double authentification.
- **System ▸ Access ▸ Users** : créer un compte nominatif par administrateur, ne plus utiliser `root`.

### 1.3 Alias et règles

**Firewall ▸ Aliases** :

| Alias | Type | Contenu |
|---|---|---|
| `RFC1918` | Network | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |
| `SRV_AD` | Host | `10.0.60.10` |
| `AD_PORTS` | Port | `53`, `88`, `123`, `135`, `389`, `445`, `464`, `636`, `3268:3269`, `49152:65535` |
| `WEB_PORTS` | Port | `80`, `443` |
| `PRINT_PORTS` | Port | `631`, `9100` |

**Firewall ▸ Rules ▸ COMMERCIAL** (de haut en bas ; la règle de refus par défaut termine
la liste) :

| Action | Protocole | Source | Destination | Port | Description |
|---|---|---|---|---|---|
| Pass | TCP/UDP | COMMERCIAL net | `SRV_AD` | `AD_PORTS` | Annuaire, DNS, partages |
| Pass | TCP | COMMERCIAL net | `10.0.100.10` | 443 | Plateforme Ymmo (si SRV-AIX-02) |
| Block | any | COMMERCIAL net | `RFC1918` | any | Rien d'autre vers le privé (journalisé) |
| Pass | TCP | COMMERCIAL net | any | `WEB_PORTS` | Navigation |

**Firewall ▸ Rules ▸ SERVEURS** :

| Action | Protocole | Source | Destination | Port | Description |
|---|---|---|---|---|---|
| Pass | TCP/UDP | `SRV_AD` | any (hors `RFC1918`) | 53, 123, 443 | Redirecteurs DNS, heure, mises à jour |
| Pass | any | SERVEURS net | SERVEURS address | any | Administration du pare-feu depuis le VLAN (maquette) |

**Firewall ▸ Rules ▸ WAN** : `Pass` UDP 500 et 4500, puis `Pass` ESP, avec pour source
`203.0.113.0/24` en maquette (en production, l'IP de chaque agence) et pour destination
WAN address. Ces règles laissent passer le VPN.

**Firewall ▸ Rules ▸ IPsec** : `Pass` TCP/UDP, source `10.1.0.0/16`, destination `SRV_AD`,
port `AD_PORTS`. Les agences n'atteignent que le contrôleur de domaine, et la plateforme
si elle existe.

NAT sortant : **Firewall ▸ NAT ▸ Outbound** en mode automatique, qui suffit.

### 1.4 Relais DHCP et DNS

- **Services ▸ DHCRelay** :
  - ajouter la destination `SRV-AD` (`10.0.60.10`) ;
  - ajouter un relais sur l'interface `COMMERCIAL` vers cette destination, puis l'activer.

  Les postes du VLAN 20 obtiennent ainsi leur adresse du DHCP Windows.
- **Services ▸ Unbound DNS ▸ Query Forwarding** : domaine `ad.ymmo.fr` → `10.0.60.10`. Le pare-feu sait ainsi résoudre l'annuaire, ce qui sert au contrôleur de domaine comme redirecteur.

## 2. SRV-AIX-01 — Windows Server (AD DS, DNS, DHCP, fichiers)

PowerShell en administrateur. Les commandes sont à lancer dans l'ordre ; deux étapes
redémarrent le serveur.

### 2.1 Système de base

```powershell
Rename-Computer -NewName 'SRV-AIX-01' -Restart
# après le redémarrage
New-NetIPAddress -InterfaceAlias 'Ethernet' -IPAddress 10.0.60.10 -PrefixLength 24 -DefaultGateway 10.0.60.1
Set-DnsClientServerAddress -InterfaceAlias 'Ethernet' -ServerAddresses 127.0.0.1
Set-TimeZone -Id 'Romance Standard Time'
# Disque D: pour les partages (disque 1 vierge)
Initialize-Disk -Number 1 -PartitionStyle GPT
New-Partition -DiskNumber 1 -UseMaximumSize -DriveLetter D | Format-Volume -FileSystem NTFS -NewFileSystemLabel 'Partages'
```

Puis appliquer les mises à jour Windows (Windows LAPS a besoin de la mise à jour
cumulative d'avril 2023 ou plus récente).

### 2.2 Active Directory et DNS

```powershell
Install-WindowsFeature AD-Domain-Services, DNS -IncludeManagementTools
Install-ADDSForest -DomainName 'ad.ymmo.fr' -DomainNetbiosName 'YMMO' -InstallDns `
    -SafeModeAdministratorPassword (Read-Host -AsSecureString 'Mot de passe DSRM') -Force
# le serveur redémarre en contrôleur de domaine ; se reconnecter en YMMO\Administrateur
```

```powershell
# Zones de recherche inversée (siège et agences)
Add-DnsServerPrimaryZone -NetworkId '10.0.0.0/16' -ReplicationScope Forest
1..12 | ForEach-Object { Add-DnsServerPrimaryZone -NetworkId "10.$_.0.0/16" -ReplicationScope Forest }
# Internet : via le résolveur du pare-feu (pas de DNS public direct depuis le LAN)
Set-DnsServerForwarder -IPAddress 10.0.60.1
# Nettoyage des enregistrements obsolètes
Set-DnsServerScavenging -ScavengingState $true -ApplyOnAllZones -ScavengingInterval 7.00:00:00
```

Le contrôleur de domaine est la source de temps du domaine. En production, il se cale sur
une source externe :

```powershell
w32tm /config /manualpeerlist:"0.fr.pool.ntp.org 1.fr.pool.ntp.org" /syncfromflags:manual /reliable:yes /update
```

### 2.3 DHCP (VLAN du siège)

```powershell
Install-WindowsFeature DHCP -IncludeManagementTools
Add-DhcpServerSecurityGroup ; Restart-Service DHCPServer
Add-DhcpServerInDC -DnsName 'srv-aix-01.ad.ymmo.fr' -IPAddress 10.0.60.10
# Options communes : DNS = contrôleur de domaine, suffixe ad.ymmo.fr
Set-DhcpServerv4OptionValue -DnsServer 10.0.60.10 -DnsDomain 'ad.ymmo.fr'
# Une étendue par VLAN de pôle : .100 à .199, passerelle .1, bail de 8 jours
foreach ($v in 10, 20, 30, 40, 50) {
    Add-DhcpServerv4Scope -Name "Siege VLAN $v" -StartRange "10.0.$v.100" -EndRange "10.0.$v.199" `
        -SubnetMask 255.255.255.0 -LeaseDuration 8.00:00:00 -State Active
    Set-DhcpServerv4OptionValue -ScopeId "10.0.$v.0" -Router "10.0.$v.1"
}
# Mise à jour DNS dynamique sécurisée des baux
Set-DhcpServerv4DnsSetting -DynamicUpdates Always -DeleteDnsRRonLeaseExpiry $true
```

- **Wi-Fi invités (VLAN 90)** : son DHCP est servi par le pare-feu, avec un DNS public. Il ne passe jamais par le contrôleur de domaine.
- **Agences** : chaque pare-feu d'agence sert son propre DHCP (§ 3).

### 2.4 Annuaire, droits et partages

Copier `infra/scripts/` sur le serveur (par exemple `C:\Ymmo\scripts`), puis :

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
.\01-New-YmmoAdStructure.ps1 -DemoPassword (Read-Host -AsSecureString 'Mot de passe des comptes de démo')
.\02-New-YmmoShares.ps1
.\03-Test-YmmoAccess.ps1     # doit afficher « Conforme a la matrice des droits »
```

Les choix (AGDLP, NTFS, énumération basée sur l'accès) sont expliqués dans le
[plan de gestion des droits](02-gestion-droits-acces.md).

### 2.5 Stratégie de mots de passe

```powershell
Set-ADDefaultDomainPasswordPolicy -Identity 'ad.ymmo.fr' -MinPasswordLength 12 -ComplexityEnabled $true `
    -PasswordHistoryCount 12 -MaxPasswordAge 0.00:00:00 `
    -LockoutThreshold 5 -LockoutDuration 00:15:00 -LockoutObservationWindow 00:15:00
```

Un `MaxPasswordAge` à 0 signifie qu'il n'y a pas d'expiration forcée (cf. politique de
sécurité, § 6). Pour les comptes `adm.*`, une stratégie affinée (PSO) impose 16 caractères.

### 2.6 Stratégies de groupe (GPO)

| GPO | Liée à | Contenu |
|---|---|---|
| `Ymmo - Securite postes` | OU `Ordinateurs` | LLMNR désactivé, signature SMB exigée, pare-feu Windows actif, Windows LAPS, clés USB en lecture seule |
| `Ymmo - Session utilisateurs` | OU `Utilisateurs` | Verrouillage de session à 10 min, lecteurs réseau |
| `Ymmo - Imprimante <agence>` | OU `Ordinateurs/Agences/<code>` | Imprimante de l'agence (`10.N.70.10`) |
| `Ymmo - Audit serveurs` | OU `Domain Controllers` | Audit des ouvertures de session et des accès aux objets |

Création des paramètres qui se scriptent (valeurs de registre) :

```powershell
$dn = (Get-ADDomain).DistinguishedName
$computers = "OU=Ordinateurs,OU=Ymmo,$dn"
$users = "OU=Utilisateurs,OU=Ymmo,$dn"

New-GPO -Name 'Ymmo - Securite postes' | New-GPLink -Target $computers
$g = 'Ymmo - Securite postes'
# LLMNR désactivé (empoisonnement de résolution de noms)
Set-GPRegistryValue -Name $g -Key 'HKLM\Software\Policies\Microsoft\Windows NT\DNSClient' -ValueName EnableMulticast -Type DWord -Value 0
# Signature SMB exigée côté client
Set-GPRegistryValue -Name $g -Key 'HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters' -ValueName RequireSecuritySignature -Type DWord -Value 1
# Clés USB : lecture seule
Set-GPRegistryValue -Name $g -Key 'HKLM\Software\Policies\Microsoft\Windows\RemovableStorageDevices\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}' -ValueName Deny_Write -Type DWord -Value 1
# Windows LAPS : mot de passe administrateur local unique, sauvegardé dans AD, changé tous les 30 jours
Set-GPRegistryValue -Name $g -Key 'HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\LAPS' -ValueName BackupDirectory -Type DWord -Value 2
Set-GPRegistryValue -Name $g -Key 'HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\LAPS' -ValueName PasswordAgeDays -Type DWord -Value 30
Update-LapsADSchema -Confirm:$false
Set-LapsADComputerSelfPermission -Identity $computers

New-GPO -Name 'Ymmo - Session utilisateurs' | New-GPLink -Target $users
$u = 'Ymmo - Session utilisateurs'
$k = 'HKCU\Software\Policies\Microsoft\Windows\Control Panel\Desktop'
Set-GPRegistryValue -Name $u -Key $k -ValueName ScreenSaveActive -Type String -Value '1'
Set-GPRegistryValue -Name $u -Key $k -ValueName ScreenSaverIsSecure -Type String -Value '1'
Set-GPRegistryValue -Name $u -Key $k -ValueName ScreenSaveTimeOut -Type String -Value '600'
```

Paramètres à régler dans la console de gestion des stratégies de groupe (GPMC), car ils ne
se scriptent pas simplement :

- **Lecteurs réseau**
  - Chemin : `Ymmo - Session utilisateurs` ▸ Configuration utilisateur ▸ Préférences ▸ Paramètres Windows ▸ Mappages de lecteurs.
  - Un mappage par dossier, vers `\\SRV-AIX-01\Partages\<dossier>` : `R:` Direction, `S:` Commercial, `T:` CommMarketing, `U:` AdminRH, `V:` IT. Action « Mettre à jour ».
  - Onglet *Commun* ▸ *Ciblage au niveau de l'élément* : appartenance au groupe `DL_<dossier>_RW` **ou** `DL_<dossier>_R`.

  Chacun ne reçoit ainsi que les lecteurs auxquels il a droit.
- **Exception USB pour l'IT** : dans `Ymmo - Securite postes` ▸ Délégation, refuser « Appliquer la stratégie de groupe » à un groupe `GG_Postes_IT` (ordinateurs du pôle IT).
- **Audit** : `Ymmo - Audit serveurs` ▸ Configuration de la stratégie d'audit avancée.
  - Ouverture de session : succès et échec.
  - Système de fichiers : succès et échec.
  - Puis, sur `D:\Partages\Direction` et `D:\Partages\AdminRH` : Propriétés ▸ Sécurité ▸ Avancé ▸ Audit ▸ Tout le monde, écriture et suppression.

Vérification sur un poste : `gpupdate /force` puis `gpresult /r`. Les deux GPO doivent
apparaître dans la liste « Objets de stratégie de groupe appliqués ».

## 3. FW-MRS — pare-feu d'agence (OPNsense)

Mêmes étapes d'installation et de sécurisation que FW-AIX (§ 1.1 et 1.2), avec :

| Interface | Nom | Adresse |
|---|---|---|
| WAN | `WAN` | `203.0.113.11/24` (« Block bogon networks » décoché) |
| LAN | `COMMERCIAL` | `10.1.20.1/24` |

- **Services ▸ ISC DHCPv4 ▸ COMMERCIAL** (ou Kea DHCP selon la version) :
  - plage `10.1.20.100` – `10.1.20.199` ;
  - DNS `10.0.60.10`, puis `10.1.20.1` en secours ;
  - domaine `ad.ymmo.fr`, passerelle `10.1.20.1`.
- **Services ▸ Unbound DNS ▸ Query Forwarding** : `ad.ymmo.fr` → `10.0.60.10`, à travers le tunnel. Le pare-feu résout alors l'annuaire, et cette entrée sert de secours.
- **Firewall ▸ Rules ▸ COMMERCIAL** :
  - Pass vers `10.0.0.0/16`, toutes destinations : le tri fin est fait par FW-AIX ;
  - Block vers `RFC1918` ;
  - Pass vers Internet sur `WEB_PORTS`.
- **Firewall ▸ Rules ▸ WAN** : UDP 500, 4500 et ESP depuis `203.0.113.10`.

## 4. Tunnel IPSec FW-AIX ↔ FW-MRS

Sur chaque pare-feu, **VPN ▸ IPsec ▸ Pre-Shared Keys**, puis **VPN ▸ IPsec ▸ Connections**
(le paramètre qui change d'un côté à l'autre est indiqué « AIX / MRS ») :

| Écran | Champ | Valeur |
|---|---|---|
| Pre-Shared Keys | Local / Remote identifier | `203.0.113.10` / `203.0.113.11` (inversé sur FW-MRS) |
| | Pre-Shared Key | 32 caractères aléatoires, identiques des deux côtés (`openssl rand -base64 24`) |
| Connection | Version | IKEv2 |
| | Proposals | `aes256gcm16-sha256-ecp256` |
| | Local / Remote addresses | `203.0.113.10` / `203.0.113.11` (inversé sur FW-MRS) |
| | DPD delay | 30 s |
| | Rekey time | 28 800 s (8 h) |
| Local authentication | Authentication / Id | Pre-Shared Key / IP WAN locale |
| Remote authentication | Authentication / Id | Pre-Shared Key / IP WAN distante |
| Child | Mode | Tunnel |
| | Local / Remote networks | `10.0.0.0/16` ↔ `10.1.0.0/16` (inversé sur FW-MRS) |
| | ESP proposals | `aes256gcm16-ecp256` (PFS groupe 19) |
| | Start action | Start (le tunnel monte sans attendre de trafic) |
| | Rekey time | 3 600 s |

Activer IPsec (**VPN ▸ IPsec ▸ Connections ▸ Enable**), puis vérifier dans **VPN ▸ IPsec
▸ Status Overview** : les phases 1 et 2 doivent être `ESTABLISHED` / `INSTALLED`.

Pour les 11 autres agences, on refait la même configuration en changeant seulement l'IP du
pair, le réseau `10.N.0.0/16` et la clé.

## 5. Postes clients

```powershell
# Siège (PC-AIX-01, VLAN 20) : DHCP via le relais -> adresse 10.0.20.1xx, DNS 10.0.60.10
# Agence (PC-MRS-01) : DHCP de FW-MRS -> 10.1.20.1xx, DNS 10.0.60.10 à travers le tunnel
ipconfig /all
nslookup ad.ymmo.fr                      # doit répondre 10.0.60.10
Add-Computer -DomainName 'ad.ymmo.fr' -Credential 'YMMO\Administrateur' `
    -OUPath 'OU=MRS,OU=Agences,OU=Ordinateurs,OU=Ymmo,DC=ad,DC=ymmo,DC=fr' -Restart
# (pour PC-AIX-01 : -OUPath 'OU=Siege,OU=Ordinateurs,OU=Ymmo,DC=ad,DC=ymmo,DC=fr')
```

Ouvrir ensuite une session avec un compte de démonstration (`j.roux` en agence,
`l.bernard` au siège).

## 6. SRV-AIX-02 — plateforme web en DMZ (option dans la maquette)

Debian 12 minimal, carte sur `aix-vlan100`. Sur FW-AIX, il faut assigner l'interface
`DMZ` (`10.0.100.1/24`), autoriser la DMZ à sortir vers Internet sur les ports 443 et 123,
bloquer la DMZ vers `RFC1918`, et ajouter la redirection de port (**Firewall ▸ NAT ▸ Port
Forward** : WAN TCP 443 → `10.0.100.10:443`).

```bash
# /etc/network/interfaces : address 10.0.100.10/24, gateway 10.0.100.1
# SSH : clé uniquement
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh
apt update && apt install -y ca-certificates curl git unattended-upgrades fail2ban nftables
dpkg-reconfigure -plow unattended-upgrades     # correctifs de sécurité automatiques
# Docker (dépôt officiel)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
# Application
git clone https://github.com/tahirylebg/ymmo.git /opt/ymmo && cd /opt/ymmo
cp .env.example .env    # SECRET_KEY et POSTGRES_PASSWORD : valeurs aléatoires longues, APP_DEBUG=false
docker compose up -d --build
```

- **Base de données** : PostgreSQL n'est pas exposée, puisque `docker-compose.yml` ne publie aucun port pour `db`.
- **Ports à ouvrir** :
  - l'application écoute en HTTP sur le port 8000 ;
  - devant elle, un proxy inverse Caddy termine HTTPS sur le 443, avec un certificat Let's Encrypt automatique une fois le nom de domaine public pointé vers `203.0.113.10` ;
  - nftables n'ouvre que le 443 (et le 80 pour la redirection) depuis tout réseau, plus le 22 depuis `10.0.50.0/24`.

## 7. Recette (à dérouler pendant la démonstration)

| # | Test | Commande / action | Résultat attendu |
|---|---|---|---|
| 1 | Tunnel actif | FW-AIX ▸ VPN ▸ IPsec ▸ Status | Phase 1 `ESTABLISHED`, phase 2 `INSTALLED` |
| 2 | Adressage agence | PC-MRS-01 : `ipconfig /all` | `10.1.20.1xx`, passerelle `10.1.20.1`, DNS `10.0.60.10` |
| 3 | DNS à travers le VPN | PC-MRS-01 : `nslookup srv-aix-01.ad.ymmo.fr` | `10.0.60.10` |
| 4 | Ouverture de session sur le domaine depuis l'agence | Session `YMMO\j.roux` | Session ouverte, lecteurs `S:` (Commercial) et `T:` (CommMarketing) |
| 5 | GPO appliquées | `gpresult /r` | `Ymmo - Securite postes` et `Ymmo - Session utilisateurs` |
| 6 | Droits en écriture | `j.roux` crée un fichier dans `S:` | Autorisé |
| 7 | Lecture seule | `j.roux` crée un fichier dans `T:` | Accès refusé |
| 8 | Dossier interdit invisible | `j.roux` ouvre `\\SRV-AIX-01\Partages` | Seuls Commercial et CommMarketing sont listés |
| 9 | Matrice complète | SRV-AIX-01 : `.\03-Test-YmmoAccess.ps1` | « Conforme a la matrice des droits » |
| 10 | Segmentation | PC-AIX-01 : `Test-NetConnection 10.0.60.1 -Port 443` | Échec (l'administration du pare-feu n'est pas ouverte au VLAN 20) |
| 11 | Journalisation | FW-AIX ▸ Firewall ▸ Log Files ▸ Live View | Le refus du test 10 apparaît |
| 12 | LAPS | SRV-AIX-01 : `Get-LapsADPassword -Identity PC-MRS-01 -AsPlainText` | Mot de passe administrateur local unique du poste |
