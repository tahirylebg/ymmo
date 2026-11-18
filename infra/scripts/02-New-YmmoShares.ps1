#Requires -Modules SmbShare
<#
.SYNOPSIS
    Ymmo - creates the department folders, their NTFS rights and the SMB share.
.DESCRIPTION
    One folder per department under ShareRoot (YmmoAccessMatrix.psd1), all published by a
    single share, \\SRV-AIX-01\Partages: access-based enumeration works inside a share (not on
    the server's list of shares), so a user browsing it only sees the folders they may open.
    - NTFS does the filtering: inheritance cut on each folder; SYSTEM and Administrators full
      control; DL_<folder>_RW modify (on the content only, so the folder itself cannot be deleted
      or renamed); DL_<folder>_R read. "Forbidden" = no permission at all (no Deny).
    - The root is only listable by users (this folder only): no file can be dropped there.
    - Share level: Authenticated Users change, Administrators full; access-based enumeration on.
    Well-known accounts are given by SID: the script works on a French Windows Server too.
    Run on SRV-AIX-01 after 01-New-YmmoAdStructure.ps1. Idempotent (ACLs are rewritten).
#>
[CmdletBinding()]
param([string]$ShareRoot)
$ErrorActionPreference = 'Stop'
$cfg = Import-PowerShellDataFile -Path (Join-Path $PSScriptRoot 'YmmoAccessMatrix.psd1')
if (-not $ShareRoot) { $ShareRoot = $cfg.ShareRoot }

$sid = @{ System = 'S-1-5-18'; Admins = 'S-1-5-32-544'; AuthUsers = 'S-1-5-11' }
function Get-AccountName([string]$Sid) {
    ([Security.Principal.SecurityIdentifier]$Sid).Translate([Security.Principal.NTAccount]).Value
}
$inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
$none = [Security.AccessControl.InheritanceFlags]::None
$noProp = [Security.AccessControl.PropagationFlags]::None
$inheritOnly = [Security.AccessControl.PropagationFlags]::InheritOnly

function New-Rule($Identity, [string]$Rights, $Inheritance, $Propagation) {
    New-Object Security.AccessControl.FileSystemAccessRule($Identity, $Rights, $Inheritance, $Propagation, 'Allow')
}
function New-ProtectedAcl {
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)   # cut inheritance, keep nothing inherited
    $acl.AddAccessRule((New-Rule ([Security.Principal.SecurityIdentifier]$sid.System) 'FullControl' $inherit $noProp))
    $acl.AddAccessRule((New-Rule ([Security.Principal.SecurityIdentifier]$sid.Admins) 'FullControl' $inherit $noProp))
    return , $acl
}

# Root: listable by users, nothing else
New-Item -ItemType Directory -Path $ShareRoot -Force | Out-Null
$rootAcl = New-ProtectedAcl
$rootAcl.AddAccessRule((New-Rule ([Security.Principal.SecurityIdentifier]$sid.AuthUsers) 'ReadAndExecute' $none $noProp))
Set-Acl -Path $ShareRoot -AclObject $rootAcl
Write-Host "  NTFS $ShareRoot : racine listable uniquement"

foreach ($folder in $cfg.Folders) {
    $name = $folder.Name
    $path = Join-Path $ShareRoot $name
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    $rw = New-Object Security.Principal.NTAccount("$($cfg.NetBios)\DL_$($name)_RW")
    $ro = New-Object Security.Principal.NTAccount("$($cfg.NetBios)\DL_$($name)_R")

    $acl = New-ProtectedAcl
    # Writers: create in the folder, modify everything inside it, but not the folder itself
    $acl.AddAccessRule((New-Rule $rw 'ReadAndExecute, Write' $none $noProp))
    $acl.AddAccessRule((New-Rule $rw 'Modify' $inherit $inheritOnly))
    $acl.AddAccessRule((New-Rule $ro 'ReadAndExecute' $inherit $noProp))
    Set-Acl -Path $path -AclObject $acl
    Write-Host "  NTFS $path : DL_$($name)_RW modification, DL_$($name)_R lecture"
}

if (-not (Get-SmbShare -Name 'Partages' -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name 'Partages' -Path $ShareRoot -FolderEnumerationMode AccessBased -CachingMode None `
        -FullAccess (Get-AccountName $sid.Admins) -ChangeAccess (Get-AccountName $sid.AuthUsers) | Out-Null
    Write-Host "  + partage \\$env:COMPUTERNAME\Partages (enumeration basee sur l'acces)"
}
Write-Host 'Termine. Verification : .\03-Test-YmmoAccess.ps1'
