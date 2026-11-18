#Requires -Modules ActiveDirectory
<#
.SYNOPSIS
    Ymmo - creates the AD structure of the access-rights plan: OUs, groups (AGDLP), demo users.
.DESCRIPTION
    Idempotent: what already exists is left as it is, so the script can be re-run after a change
    of YmmoAccessMatrix.psd1. Run on SRV-AIX-01 (domain controller) as a domain admin.
    A: accounts in pole/agency OUs  ->  G: GG_<pole> (GG_Commercial_<agency> nested into
    GG_Commercial)  ->  DL: DL_<folder>_RW / DL_<folder>_R  ->  P: NTFS rights (02-New-YmmoShares.ps1).
.EXAMPLE
    .\01-New-YmmoAdStructure.ps1 -DemoPassword (Read-Host -AsSecureString 'Mot de passe demo')
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][securestring]$DemoPassword,
    [switch]$SkipDemoUsers
)
$ErrorActionPreference = 'Stop'
$cfg = Import-PowerShellDataFile -Path (Join-Path $PSScriptRoot 'YmmoAccessMatrix.psd1')
$domainDN = (Get-ADDomain).DistinguishedName

function Add-YmmoOU([string]$Name, [string]$Path) {
    $dn = "OU=$Name,$Path"
    if (-not (Get-ADOrganizationalUnit -Filter "DistinguishedName -eq '$dn'")) {
        New-ADOrganizationalUnit -Name $Name -Path $Path -ProtectedFromAccidentalDeletion $true
        Write-Host "  + OU $dn"
    }
    return $dn
}

function Add-YmmoGroup([string]$Name, [string]$Scope, [string]$Path, [string]$Description) {
    if (-not (Get-ADGroup -Filter "Name -eq '$Name'")) {
        New-ADGroup -Name $Name -SamAccountName $Name -GroupScope $Scope -GroupCategory Security `
            -Path $Path -Description $Description
        Write-Host "  + groupe $Name ($Scope)"
    }
}

Write-Host '1. Unites d''organisation'
$root = Add-YmmoOU $cfg.BaseOU $domainDN
$usersOU = Add-YmmoOU 'Utilisateurs' $root
foreach ($pole in $cfg.Poles) { [void](Add-YmmoOU $pole.Key $usersOU) }
$agencyUsersOU = Add-YmmoOU 'Agences' $usersOU
foreach ($code in $cfg.Agencies) { [void](Add-YmmoOU $code $agencyUsersOU) }
$groupsOU = Add-YmmoOU 'Groupes' $root
$globalOU = Add-YmmoOU 'Globaux' $groupsOU
$localOU = Add-YmmoOU 'DomaineLocal' $groupsOU
$computersOU = Add-YmmoOU 'Ordinateurs' $root
[void](Add-YmmoOU 'Siege' $computersOU)
$agencyComputersOU = Add-YmmoOU 'Agences' $computersOU
foreach ($code in $cfg.Agencies) { [void](Add-YmmoOU $code $agencyComputersOU) }
[void](Add-YmmoOU 'Serveurs' $root)
[void](Add-YmmoOU 'Comptes-admin' $root)

Write-Host '2. Groupes globaux (qui : un groupe par pole, un par agence)'
foreach ($pole in $cfg.Poles) {
    Add-YmmoGroup "GG_$($pole.Key)" 'Global' $globalOU "Pole $($pole.Label) (siege et agences)"
}
foreach ($code in $cfg.Agencies) {
    Add-YmmoGroup "GG_Commercial_$code" 'Global' $globalOU "Commerciaux de l'agence $code"
    Add-ADGroupMember -Identity 'GG_Commercial' -Members "GG_Commercial_$code"
}

Write-Host '3. Groupes de domaine local (quoi : un groupe par dossier et par droit) et matrice'
foreach ($folder in $cfg.Folders) {
    foreach ($right in 'RW', 'R') {
        $dl = "DL_$($folder.Name)_$right"
        $label = if ($right -eq 'RW') { 'lecture / ecriture' } else { 'lecture' }
        Add-YmmoGroup $dl 'DomainLocal' $localOU "Dossier $($folder.Name) : $label"
        $members = @($folder[$right] | ForEach-Object { "GG_$_" })
        if ($members.Count) { Add-ADGroupMember -Identity $dl -Members $members }
    }
}

if (-not $SkipDemoUsers) {
    Write-Host '4. Comptes de demonstration'
    foreach ($u in $cfg.DemoUsers) {
        $ou = if ($u.Agency) { "OU=$($u.Agency),$agencyUsersOU" } else { "OU=$($u.Pole),$usersOU" }
        $group = if ($u.Agency) { "GG_Commercial_$($u.Agency)" } else { "GG_$($u.Pole)" }
        if (-not (Get-ADUser -Filter "SamAccountName -eq '$($u.Sam)'")) {
            New-ADUser -Name "$($u.Given) $($u.Surname)" -GivenName $u.Given -Surname $u.Surname `
                -SamAccountName $u.Sam -UserPrincipalName "$($u.Sam)@$($cfg.Domain)" -Path $ou `
                -AccountPassword $DemoPassword -Enabled $true -ChangePasswordAtLogon $false
            Write-Host "  + $($u.Sam) -> $group"
        }
        Add-ADGroupMember -Identity $group -Members $u.Sam
    }
}
Write-Host 'Termine. Etape suivante : .\02-New-YmmoShares.ps1'
