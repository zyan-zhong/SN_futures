param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8788
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
python -m sn_futures.devtools.mock_managed_proxy --host $HostName --port $Port
