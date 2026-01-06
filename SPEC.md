# Text Table Processing Tool - Specification

---

## 1. Project Overview

This project is a professional desktop GUI application for processing structured text
and displaying it in a powerful Excel-like table.

Primary goals:
- Fast text parsing
- Strong table interaction (sorting, filtering, selection)
- Batch text operations
- Flexible export
- Persistent settings
- Optional plugin scripting for power users

Target users:
- Technical users
- Analysts
- Developers

---

## 2. Technology Stack

- Language: Python 3
- GUI Framework: PySide6 (Qt)
- Table Framework:
  - QTableView
  - QAbstractTableModel
  - QSortFilterProxyModel (custom extensions allowed)
- Data Processing: pandas
- Export:
  - TXT / CSV: Python standard library
  - XLSX: openpyxl (via pandas)
- Settings Persistence: QSettings
- Platform:
  - Windows (primary)
  - Cross-platform compatible

---

## 3. Text Parsing

### 3.1 Input Format

Each line represents one record:
aaa----bbbb----cccc----dddd


Rules:
- Default delimiter: `----`
- One line = one row
- Split by delimiter into columns
- Trim whitespace
- Ignore empty lines
- Variable column counts allowed
- Missing columns padded with empty strings

### 3.2 Input Methods

- Drag & drop text files (.txt, .log, .csv)
- Drag & drop raw text
- Paste from clipboard
- Load multiple files at once (merge into one table)

---

## 4. Table View (Core)

### 4.1 Display

- Excel-like table using QTableView
- Alternating row colors
- Editable cells
- Auto column resize on initial load
- Row-based selection

### 4.2 Selection

- Multi-row selection (ExtendedSelection)
- Ctrl + Click
- Shift + Click
- Selecting any cell selects its entire row

---

## 5. Sorting

### 5.1 Column Sorting

- Click column header to sort ascending / descending
- Sorting applies to entire dataset
- Sorting respects current filtering

### 5.2 Global (Whole-Row) Sorting

- Provide buttons:
  - 整体排序（升序）
  - 整体排序（降序）
- Sorting logic:
  - For each row, build a key by joining all columns using `----`
  - Sort rows by this key
- Applies to current filtered view

---

## 6. Filtering (F1)

### 6.1 Global Filter

- Single search box
- Filters across all columns
- Case-insensitive

### 6.2 Per-Column Filtering

- Multiple filters active simultaneously (AND logic)
- Filter modes:
  - Contains
  - Not contains
  - Equals
  - Starts with
  - Ends with
  - Regex (optional)
- UI:
  - Filter panel with:
    - Column selector (including "All columns")
    - Mode selector
    - Value input
    - Apply / Clear buttons
- Show active filters summary
- Implement via proxy model(s)

---

## 7. Context Menu (Right Click)

### 7.1 Menu Items

- Copy Selected
- Delete Selected
- Invert Selection (反选)
- Select All (全选)

### 7.2 Copy Selected

- Copies selected rows to clipboard
- Format:
  - Columns joined by `----`
  - One row per line

### 7.3 Delete Selected

- Deletes selected rows from source model
- Must correctly map proxy indexes to source indexes
- Deletion processed in descending row order

### 7.4 Shortcuts

- Ctrl + C → Copy Selected
- Delete → Delete Selected
- Ctrl + A → Select All

---

## 8. Column Manager (F2)

### 8.1 Features

- Show / Hide columns
- Reorder columns
- Rename columns (display name only)

### 8.2 UI

- Column Manager dialog:
  - Column list with checkbox (visibility)
  - Move Up / Move Down buttons
  - Rename field
- Buttons:
  - OK
  - Cancel
  - Reset to default

### 8.3 Effects

- Column order affects:
  - Table display
  - Export order (unless overridden)
- Column state must persist

---

## 9. Batch Text Operations (F3)

### 9.1 Scope

User chooses:
- Selected cells
- Selected rows
- Entire table

User selects target columns.

### 9.2 Operations

#### 1. Replace
- Find → Replace
- Optional regex support

#### 2. Prefix / Suffix
- Add prefix to each cell
- Add suffix to each cell

#### 3. Split Column
- Split by user-defined delimiter
- Option:
  - Keep original column
  - Replace original column
- New columns inserted to the right

#### 4. Merge Columns
- Merge selected columns into a new column
- Join using user-defined delimiter (default `----`)
- Option:
  - Keep originals
  - Remove originals

### 9.3 UX

- "Batch Tools" dialog
- Tabs per operation
- Confirmation before destructive operations

---

## 10. Deduplication & Grouping (F4)

### 10.1 Deduplication

- Deduplicate rows based on selected columns
- Options:
  - Keep first occurrence
  - Keep last occurrence
- Show preview:
  - Number of rows to be removed

### 10.2 Grouping

- Group by selected columns
- Show:
  - Group keys
  - Count per group
- Group result shown in separate table/dialog
- Group summary exportable

---

## 11. Export

### 11.1 TXT Export

- File type: `.txt`
- Delimiter: `----`
- User selects:
  - Columns to export
  - Column order
- Export respects:
  - Sorting
  - Filtering
- Encoding: UTF-8 (no BOM)

### 11.2 CSV / XLSX Export

- Export current view
- Column order follows:
  - Column manager
  - Or export template

---

## 12. Export Templates (E1)

- Save named export profiles:
  - Export type (TXT / CSV / XLSX)
  - Selected columns & order
  - TXT delimiter
  - Export scope (current view)
- Load / Apply / Delete templates
- Templates persist across runs

---

## 13. Recent Files & Session Restore (E2)

### 13.1 Recent Files

- Maintain last 10 files
- Show in File menu
- Click to open

### 13.2 Session Restore

- Restore on startup:
  - Last dataset OR last opened files
  - Active filters
  - Column manager state
- Option:
  - Restore last session on startup (default ON)

---

## 14. Persistent Settings (E3)

Persist via QSettings:
- Window geometry
- Parsing delimiter
- Column visibility / order / names
- Active filters
- Export templates
- Recent files
- Session restore option
- Plugin settings

---

## 15. Plugin / Script System (E4)

### 15.1 Goal

Allow power users to process table data using Python scripts.

---

### 15.2 Script Format

Each script must define:

```python
def transform(df):
    """
    df: pandas.DataFrame
    return: pandas.DataFrame
    """
    return df
Rules:

Input is a pandas DataFrame

Must return a pandas DataFrame

Returned DataFrame replaces current dataset

Column names and order come from returned DataFrame

15.3 Execution

User selects a .py script to run

Execution scope:

Full dataset

Current filtered view

App passes a copy of the DataFrame

Script runs synchronously

15.4 Error Handling & Safety

Show warning before execution:

"Python scripts can execute arbitrary code on your machine"

Capture:

stdout

stderr

If script raises exception:

Show readable error

Do NOT modify current data

If return value invalid:

Show error message

15.5 Logging & Feedback

Show execution log

Show summary:

Rows before / after

Columns before / after

15.6 Dry Run (Optional)

Dry run executes script without applying result

Show preview statistics only

15.7 Script Management UI

Plugins menu:

Run Script

Manage Scripts

Open Scripts Folder

Default script folder: ./scripts

Script folder path must persist

15.8 Persistence

Persist:

Script folder path

Last executed script

Last execution scope

15.9 Non-Goals

Script sandboxing

Network isolation

Permission control

16. Non-Goals

Database storage

Cloud sync

User authentication

17. Code Quality Requirements

Modular structure

Clear separation of concerns

No hard-coded paths

Extendable design

Avoid unnecessary refactoring