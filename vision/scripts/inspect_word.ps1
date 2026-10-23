param(
  [Parameter(Mandatory=$true)][string]$Report,
  [Parameter(Mandatory=$true)][string]$OutputDirectory,
  [switch]$ExportPdf
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$reportPath=(Resolve-Path -LiteralPath $Report).Path
$outputPath=[System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $outputPath) { throw 'Preserve previous Word inspection; choose a new directory' }
New-Item -ItemType Directory -Path $outputPath | Out-Null
$word=$null
$document=$null
try {
  # The generic Word.Application ROT may be registered by WPS. Bind explicitly
  # to installed Microsoft Word 16 and retain this owned COM instance throughout.
  $word=[Activator]::CreateInstance([type]::GetTypeFromProgID('Word.Application.16'))
  $word.Visible=$false
  $word.DisplayAlerts=0
  $word.AutomationSecurity=3
  $formattedPath=Join-Path $outputPath 'vision_report.docx'
  Copy-Item -LiteralPath $reportPath -Destination $formattedPath
  Write-Output ('Opening in '+$word.Name+' '+$word.Version)
  $document=$word.Documents.Open($formattedPath,$false,$false,$false)
  $document.ActiveWindow.View.Type=3
  Write-Output 'Updating table of contents'
  if ($document.TablesOfContents.Count -gt 0) { $document.TablesOfContents.Item(1).Update() }
  $document.Repaginate()
  $pdfPath=Join-Path $outputPath 'vision_report.pdf'
  Write-Output 'Saving generated copy'
  $document.Save()
  if ($ExportPdf) {
    Write-Output 'Exporting local PDF'
    $document.ExportAsFixedFormat($pdfPath,17)
  }
  $pages=$document.ComputeStatistics(2)
  $headings=@()
  # Find the actual appendices after the TOC, without thousands of COM round trips.
  foreach ($title in @('附录 A','附录 B','附录 C','附录 D')) {
    $range=$document.Content.Duplicate
    if ($document.TablesOfContents.Count -gt 0) { $range.Start=$document.TablesOfContents.Item(1).Range.End }
    $range.Find.Text=$title
    if ($range.Find.Execute()) { $headings += [pscustomobject]@{title=$title;page=$range.Information(3)} }
  }
  $previewPages=@(1,2,6,10,14,18,22,24)+@($headings | ForEach-Object { $_.page })
  $previews=@()
  foreach ($number in ($previewPages | Sort-Object -Unique)) {
    try {
      Write-Output "Rendering page $number"
      $bits=$document.ActiveWindow.Panes.Item(1).Pages.Item($number).EnhMetaFileBits
      $stream=New-Object System.IO.MemoryStream(,[byte[]]$bits)
      $metafile=[System.Drawing.Image]::FromStream($stream)
      $bitmap=New-Object System.Drawing.Bitmap(1240,1754)
      $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
      $graphics.Clear([System.Drawing.Color]::White)
      $graphics.DrawImage($metafile,0,0,1240,1754)
      $imagePath=Join-Path $outputPath ("page_{0:D3}.png" -f $number)
      $bitmap.Save($imagePath,[System.Drawing.Imaging.ImageFormat]::Png)
      $graphics.Dispose();$bitmap.Dispose();$metafile.Dispose();$stream.Dispose()
      $previews+=$number
    } catch { Write-Output "Page image unavailable for page ${number}: $($_.Exception.Message)" }
  }
  $audit=[ordered]@{ source=$reportPath; formatted_docx=$formattedPath; pdf= $(if ($ExportPdf) {$pdfPath} else {$null}); pages=$pages; figures=$document.InlineShapes.Count; tables=$document.Tables.Count; headings=$headings; preview_pages=$previews; application_name=$word.Name; application_path=$word.Path; word_version=$word.Version; fields_updated=$true }
  [System.IO.File]::WriteAllText((Join-Path $outputPath 'word_layout.json'),($audit | ConvertTo-Json -Depth 6),(New-Object System.Text.UTF8Encoding($false)))
  Write-Output ($audit | ConvertTo-Json -Depth 5)
} finally {
  if ($document) { $document.Close(0) }
  if ($word) { $word.Quit() }
}
