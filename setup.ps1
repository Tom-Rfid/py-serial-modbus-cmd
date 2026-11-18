<#
.SYNOPSIS
    Prépare l'environnement Python de SerialHex dans le dossier .venv

.DESCRIPTION
    1. Vérifie que la version de Python demandée est installée (lanceur py)
    2. Crée l'environnement virtuel .venv (ou le recrée si la version a changé)
    3. Met pip à jour et installe requirements.txt
    4. Vérifie tkinter et pyserial, lance les tests

.EXAMPLE
    .\setup.ps1                 # Python 3.9 (minimum du débogueur VS Code)
    .\setup.ps1 -Python 3.12    # autre version
    .\setup.ps1 -Recreate       # repart d'un environnement neuf

.NOTES
    Fermer VS Code (ou au moins ses terminaux) avant de recréer .venv : l'extension Python
    garde python.exe ouvert et la suppression échoue. Le code reste compatible Python 3.8.
#>
param(
    [string]$Python = "3.9",
    [switch]$Recreate
)

# "Continue" : sous Windows PowerShell 5.1, "Stop" transforme la sortie d'erreur
# des commandes externes en exceptions. On teste $LASTEXITCODE à la place.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$Venv       = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Fail([string]$msg) { Write-Host "`nERREUR : $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
Step "Recherche de Python $Python"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Fail "Lanceur 'py' introuvable. Installer Python depuis https://www.python.org/downloads/ en cochant 'py launcher'."
}
$version = & py "-$Python" -c "import sys; print(sys.version.split()[0])" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Versions installées :"
    & py --list
    Fail "Python $Python n'est pas installé. L'installer depuis https://www.python.org/downloads/ (installeur Windows 64 bits), puis relancer ce script."
}
Ok "Python $version"

# ---------------------------------------------------------------------------
Step "Environnement virtuel .venv"
if ((Test-Path $VenvPython) -and -not $Recreate) {
    $venvVersion = & $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -ne 0 -or $venvVersion -ne $Python) {
        Write-Host "    .venv utilise Python $venvVersion au lieu de $Python : il est recréé."
        $Recreate = $true
    }
}
if ($Recreate -and (Test-Path $Venv)) {
    Remove-Item -Recurse -Force $Venv
    if (Test-Path $Venv) { Fail "Impossible de supprimer .venv : fermer les programmes qui l'utilisent (SerialHex, terminal activé...)." }
}
if (-not (Test-Path $VenvPython)) {
    & py "-$Python" -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail "Création de .venv impossible." }
    Ok "créé avec Python $version"
} else {
    Ok "déjà présent"
}

# ---------------------------------------------------------------------------
Step "Installation des dépendances"
& $VenvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Fail "Mise à jour de pip impossible (connexion internet ?)." }
& $VenvPython -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Fail "Installation de requirements.txt impossible." }
Ok "requirements.txt installé"

# ---------------------------------------------------------------------------
Step "Vérifications"
$check = & $VenvPython -c "import tkinter, serial; print('tkinter %s, pyserial %s' % (tkinter.TkVersion, serial.__version__))"
if ($LASTEXITCODE -ne 0) { Fail "tkinter ou pyserial ne se charge pas. Réinstaller Python en cochant 'tcl/tk and IDLE'." }
Ok $check
& $VenvPython -m unittest discover tests 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Les tests échouent : relancer 'python -m unittest discover tests -v' pour le détail." }
Ok "tests OK"

# ---------------------------------------------------------------------------
Write-Host "`nPrêt. Pour lancer SerialHex :" -ForegroundColor Green
Write-Host "    double-clic sur run.bat"
Write-Host "    ou : .venv\Scripts\python serialhex.py"
Write-Host "`nDans VS Code (une seule fois après un changement de version) :" -ForegroundColor Green
Write-Host "    1. Ctrl+Shift+P > 'Python: Select Interpreter' > .venv ($version)"
Write-Host "    2. Terminal > 'Tuer tous les terminaux', puis Terminal > Nouveau terminal : l'invite commence par (.venv)"
Write-Host "    Si rien ne change : Ctrl+Shift+P > 'Developer: Reload Window'"
