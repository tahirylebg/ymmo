#Requires -Modules ActiveDirectory
<#
.SYNOPSIS
    Ymmo - checks the access rights actually in place against the brief's matrix.
.DESCRIPTION
    For every pole and every folder, reads the real configuration (membership of the DL groups,
    NTFS rules on the folder, access-based enumeration on the share) and prints the matrix it
    gives, next to the expected one. Exit code 1 if anything differs: usable during the demo.
#>
[CmdletBinding()]
param([string]$ShareRoot)
$ErrorActionPreference = 'Stop'
$cfg = Import-PowerShellDataFile -Path (Join-Path $PSScriptRoot 'YmmoAccessMatrix.psd1')
if (-not $ShareRoot) { $ShareRoot = $cfg.ShareRoot }

function Test-DirectMember([string]$Group, [string]$Member) {
    @(Get-ADGroupMember -Identity $Group -Recursive:$false | Where-Object Name -eq $Member).Count -gt 0
}
function Test-AclHas([string]$Path, [string]$Group, [string]$Right) {
    $rules = (Get-Acl -Path $Path).Access | Where-Object {
        $_.IdentityReference.Value -eq "$($cfg.NetBios)\$Group" -and $_.AccessControlType -eq 'Allow'
    }
    @($rules | Where-Object { $_.FileSystemRights.ToString() -match $Right }).Count -gt 0
}

$rows = @()
$errors = 0
foreach ($pole in $cfg.Poles) {
    $row = [ordered]@{ Pole = $pole.Label }
    foreach ($folder in $cfg.Folders) {
        $expected = if ($folder.RW -contains $pole.Key) { 'RW' } elseif ($folder.R -contains $pole.Key) { 'R' } else { '-' }
        $path = Join-Path $ShareRoot $folder.Name
        $gg = "GG_$($pole.Key)"
        $actual = '-'
        if ((Test-DirectMember "DL_$($folder.Name)_RW" $gg) -and (Test-AclHas $path "DL_$($folder.Name)_RW" 'Modify')) { $actual = 'RW' }
        elseif ((Test-DirectMember "DL_$($folder.Name)_R" $gg) -and (Test-AclHas $path "DL_$($folder.Name)_R" 'ReadAndExecute')) { $actual = 'R' }
        if ($actual -ne $expected) { $errors++; $actual = "$actual (attendu $expected)" }
        $row[$folder.Name] = $actual
    }
    $rows += [pscustomobject]$row
}
$rows | Format-Table -AutoSize

foreach ($folder in $cfg.Folders) {
    $share = Get-SmbShare -Name $folder.Name -ErrorAction SilentlyContinue
    if (-not $share) { $errors++; Write-Warning "Partage $($folder.Name) absent" }
    elseif ($share.FolderEnumerationMode -ne 'AccessBased') { $errors++; Write-Warning "ABE desactive sur $($folder.Name)" }
    if (-not (Get-Acl -Path (Join-Path $ShareRoot $folder.Name)).AreAccessRulesProtected) {
        $errors++; Write-Warning "Heritage NTFS non coupe sur $($folder.Name)"
    }
}
$agencyNested = @($cfg.Agencies | Where-Object { -not (Test-DirectMember 'GG_Commercial' "GG_Commercial_$_") })
if ($agencyNested.Count) { $errors++; Write-Warning "Agences hors de GG_Commercial : $($agencyNested -join ', ')" }

if ($errors) { Write-Host "$errors ecart(s) avec la matrice." -ForegroundColor Red; exit 1 }
Write-Host 'Conforme a la matrice des droits (RW = lecture/ecriture, R = lecture, - = interdit).' -ForegroundColor Green
