"""
BRD Writer - Writes Average values from Asana CSV back to BRD Excel file.
Uses win32com (COM automation) for lossless Excel file editing on Windows.
Falls back to openpyxl if win32com is not available.
"""

import os
import shutil
import logging
from typing import Dict, List, Any, Tuple
from core.brd_matcher import BrdMatcher

logger = logging.getLogger('AsanaGenerator.BrdWriter')

# Try to import win32com for lossless Excel editing
try:
    import win32com.client
    HAS_WIN32COM = True
    logger.info("win32com available — using lossless Excel editing")
except ImportError:
    HAS_WIN32COM = False
    logger.info("win32com not available — falling back to openpyxl")


class BrdWriter:
    """
    Writes performance values (Average) from Asana CSV data back into the BRD Excel file.
    Matches scenarios using normalized name matching (same as BrdMatcher).
    
    Uses win32com (COM automation) for lossless file editing when available.
    Falls back to openpyxl otherwise.
    """

    def __init__(self):
        self.matcher = BrdMatcher()

    def write_averages_to_brd(self, brd_file_path: str, sheet_name: str,
                               target_col_index: int, scenario_col_index: int,
                               csv_tasks: List[Dict],
                               output_path: str = None,
                               dry_run: bool = False) -> Dict[str, Any]:
        """
        Write Average values from CSV tasks to the BRD Excel file.
        """
        if output_path is None:
            output_path = brd_file_path

        if HAS_WIN32COM and not dry_run:
            return self._write_with_win32com(
                brd_file_path, sheet_name, target_col_index, scenario_col_index,
                csv_tasks, output_path, dry_run
            )
        else:
            return self._write_with_openpyxl(
                brd_file_path, sheet_name, target_col_index, scenario_col_index,
                csv_tasks, output_path, dry_run
            )

    def _build_scenario_lookup(self, brd_rows, scenario_col_index):
        """Build normalized scenario → row index mapping from BRD data."""
        scenario_to_row = {}
        start_row = 3  # Skip first 2 header rows
        
        for row_idx in range(start_row - 1, len(brd_rows)):
            row = brd_rows[row_idx]
            if scenario_col_index < len(row):
                scenario_raw = row[scenario_col_index]
                normalized = self.matcher.normalize_scenario_name(scenario_raw)
                if normalized and normalized not in scenario_to_row:
                    scenario_to_row[normalized] = row_idx + 1  # 1-based
        
        return scenario_to_row

    def _match_tasks(self, csv_tasks, scenario_to_row):
        """Match CSV tasks to BRD rows by normalized scenario name."""
        matched = []
        unmatched = []
        
        for task in csv_tasks:
            scenario_name = task.get('Name', '')
            average = task.get('Average', '')
            perf_brd = task.get('Perf_BRD', '')
            prev_value = task.get('Previous Value', '')
            parent = task.get('Parent task', '')
            
            if not average or average in ['', '-', '0']:
                continue
            
            normalized = self.matcher.normalize_scenario_name(scenario_name)
            
            if normalized in scenario_to_row:
                row_num = scenario_to_row[normalized]
                matched.append({
                    'scenario': scenario_name,
                    'parent': parent,
                    'brd_row': row_num,
                    'old_value': '-',
                    'new_value': average,
                    'perf_brd': perf_brd,
                    'prev_value': prev_value,
                })
            else:
                unmatched.append({
                    'scenario': scenario_name,
                    'parent': parent,
                    'average': average,
                    'normalized': normalized,
                })
        
        return matched, unmatched

    def _write_with_win32com(self, brd_file_path, sheet_name, target_col_index,
                              scenario_col_index, csv_tasks, output_path, dry_run):
        """Write using win32com COM automation — lossless Excel editing."""
        import pythoncom
        pythoncom.CoInitialize()
        
        excel = None
        wb = None
        
        try:
            # Copy source file to output path first
            abs_src = os.path.abspath(brd_file_path)
            abs_dst = os.path.abspath(output_path)
            
            if abs_src != abs_dst:
                shutil.copy2(abs_src, abs_dst)
            
            # Open with Excel COM
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            
            wb = excel.Workbooks.Open(abs_dst)
            ws = wb.Sheets(sheet_name)
            
            # Read scenario column to build lookup
            max_row = ws.UsedRange.Rows.Count
            brd_rows = []
            for r in range(1, max_row + 1):
                scenario_val = ws.Cells(r, scenario_col_index + 1).Value
                brd_rows.append([scenario_val])
            
            # Build lookup (using simple list with just scenario col)
            scenario_to_row = {}
            start_row = 3
            for row_idx in range(start_row - 1, len(brd_rows)):
                scenario_raw = brd_rows[row_idx][0]
                normalized = self.matcher.normalize_scenario_name(scenario_raw)
                if normalized and normalized not in scenario_to_row:
                    scenario_to_row[normalized] = row_idx + 1
            
            logger.info(f"win32com: Built BRD lookup: {len(scenario_to_row)} scenarios")
            
            # Match tasks
            matched, unmatched = self._match_tasks(csv_tasks, scenario_to_row)
            
            # Read old values and write new values
            for m in matched:
                row_num = m['brd_row']
                col_num = target_col_index + 1  # 1-based
                
                old_val = ws.Cells(row_num, col_num).Value
                m['old_value'] = str(old_val) if old_val is not None else '-'
                
                try:
                    ws.Cells(row_num, col_num).Value = float(m['new_value'])
                except (ValueError, TypeError):
                    ws.Cells(row_num, col_num).Value = m['new_value']
            
            # Save
            wb.Save()
            logger.info(f"win32com: Saved {len(matched)} values to '{abs_dst}'")
            
            wb.Close(False)
            wb = None
            excel.Quit()
            excel = None
            
            pythoncom.CoUninitialize()
            
            return {
                'matched': matched,
                'unmatched': unmatched,
                'total_written': len(matched),
                'total_skipped': len(unmatched),
                'output_file': output_path,
                'dry_run': False,
            }
            
        except Exception as e:
            logger.error(f"win32com write failed: {e}, falling back to openpyxl")
            if wb:
                try: wb.Close(False)
                except: pass
            if excel:
                try: excel.Quit()
                except: pass
            try: pythoncom.CoUninitialize()
            except: pass
            
            # Fallback to openpyxl
            return self._write_with_openpyxl(
                brd_file_path, sheet_name, target_col_index, scenario_col_index,
                csv_tasks, output_path, dry_run
            )

    def _write_with_openpyxl(self, brd_file_path, sheet_name, target_col_index,
                              scenario_col_index, csv_tasks, output_path, dry_run):
        """Write using openpyxl — may cause Excel recovery warning on complex files."""
        import openpyxl
        
        wb = openpyxl.load_workbook(brd_file_path, keep_links=True)
        ws = wb[sheet_name]
        
        # Read all rows
        brd_rows = []
        for row in ws.iter_rows(min_row=1, values_only=False):
            brd_rows.append([cell.value for cell in row])
        
        logger.info(f"openpyxl: BRD sheet '{sheet_name}': {len(brd_rows)} rows")
        
        # Build lookup
        scenario_to_row = self._build_scenario_lookup(brd_rows, scenario_col_index)
        logger.info(f"openpyxl: Built BRD lookup: {len(scenario_to_row)} scenarios")
        
        # Match tasks
        matched, unmatched = self._match_tasks(csv_tasks, scenario_to_row)
        
        # Read old values and write new values
        for m in matched:
            row_num = m['brd_row']
            cell = ws.cell(row=row_num, column=target_col_index + 1)
            m['old_value'] = str(cell.value) if cell.value is not None else '-'
            
            if not dry_run:
                try:
                    cell.value = float(m['new_value'])
                except (ValueError, TypeError):
                    cell.value = m['new_value']
        
        if not dry_run and matched:
            wb.save(output_path)
            logger.info(f"openpyxl: Saved {len(matched)} values to '{output_path}'")
        
        wb.close()
        
        return {
            'matched': matched,
            'unmatched': unmatched,
            'total_written': len(matched) if not dry_run else 0,
            'total_skipped': len(unmatched),
            'output_file': output_path,
            'dry_run': dry_run,
        }
