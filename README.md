# Asana CSV Generator v4.1

A PyQt5 desktop application and standalone web interface for generating Asana-compatible CSV files from Excel templates with automatic BRD data integration.

## Features

### Desktop Application (PyQt5)
- 📄 **Excel Template Loading** — Auto-detects header rows, supports multi-sheet templates
- 📊 **BRD Spreadsheet Viewer** — Visual column selection with search, quick filters, and highlighting
- 🎯 **Intelligent BRD Matching** — Normalized scenario name matching with typo tolerance
- 📱 **Device Filtering** — Filters tasks by Template's "Applicable Devices" column
- 🔄 **OOBE Multi-Criteria Matching** — Enhanced matching for OOBE sheets (component + scenario)
- 📋 **Configuration Queue** — Queue multiple device/sheet configs before export
- 💾 **Queue Persistence** — Queue saved to disk, survives app restarts
- 📝 **Comprehensive Logging** — All operations logged to file for debugging

### Web Interface
- 🌐 **Standalone HTML** — Single-file web app (`asana_generator_web.html`), no server required
- 📊 **Same matching logic** — Mirrors desktop app's BRD matching and template processing

## Quick Start

### Prerequisites
```bash
pip install PyQt5 pandas openpyxl
```

### Run the Desktop App
```bash
cd asana_generator_app
python main.py
```

### Run the Web Interface
Open `asana_generator_web.html` in any modern browser — no installation needed.

## Usage Guide

### Step 1: Load Files
1. **Template** auto-loads from `resources/Template.xlsx`, or click "Update..." to select a different file
2. Click **"Select File..."** to load a BRD Excel file
3. Select the appropriate **sheet** for both Template and BRD

### Step 2: Configure
1. Enter a **Parent Task Name** (e.g., "P1 Malbec - WiFi Stability")
2. Select the **Target Device** (e.g., Malbec, Cava, Barolo)
3. Enter **Project Name** and **Section** for Asana organization
4. For OOBE sheets: select the **Dashboard Component**

### Step 3: Select BRD Columns
1. Click **"🔍 Open Spreadsheet Viewer"**
2. Search for your device name (e.g., "Malbec BRD")
3. Click column headers to select **Perf/BRD** (green) and **Previous Value** (orange) columns
4. Confirm selection

### Step 4: Build Queue & Export
1. Click **"➕ Add to Queue"** — repeat for multiple devices/configs
2. Click **"👁️ Preview Tasks"** to verify
3. Click **"💾 Export CSV"** to generate the Asana-compatible file
4. Import the CSV into Asana via Project → ⋯ → Import → CSV

## Project Structure

```
ASANA_Dashboard/
├── asana_generator_app/           # Desktop application
│   ├── main.py                    # Entry point with logging setup
│   ├── requirements.txt           # Python dependencies
│   ├── core/
│   │   ├── brd_matcher.py         # BRD matching engine
│   │   └── data_loader.py         # Excel/CSV file loading
│   ├── ui/
│   │   ├── main_window.py         # Main application window
│   │   ├── brd_viewer_dialog.py   # BRD spreadsheet viewer dialog
│   │   └── styles.qss             # Qt stylesheet (light theme)
│   └── resources/
│       └── Template.xlsx          # Default template (auto-loaded)
├── asana_generator_web.html       # Standalone web interface
├── .gitignore
└── README.md
```

## Version History

### v4.1 (Current) — Bug Fixes & Improvements
**Bug Fixes:**
- 🐛 Fixed `_format_time` unreachable fallback branch — now correctly handles Excel decimal time format vs minutes
- 🐛 Fixed bare `except:` in `load_all_template_sheets` that silently swallowed errors
- 🐛 Fixed resource leak in `get_sheet_names` — `ExcelFile` was never closed
- 🐛 Fixed resource leak in `load_brd_raw` and `load_all_sheets_as_raw` — workbooks now closed in `finally` blocks
- 🐛 Removed redundant `from core.data_loader import DataLoader` re-import in `_load_default_template`
- 🐛 Fixed inconsistent highlight colors between `ColumnHighlightDelegate` (bright test colors) and dialog class (production colors)

**New Features:**
- ✨ BRD sheet change now auto-resets column selections (prevents stale column indices)
- ✨ Individual queue item removal via right-click context menu
- ✨ Comprehensive logging throughout all modules (`asana_generator.log`)
- ✨ Application startup error handling with user-friendly error dialog
- ✨ Extended `sanitize_numeric_value` to handle more text values ('not applicable', 'pending', 'skip', 'skipped')

**Code Quality:**
- 🔧 Replaced all `print()` debug statements with proper `logging` module usage
- 🔧 Added structured loggers per module (`AsanaGenerator.MainWindow`, `.DataLoader`, `.BrdMatcher`, `.BrdViewer`)
- 🔧 Updated `.gitignore` to exclude deprecated script files and backups
- 🔧 Version bumped to v4.1 in window title

### v4.0
- Full PyQt5 desktop application with web app feature parity
- BRD spreadsheet viewer with visual column selection
- OOBE multi-criteria matching
- Configuration queue with persistence
- Light theme UI

### v3.0
- Enhanced generator with comprehensive logging
- Web interface (`asana_generator_web.html`)

### v2.0
- Excel template import, BRD data integration
- Quick import interface, device filtering

### v1.0
- Basic CSV generation with manual task entry

## Template Format

### Required Columns
| Column | Description |
|--------|-------------|
| `Performance Scenario` or `Scenario Name` | Task/scenario name for BRD matching |
| `Applicable Devices` | Comma-separated device list (e.g., "Malbec,Cava,Barolo") |
| `Priority` | Task priority (P0, P1, P2, etc.) |
| `Estimated Time` | Duration in minutes |

### OOBE-Specific Columns
| Column | Description |
|--------|-------------|
| `New_Dashboard_Component` | Dashboard component identifier |
| `Sub_Priority` | Sub-priority for OOBE matching |

## Logging

All operations are logged to `asana_generator_app/asana_generator.log`:
```
2026-02-12 11:00:00 [INFO] AsanaGenerator: Application started successfully
2026-02-12 11:00:01 [INFO] AsanaGenerator.DataLoader: Template loaded: 45 rows, 8 columns
2026-02-12 11:00:05 [INFO] AsanaGenerator.MainWindow: Added to queue: 'P1 Malbec' - Malbec - Sheet1 (32 tasks)
```

## License
For internal use only.
