# SynPin brand colors for PowerShell scripts.
#
# The Python CLI uses Rich with hex codes (#f97316 for --orange,
# #f59e0b for --accent) defined in core/synpin/cli/console.py.
# PowerShell 5.1's Write-Host only accepts named colors (Yellow,
# Green, Red, Cyan, Gray, DarkGray, etc.) — not hex — so we map each
# SynPin brand color to its closest named counterpart.
#
# Bash uses ANSI 24-bit escape codes (defined in colors.sh) so it can
# match exactly. PowerShell on Windows Terminal / modern conhost also
# supports VT processing (enabled in dev.ps1), but Write-Host still
# doesn't take hex — only named. So the mapping below is the best we
# can do without rewriting output to use [Console]::WriteLine().
#
# Keep this in sync with core/synpin/cli/console.py:synpin_theme.

$SynPinBrand   = 'Yellow'        # --orange (#f97316) — closest named: Yellow
$SynPinAccent  = 'DarkYellow'    # --accent (#f59e0b) — warmer accent for sub-headers
$SynPinInfo    = 'Yellow'        # informational highlights
$SynPinOK      = 'Green'         # success
$SynPinWarn    = 'Yellow'        # warnings (same hue as brand — visual cohesion)
$SynPinFail    = 'Red'           # errors
$SynPinDim     = 'DarkGray'      # secondary metadata
$SynPinPath    = 'Gray'          # file paths
