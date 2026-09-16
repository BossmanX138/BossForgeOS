[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SiteName = "CBCAA Accounts",
    [string]$HostName = "accounts.bosscrafts.net",
    [string]$PhysicalPath = "C:\inetpub\cbcaa-accounts",
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$BackendHealthPath = "/openapi.json",
    [int]$HttpsPort = 443,
    [string]$CertThumbprint = "",
    [string]$CertStoreName = "My",
    [switch]$SkipBackendProbe,
    [switch]$SkipCertificateBinding
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

function Assert-IISModule {
    Import-Module WebAdministration -ErrorAction Stop
}

function Assert-AppCmd {
    $script:AppCmdPath = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
    if (-not (Test-Path $script:AppCmdPath)) {
        throw "IIS appcmd.exe was not found at $script:AppCmdPath."
    }
}

function Test-Backend {
    param(
        [string]$BaseUrl,
        [string]$HealthPath
    )

    $probeUrl = "{0}{1}" -f $BaseUrl.TrimEnd('/'), $HealthPath
    Write-Step "Probing CBCAA backend at $probeUrl"
    try {
        $response = Invoke-WebRequest -Uri $probeUrl -UseBasicParsing -TimeoutSec 15
    } catch {
        throw "CBCAA backend probe failed for $probeUrl. Make sure the Docker container is running and reachable locally. Details: $($_.Exception.Message)"
    }

    $contentType = [string]($response.Headers["Content-Type"])
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "CBCAA backend probe returned HTTP $($response.StatusCode) from $probeUrl."
    }
    if ($contentType -notmatch "json") {
        throw "CBCAA backend probe succeeded but did not return JSON. Content-Type was '$contentType'."
    }

    Write-Host "Backend probe passed: HTTP $($response.StatusCode) $contentType" -ForegroundColor Green
}

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        if ($PSCmdlet.ShouldProcess($Path, "Create directory")) {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
        }
    }
}

function Enable-ArrProxy {
    Write-Step "Enabling IIS ARR reverse proxy"
    $args = @(
        "set", "config",
        "-section:system.webServer/proxy",
        "/enabled:true",
        "/preserveHostHeader:true",
        "/reverseRewriteHostInResponseHeaders:false",
        "/commit:apphost"
    )
    if ($PSCmdlet.ShouldProcess("IIS ARR proxy", "Enable proxy settings")) {
        & $script:AppCmdPath @args | Out-Null
    }
}

function New-RewriteConfigContent {
    param(
        [string]$ProxyTarget,
        [string]$PublicHost
    )

@"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReverseProxyToCBCAA" stopProcessing="true">
          <match url="(.*)" />
          <conditions logicalGrouping="MatchAll" trackAllCaptures="false">
            <add input="{CACHE_URL}" pattern="^(.+)$" />
          </conditions>
          <action type="Rewrite" url="$ProxyTarget/{R:1}" logRewrittenUrl="true" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST" value="$PublicHost" />
            <set name="HTTP_X_FORWARDED_FOR" value="{REMOTE_ADDR}" />
          </serverVariables>
        </rule>
      </rules>
    </rewrite>
    <httpProtocol>
      <customHeaders>
        <add name="X-Forwarded-Proto" value="https" />
        <add name="X-Forwarded-Host" value="$PublicHost" />
      </customHeaders>
    </httpProtocol>
  </system.webServer>
</configuration>
"@
}

function Write-WebConfig {
    param(
        [string]$Path,
        [string]$ProxyTarget,
        [string]$PublicHost
    )

    $configPath = Join-Path $Path "web.config"
    $content = New-RewriteConfigContent -ProxyTarget $ProxyTarget.TrimEnd('/') -PublicHost $PublicHost
    if ($PSCmdlet.ShouldProcess($configPath, "Write IIS reverse proxy web.config")) {
        Set-Content -Path $configPath -Value $content -Encoding UTF8
    }
}

function Ensure-AppPool {
    param([string]$PoolName)

    $poolPath = "IIS:\AppPools\$PoolName"
    if (-not (Test-Path $poolPath)) {
        Write-Step "Creating IIS app pool '$PoolName'"
        if ($PSCmdlet.ShouldProcess($PoolName, "Create IIS application pool")) {
            New-Item $poolPath | Out-Null
        }
    }

    if ($PSCmdlet.ShouldProcess($PoolName, "Set IIS app pool managed runtime to none")) {
        Set-ItemProperty $poolPath -Name managedRuntimeVersion -Value ""
        Set-ItemProperty $poolPath -Name processModel.identityType -Value 4
    }
}

function Ensure-Site {
    param(
        [string]$Name,
        [string]$Path,
        [string]$PoolName
    )

    $sitePath = "IIS:\Sites\$Name"
    if (-not (Test-Path $sitePath)) {
        Write-Step "Creating IIS site '$Name'"
        if ($PSCmdlet.ShouldProcess($Name, "Create IIS site")) {
            New-Website -Name $Name -PhysicalPath $Path -ApplicationPool $PoolName -Port 80 | Out-Null
        }
    } else {
        if ($PSCmdlet.ShouldProcess($Name, "Update IIS site physical path and app pool")) {
            Set-ItemProperty $sitePath -Name physicalPath -Value $Path
            Set-ItemProperty $sitePath -Name applicationPool -Value $PoolName
        }
    }
}

function Ensure-HostBindings {
    param(
        [string]$Name,
        [string]$PublicHost,
        [int]$Port,
        [string]$Thumbprint,
        [string]$StoreName,
        [bool]$SkipCert
    )

    Write-Step "Ensuring IIS bindings for $PublicHost"

    $httpBinding = Get-WebBinding -Name $Name -Protocol "http" -ErrorAction SilentlyContinue |
        Where-Object { $_.bindingInformation -eq "*:80:$PublicHost" }
    if (-not $httpBinding) {
        if ($PSCmdlet.ShouldProcess("$Name http binding", "Add http host binding for $PublicHost")) {
            New-WebBinding -Name $Name -Protocol "http" -Port 80 -HostHeader $PublicHost | Out-Null
        }
    }

    $httpsBindingInfo = "*:${Port}:$PublicHost"
    $httpsBinding = Get-WebBinding -Name $Name -Protocol "https" -ErrorAction SilentlyContinue |
        Where-Object { $_.bindingInformation -eq $httpsBindingInfo }
    if (-not $httpsBinding) {
        if ($PSCmdlet.ShouldProcess("$Name https binding", "Add https host binding for $PublicHost")) {
            New-WebBinding -Name $Name -Protocol "https" -Port $Port -HostHeader $PublicHost | Out-Null
        }
    }

    if ($SkipCert) {
        Write-Warning "Skipping certificate binding. Add an SSL certificate for $PublicHost before going live."
        return
    }

    if (-not $Thumbprint) {
        throw "CertThumbprint is required unless -SkipCertificateBinding is set."
    }

    $normalizedThumbprint = ($Thumbprint -replace "\s", "").ToUpperInvariant()
    $certPath = "Cert:\LocalMachine\$StoreName\$normalizedThumbprint"
    if (-not (Test-Path $certPath)) {
        throw "Certificate $normalizedThumbprint was not found in LocalMachine\$StoreName."
    }

    $sslBindingPath = "IIS:\SslBindings\0.0.0.0!${Port}!$PublicHost"
    if ($PSCmdlet.ShouldProcess($sslBindingPath, "Bind certificate $normalizedThumbprint")) {
        if (Test-Path $sslBindingPath) {
            Remove-Item $sslBindingPath -Force
        }
        Get-Item $certPath | New-Item $sslBindingPath | Out-Null
    }
}

function Restart-SiteSafe {
    param([string]$Name)

    Write-Step "Restarting IIS site '$Name'"
    if ($PSCmdlet.ShouldProcess($Name, "Restart IIS site")) {
        Stop-Website -Name $Name -ErrorAction SilentlyContinue
        Start-Website -Name $Name
    }
}

function Write-CompletionNotes {
    param(
        [string]$PublicHost,
        [string]$ProxyTarget,
        [string]$ProbePath
    )

    $externalDocs = "https://$PublicHost/docs"
    $externalOpenApi = "https://$PublicHost/openapi.json"
    $backendProbe = "{0}{1}" -f $ProxyTarget.TrimEnd('/'), $ProbePath

    Write-Host ""
    Write-Host "Setup script finished." -ForegroundColor Green
    Write-Host ""
    Write-Host "Manual follow-up:" -ForegroundColor Yellow
    Write-Host "1. In IONOS DNS, point '$PublicHost' to this server's public IP."
    Write-Host "2. Make sure URL Rewrite and ARR are installed in IIS."
    Write-Host "3. Make sure a valid SSL certificate is bound for '$PublicHost'."
    Write-Host "4. Verify backend locally: $backendProbe"
    Write-Host "5. Verify externally: $externalOpenApi and $externalDocs"
}

Assert-Administrator
Assert-IISModule
Assert-AppCmd

if (-not $SkipBackendProbe) {
    Test-Backend -BaseUrl $BackendUrl -HealthPath $BackendHealthPath
} else {
    Write-Warning "Skipping backend probe."
}

$appPoolName = $SiteName

Write-Step "Preparing filesystem path"
Ensure-Directory -Path $PhysicalPath

Write-Step "Writing IIS reverse proxy config"
Write-WebConfig -Path $PhysicalPath -ProxyTarget $BackendUrl -PublicHost $HostName

Ensure-AppPool -PoolName $appPoolName
Ensure-Site -Name $SiteName -Path $PhysicalPath -PoolName $appPoolName
Enable-ArrProxy
Ensure-HostBindings -Name $SiteName -PublicHost $HostName -Port $HttpsPort -Thumbprint $CertThumbprint -StoreName $CertStoreName -SkipCert:$SkipCertificateBinding.IsPresent
Restart-SiteSafe -Name $SiteName
Write-CompletionNotes -PublicHost $HostName -ProxyTarget $BackendUrl -ProbePath $BackendHealthPath
