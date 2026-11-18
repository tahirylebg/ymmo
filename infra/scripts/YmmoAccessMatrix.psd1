# Ymmo - single source of truth for the access-rights plan (docs/infra/02-gestion-droits-acces.md).
# Read by every script in this folder: change the matrix here, re-run the scripts, run the test.
@{
    Domain      = 'ad.ymmo.fr'
    NetBios     = 'YMMO'
    BaseOU      = 'Ymmo'
    FileServer  = 'SRV-AIX-01'
    ShareRoot   = 'D:\Partages'

    # Departments (poles) of the head office: Key = OU, share and group suffix
    Poles = @(
        @{ Key = 'Direction';     Label = 'Direction' }
        @{ Key = 'Commercial';    Label = 'Commercial' }
        @{ Key = 'CommMarketing'; Label = 'Communication & Marketing' }
        @{ Key = 'AdminRH';       Label = 'Administration / RH' }
        @{ Key = 'IT';            Label = 'IT & Support' }
    )

    # The 12 agencies (same codes as the platform): their staff are sales people only,
    # GG_Commercial_<code> is nested into GG_Commercial.
    Agencies = @('MRS', 'NCE', 'LYS', 'PAR', 'BOD', 'TLS', 'MPL', 'NTE', 'LIL', 'SXB', 'RNS', 'GNB')

    # The brief's matrix, read per folder: who writes (RW), who reads (R).
    # Any pole not listed is denied by absence of permission (no explicit Deny).
    Folders = @(
        @{ Name = 'Direction';     RW = @('Direction');     R = @() }
        @{ Name = 'Commercial';    RW = @('Commercial');    R = @('Direction', 'CommMarketing', 'AdminRH', 'IT') }
        @{ Name = 'CommMarketing'; RW = @('CommMarketing'); R = @('Direction', 'Commercial', 'AdminRH', 'IT') }
        @{ Name = 'AdminRH';       RW = @('AdminRH');       R = @('Direction') }
        @{ Name = 'IT';            RW = @('IT');            R = @('Direction') }
    )

    # Demo accounts (one per pole + one agency sales person) for the VM demonstration
    DemoUsers = @(
        @{ Sam = 'c.martin';  Given = 'Claire';  Surname = 'Martin';  Pole = 'Direction';     Agency = $null }
        @{ Sam = 'l.bernard'; Given = 'Lucas';   Surname = 'Bernard'; Pole = 'Commercial';    Agency = $null }
        @{ Sam = 'e.petit';   Given = 'Emma';    Surname = 'Petit';   Pole = 'CommMarketing'; Agency = $null }
        @{ Sam = 's.durand';  Given = 'Sarah';   Surname = 'Durand';  Pole = 'AdminRH';       Agency = $null }
        @{ Sam = 'n.moreau';  Given = 'Nathan';  Surname = 'Moreau';  Pole = 'IT';            Agency = $null }
        @{ Sam = 'j.roux';    Given = 'Julie';   Surname = 'Roux';    Pole = 'Commercial';    Agency = 'MRS' }
    )
}
