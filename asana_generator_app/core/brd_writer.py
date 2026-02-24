"""
BRD Writer - Writes Average values from Asana CSV back to BRD Excel file.
Uses openpyxl to update specific cells in the BRD spreadsheet.
"""

import logging
import openpyxl
from typing import Dict, List, Any, Tuple
from core.brd_matcher import BrdMatcher

logger = logging.getLogger('AsanaGenerator.BrdWriter')


class BrdWriter:
    """
    Writes performance values (Average) from Asana CSV data back into the BRD Excel file.
    Matches scenarios using normalized name matching (same as BrdMatcher).
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
        
        Args:
            brd_file_path: Path to the BRD Excel file
            sheet_name: Sheet name in the BRD file
            target_col_index: Column index (0-based) where Average should be written
            scenario_col_index: Column index (0-based) of the Performance Scenario column in BRD
            csv_tasks: List of task dicts from CsvImporter (subtasks with Average values)
            output_path: Output file path (if None, overwrites original)
            dry_run: If True, don't actually write — just preview what would change
            
        Returns:
            Dict with results:
                'matched': List of matched scenarios with old/new values
                'unmatched': List of CSV scenarios that couldn't be matched in BRD
                'total_written': Number of cells written
                'output_file': Path to the output file
        """
        if output_path is None:
            output_path = brd_file_path
        
        # Load workbook with openpyxl (NOT read_only — need write access)
        wb = openpyxl.load_workbook(brd_file_path)
        ws = wb[sheet_name]
        
        # Build BRD scenario lookup from the sheet
        # Read all rows and create normalized scenario → row mapping
        brd_rows = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=1, values_only=False), start=1):
            cells = [cell.value for cell in row]
            brd_rows.append(cells)
        
        logger.info(f"BRD sheet '{sheet_name}': {len(brd_rows)} rows, "
                    f"scenario_col={scenario_col_index}, target_col={target_col_index}")
        
        # Build normalized scenario → row index mapping (skip header rows)
        scenario_to_row = {}
        start_row = 3  # Skip first 2 header rows (typical BRD format)
        
        for row_idx in range(start_row - 1, len(brd_rows)):
            row = brd_rows[row_idx]
            if scenario_col_index < len(row):
                scenario_raw = row[scenario_col_index]
                normalized = self.matcher.normalize_scenario_name(scenario_raw)
                if normalized:
                    # Store first occurrence only (avoid duplicates)
                    if normalized not in scenario_to_row:
                        scenario_to_row[normalized] = row_idx + 1  # 1-based for openpyxl
        
        logger.info(f"Built BRD scenario lookup: {len(scenario_to_row)} unique scenarios")
        
        # Match CSV tasks to BRD rows and collect writes
        matched = []
        unmatched = []
        
        for task in csv_tasks:
            scenario_name = task.get('Name', '')
            average = task.get('Average', '')
            perf_brd = task.get('Perf_BRD', '')
            prev_value = task.get('Previous Value', '')
            parent = task.get('Parent task', '')
            
            # Skip tasks without Average value
            if not average or average in ['', '-', '0']:
                continue
            
            # Normalize scenario name for matching
            normalized = self.matcher.normalize_scenario_name(scenario_name)
            
            if normalized in scenario_to_row:
                row_num = scenario_to_row[normalized]
                
                # Get current value in target cell
                # openpyxl is 1-based, column index needs +1
                current_cell = ws.cell(row=row_num, column=target_col_index + 1)
                old_value = current_cell.value
                
                matched.append({
                    'scenario': scenario_name,
                    'parent': parent,
                    'brd_row': row_num,
                    'old_value': str(old_value) if old_value else '-',
                    'new_value': average,
                    'perf_brd': perf_brd,
                    'prev_value': prev_value,
                })
                
                if not dry_run:
                    # Try to write as number if possible
                    try:
                        current_cell.value = float(average)
                    except (ValueError, TypeError):
                        current_cell.value = average
            else:
                unmatched.append({
                    'scenario': scenario_name,
                    'parent': parent,
                    'average': average,
                    'normalized': normalized,
                })
        
        # Save workbook
        if not dry_run and matched:
            wb.save(output_path)
            logger.info(f"BRD file saved: {len(matched)} values written to '{output_path}'")
        
        wb.close()
        
        result = {
            'matched': matched,
            'unmatched': unmatched,
            'total_written': len(matched) if not dry_run else 0,
            'total_skipped': len(unmatched),
            'output_file': output_path,
            'dry_run': dry_run,
        }
        
        logger.info(f"Write results: {len(matched)} matched, {len(unmatched)} unmatched, "
                    f"dry_run={dry_run}")
        
        return result