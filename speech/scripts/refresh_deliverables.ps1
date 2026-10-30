# 录音就位后一键刷新全部交付物（对应根目录《自录音频准备清单.md》第五节）：
#   1) 推理套件：示例推理 + 长音频阈值实验 + 处理 my_recordings/ 内自录音频
#   2) 报告 docx 重新生成（全部数字程序化读自 outputs/ 证据文件）
#   3) Word COM 导出 PDF（按文档要求 4~8 页）
#   4) 重新打包提交 zip（2023302610_肖怀瑾_kws.zip）
# 运行前请关闭已打开的 kws_report.docx / kws_report.pdf。
$ErrorActionPreference = "Stop"

$repo     = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)  # speech/scripts -> speech -> 仓库根
$py       = "D:\Anaconda3\envs\pytorch\python.exe"
$delivery = Join-Path $repo "speech\reports\delivery-20261031"

Write-Output "[1/4] 推理套件（含自录音频）..."
& $py -s (Join-Path $repo "speech\scripts\run_inference_suite.py") 2>&1 | Select-Object -Last 3

Write-Output "[2/4] 重新生成报告 docx..."
& $py -s (Join-Path $repo "speech\reports\build_report.py") 2>&1 | Select-Object -Last 2

Write-Output "[3/4] Word 导出 PDF..."
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open((Join-Path $delivery "kws_report.docx"), $false, $true)
  $doc.ExportAsFixedFormat((Join-Path $delivery "kws_report.pdf"), 17)
  Write-Output ("  PDF 页数: " + $doc.ComputeStatistics(2))
  $doc.Close($false)
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

Write-Output "[4/4] 重新打包提交 zip..."
& $py -s (Join-Path $repo "speech\scripts\package_submission.py") 2>&1 | Select-Object -Last 3

Write-Output "全部交付物已刷新。"
