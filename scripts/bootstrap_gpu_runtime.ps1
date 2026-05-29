param(
    [string]$PythonExe = "python",
    [string]$TorchVersion = "2.5.1",
    [string]$CudaWheelTag = "cu121"
)

$ErrorActionPreference = "Stop"

Write-Host "Checking CUDA-enabled Torch runtime..."
$probe = @'
import json
payload = {}
try:
    import torch
    payload = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
    }
except Exception as exc:
    payload = {"error": repr(exc)}
print(json.dumps(payload, ensure_ascii=False))
'@

function Invoke-TorchProbe {
    $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "sn_torch_probe_$([System.Guid]::NewGuid().ToString('N')).py")
    try {
        Set-Content -LiteralPath $tmp -Value $probe -Encoding UTF8
        $result = & $PythonExe $tmp
        if ($LASTEXITCODE -ne 0) {
            throw "Torch probe failed with exit code $LASTEXITCODE."
        }
        return $result
    }
    finally {
        if (Test-Path -LiteralPath $tmp) {
            Remove-Item -LiteralPath $tmp -Force
        }
    }
}

$before = Invoke-TorchProbe
Write-Host "Current runtime: $before"
if ($before -match '"cuda_available": true') {
    Write-Host "CUDA Torch is already available. No install needed."
    exit 0
}

$indexUrl = "https://download.pytorch.org/whl/$CudaWheelTag"
Write-Host "Installing torch==$TorchVersion+$CudaWheelTag from $indexUrl ..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install --upgrade --index-url $indexUrl "torch==$TorchVersion+$CudaWheelTag"

$after = Invoke-TorchProbe
Write-Host "Updated runtime: $after"
if ($after -notmatch '"cuda_available": true') {
    throw "CUDA Torch installation completed but torch.cuda.is_available() is still false. Check NVIDIA driver and Python architecture."
}
