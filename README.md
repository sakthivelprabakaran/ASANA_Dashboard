# Asana CSV Generator V2

Enhanced PyQt5 application for generating Asana-formatted CSV files with Excel template integration and BRD data lookup.

## Features

✨ **Quick Import from Excel Templates**
- Load task templates from Excel files
- Filter tasks by device using "Applicable" column
- Bulk import with checkbox selection

📊 **Automatic BRD Data Integration**
- Auto-loads BRD performance files from directory
- Matches tasks with Previous Value and Perf_BRD data
- Supports both SBR and Mainline sheet types

🎯 **Fixed Performance Values**
- GREEN: 0
- YELLOW: 0.1
- RED: 0.1
- Iteration_01: 0
- Average: 0
- Perf_BRD: 0.1 (default)
- Deviation % Current Vs BRD: 0.1

🔧 **User-Friendly Interface**
- Tab-based navigation
- Visual task hierarchy tree
- CSV preview before export
- Section and task management

## Installation

### Prerequisites
```bash
# Install Python 3.7+
# Install required packages
pip install PyQt5 pandas openpyxl
```

### Quick Start
```bash
# Run the application
python asana_csv_generator_v2.py
```

## Usage Guide

### 1. Project Setup
1. Go to **Project Settings** tab
2. Enter your project name (e.g., "J19.2 SBR J19.3 Mainline")

### 2. Create Sections
1. Go to **Sections** tab
2. Enter section name (e.g., "Week_05 J19.2")
3. Click **Add Section**
4. Repeat for all needed sections

### 3. Quick Import from Excel (Recommended)

#### Step 1: Prepare Your Excel Template
Your Excel template should have these columns:
- **Applicable** - Mark with any value (X, Yes, True) for tasks to include
- **Task Name** or **Name** - The task description
- **Priority** - P0, P1, P2, P3, OOBE, GEN Ai, etc.
- **Time** or **Estimated Time** - Time in minutes
- **Parent Task** - (Optional) Parent task name for subtasks
- **Notes** - (Optional) Additional notes

Example Excel structure:
```
| Applicable | Task Name                    | Priority | Time | Parent Task      |
|------------|------------------------------|----------|------|------------------|
| X          | P0 All Devices              | P0       | 0    |                  |
| X          | Wake-up time from suspend   | P0       | 15   | P0 All Devices   |
```

#### Step 2: Load Files
1. Click **📁 Load Excel Template** button
2. Select your task template Excel file
3. BRD file auto-loads if named with "Performance" or "BRD" in filename
   - Or manually click **📊 Load BRD File** to select

#### Step 3: Import Tasks
1. Go to **⚡ Quick Import** tab
2. Select:
   - **Excel Sheet**: Choose the sheet containing tasks
   - **Target Section**: Select where to import (must create sections first)
   - **Device**: Select device name (Malbec, Cava, Barolo, etc.)
   - **BRD Sheet Type**: Choose Mainline or SBR
3. Click **Preview Tasks** to see filtered tasks
4. Check/uncheck tasks to import
5. Click **Import Selected Tasks**

The app will:
- Filter tasks based on "Applicable" column
- Apply device name to all tasks
- Lookup BRD data automatically (Previous Value, Perf_BRD)
- Set fixed values (GREEN, YELLOW, RED)
- Add to project structure

### 4. Review and Export
1. Go to **Manual Tasks** tab to see imported hierarchy
2. Go to **Preview & Export** tab
3. Click **🔄 Refresh Preview** to see CSV preview
4. Review the data
5. Click **💾 Export CSV** to save file

### 5. Import to Asana
1. Open Asana project
2. Click on the three dots (...) menu
3. Select "Import" → "CSV"
4. Upload the generated CSV file
5. Asana will create sections, tasks, and subtasks based on the hierarchy

## Excel Template Format

### Required Columns for Task Import
- `Applicable` - Any value marks task as applicable
- `Task Name` or `Name` - Task description
- `Priority` - Task priority level
- `Time` or `Estimated Time` - Duration in minutes

### Optional Columns
- `Parent Task` - For creating subtasks
- `Notes` - Additional information
- `Section` - Section assignment

### BRD File Format
The BRD file should contain:
- `Name` or `Task Name` - For matching with templates
- `Device` or `Devices` - Device identifier
- `Previous Value` - Historical performance value
- `Perf_BRD` or `BRD` - BRD performance baseline

## File Naming Conventions

### Auto-Detection
- **BRD Files**: Must contain "Performance" or "BRD" in filename
  - Example: `Juno_Mainline_Performance_Results_Mar_J19.3 (6).xlsx`
  
### Export Format
- Generated CSV: `asana_import_YYYYMMDD_HHMMSS.csv`

## CSV Output Format

The application generates a CSV with 51 columns matching Asana's import format:

**Key Columns Populated:**
- Name, Section/Column, Projects, Parent task
- Estimated time, Priority, Device
- Iteration_01, Average, Perf_BRD
- Deviation % Current Vs BRD
- GREEN, YELLOW, RED
- Previous Value (from BRD lookup)

## Tips & Best Practices

### Task Organization
1. Create all sections before importing tasks
2. Use consistent parent task names for proper hierarchy
3. Review the Manual Tasks tab to verify structure

### Excel Template Tips
1. Use the "Applicable" column to control which tasks import
2. Keep task names consistent with BRD file for auto-matching
3. Include parent task names for proper nesting

### BRD Data Matching
- App uses fuzzy matching on task names and devices
- Exact matches preferred
- Falls back to default values if no match found

### Performance Optimization
- Import tasks by device for better organization
- Use Preview before importing large datasets
- Clear data between different projects

## Troubleshooting

### "Please install pandas" Error
```bash
pip install pandas openpyxl
```

### Tasks Not Showing in Preview
- Verify "Applicable" column has values
- Check Excel sheet name is selected
- Ensure template loaded successfully (green checkmark)

### BRD Data Not Matching
- Verify BRD file is loaded (green checkmark in header)
- Check task names match between template and BRD
- Verify device names match
- Select correct BRD sheet type (SBR vs Mainline)

### Import Issues in Asana
- Refresh preview to verify CSV structure
- Check all required fields are populated
- Ensure section names match exactly

## Advanced Features

### Manual Task Entry
Use the **Manual Tasks** tab for single task entry when needed

### Duplicate Prevention
- Review tasks in tree before importing more
- Use Clear All to start fresh

### Multi-Device Projects
1. Import each device separately
2. Select appropriate device each time
3. Keep same sections for consistency

## Support

For issues or questions about:
- **Application**: Check this README
- **Asana Import**: Consult Asana's CSV import documentation
- **Excel Format**: Review the sample CSV provided

## Version History

### V2.0 (Current)
- Excel template import
- BRD data integration
- Quick import interface
- Auto-file detection
- Device filtering
- Enhanced UI

### V1.0
- Basic CSV generation
- Manual task entry
- Section management

## File Structure
```
ASANA_Dashboard/
├── asana_csv_generator_v2.py  # Main application (Enhanced)
├── asana_csv_generator.py     # Original version
├── README.md                   # This file
├── J19.2_SBR_J19.3_Mainline.csv  # Sample format
└── Juno_Mainline_Performance_Results_Mar_J19.3 (6).xlsx  # BRD data
```

## License
For internal use only.
