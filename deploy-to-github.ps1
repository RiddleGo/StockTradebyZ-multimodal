# 将 StockTradebyZ-multimodal 推送到 GitHub（需已安装 Git）
# 用法：在 PowerShell 中执行 .\deploy-to-github.ps1
# 首次会创建仓库 RiddleGo/StockTradebyZ-multimodal 并推送；之后直接 push。

$ErrorActionPreference = "Stop"
$repoDir = $PSScriptRoot
$repoName = "StockTradebyZ-multimodal"
$githubUser = "RiddleGo"
# 请勿把 token 提交到仓库！用环境变量 GITHUB_TOKEN 或执行时传入
$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Host "请设置环境变量 GITHUB_TOKEN 后再运行此脚本，或在一行中执行："
    Write-Host '  $env:GITHUB_TOKEN="你的token"; .\deploy-to-github.ps1'
    exit 1
}

Set-Location $repoDir

# 若尚未初始化 git
if (-not (Test-Path .git)) {
    git init
    git add -A
    git commit -m "feat: 多模态复评统一配置与 HTML 报告（支持多厂商、运行结束自动打开网页）"
}

$remote = "https://${token}@github.com/${githubUser}/${repoName}.git"
$branch = "main"

# 是否已有 remote
$hasOrigin = git remote get-url origin 2>$null
if (-not $hasOrigin) {
    git remote add origin $remote
}

# 创建 GitHub 仓库（若不存在）
$create = Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post -Headers @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
} -Body (@{ name = $repoName; description = "StockTradebyZ 多模态图表复评：统一配置多厂商 + HTML 报告自动打开"; private = $false } | ConvertTo-Json) -ErrorAction SilentlyContinue
# 若已存在会 422，忽略

git branch -M $branch
git push -u origin $branch

Write-Host "已推送到 https://github.com/${githubUser}/${repoName}"
