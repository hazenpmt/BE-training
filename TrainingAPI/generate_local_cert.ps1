$ErrorActionPreference = 'Stop'
$opensslCommand = Get-Command openssl -ErrorAction SilentlyContinue
$opensslPath = if ($opensslCommand) { $opensslCommand.Source } else { $null }
if (-not $opensslPath) {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCommand) {
        $gitRoot = Split-Path (Split-Path $gitCommand.Source)
        $candidate = Join-Path $gitRoot 'usr\bin\openssl.exe'
        if (Test-Path -LiteralPath $candidate) { $opensslPath = $candidate }
    }
}
if (-not $opensslPath) { throw 'OpenSSL not found. Install Git for Windows with bundled OpenSSL or add openssl to PATH.' }
$certDirectory = Join-Path $PSScriptRoot 'certs'
New-Item -ItemType Directory -Path $certDirectory -Force | Out-Null
$certPath = Join-Path $certDirectory 'localhost.crt'
$keyPath = Join-Path $certDirectory 'localhost.key'
if ((Test-Path -LiteralPath $certPath) -or (Test-Path -LiteralPath $keyPath)) {
    throw 'Certificate/key already exists; refusing to overwrite.'
}
& $opensslPath req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 `
    -keyout $keyPath -out $certPath -subj '/CN=localhost' `
    -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' `
    -addext 'extendedKeyUsage=serverAuth'
if ($LASTEXITCODE -ne 0) { throw 'Certificate generation failed.' }
Write-Output "Local certificate created: $certPath"
