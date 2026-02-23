"""
BRD Matcher - Matches Template scenarios to BRD rows and extracts performance values.
Device filtering is done by Template's 'Applicable Devices' column, NOT by BRD.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
import logging

logger = logging.getLogger('AsanaGenerator.BrdMatcher')

class BrdMatcher:
    """
    Handles logic for matching Template Tasks to BRD Rows.
    
    IMPORTANT: Device applicability is determined by Template's 'Applicable Devices' column.
    This matcher only finds matching BRD rows and extracts performance values.
    """

    @staticmethod
    def normalize_scenario_name(name: Any) -> str:
        """
        Normalize scenario names for matching.
        Matches web app's normalizeScenarioName function.
        """
        if name is None or str(name).lower() == 'nan':
            return ""
        text = str(name).lower().strip()
        # Remove special characters (keep only alphanumeric and spaces)
        text = re.sub(r'[^\w\s]', '', text)
        # Collapse multiple spaces to single space
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def sanitize_numeric_value(value: Any) -> str:
        """
        Sanitize BRD values to ensure only numeric values are returned.
        Converts text values like 'NA', 'Blocked', 'YTU' to '0'.
        
        Args:
            value: Raw value from BRD cell
            
        Returns:
            '0' if non-numeric, string representation of number if numeric, '-' if empty
        """
        if value is None or str(value).strip() == '':
            return '-'
        
        val_str = str(value).strip().lower()
        
        # Check for empty/nan values
        if val_str in ['', 'nan', 'none']:
            return '-'
        
        # Check for text values that should become '0'
        text_values = ['na', 'n/a', 'blocked', 'ytu', 'yet to update', 'tbd', 'to be determined']
        if val_str in text_values:
            return '0'
        
        # Try to parse as number
        try:
            # Remove any commas (e.g., "1,234" -> "1234")
            cleaned = val_str.replace(',', '')
            float(cleaned)  # Test if it's numeric
            return cleaned  # Return the numeric string
        except ValueError:
            # Not a number - return '0' for any other text
            return '0'


    @staticmethod
    def find_column_index(headers: List[Any], predicate) -> int:
        """Find column index where predicate returns True."""
        for idx, header in enumerate(headers):
            if predicate(header):
                return idx
        return -1

    @staticmethod
    def find_column_in_rows(row0: List[Any], row1: List[Any], predicate) -> int:
        """Find column index in either of two header rows."""
        # Try second row first (often has more specific headers)
        if row1:
            idx = BrdMatcher.find_column_index(row1, predicate)
            if idx != -1:
                return idx
        # Fall back to first row
        if row0:
            return BrdMatcher.find_column_index(row0, predicate)
        return -1

    def find_oobe_columns(self, brd_data: List[List[Any]]) -> Tuple[int, int]:
        """
        Find OOBE-specific columns in BRD data.
        
        Returns:
            Tuple of (component_col_index, priority_col_index)
            Returns -1 for columns that are not found
        """
        if not brd_data or len(brd_data) < 2:
            return -1, -1
        
        headers0 = brd_data[0]
        headers1 = brd_data[1] if len(brd_data) > 1 else []
        
        # Find "New_Dashboard_Component" column (must have "new" to avoid matching "Dashboard Component")
        def is_component_col(h):
            h_str = str(h or '').lower().replace('_', '').replace(' ', '')
            # Only match if it contains "new" + "dashboard" + "component"
            return 'newdashboardcomponent' in h_str
        
        component_col = self.find_column_in_rows(headers0, headers1, is_component_col)
        
        # Find "Priority" column
        def is_priority_col(h):
            h_str = str(h or '').lower().strip()
            return h_str == 'priority'
        
        priority_col = self.find_column_in_rows(headers0, headers1, is_priority_col)
        
        return component_col, priority_col

    def get_brd_data_for_task(self, scenario_name: str, device: str, 
                              brd_data: List[List[Any]], 
                              perf_col_index: int, prev_col_index: int,
                              debug: bool = False) -> Dict[str, Any]:
        """
        Get BRD data for a specific task.
        
        NOTE: This does NOT filter by device. Device filtering is done using
        Template's 'Applicable Devices' column in the main window.
        
        Args:
            scenario_name: The task/scenario name to match
            device: Target device (currently only used for logging)
            brd_data: Raw BRD data as list of lists (first row(s) are headers)
            perf_col_index: Index of the Perf BRD column (-1 if not selected)
            prev_col_index: Index of the Previous Value column (-1 if not selected)
            debug: Whether to print debug info
            
        Returns:
            Dict with {applicable, perf_value, prev_value}
        """
        # Default result - if no BRD data, task is still applicable (just no BRD values)
        if not brd_data or not scenario_name or len(brd_data) < 2:
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

        # Check both first and second rows for headers (BRDs often have multi-row headers)
        # UPDATED: Scan first 10 rows to find "Performance Scenario" column
        scan_rows = brd_data[:10]
        
        def is_performance_scenario_col(h):
            h_str = str(h or '').lower()
            # Handle common typos and variations
            return ('performance scenario' in h_str or 
                    'performance scanrio' in h_str or
                    'performance scenarios' in h_str)
        
        def is_any_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or 
                    'performance scanrio' in h_str or
                    'scenario name' in h_str or 
                    ('performance' in h_str and 'sc' in h_str) or # Very loose fallback
                    h_str == 'name')
        
        # Helper to find ALL matching columns in scan rows
        def find_all_cols_in_scan_rows(predicate):
            found = set()
            for r_idx, row in enumerate(scan_rows):
                for c_idx, val in enumerate(row):
                    if predicate(val):
                        found.add(c_idx)
            return sorted(found)

        # Helper to find the column closest to (and before) a reference column
        def find_nearest_col(candidates, ref_col):
            if not candidates:
                return -1
            if ref_col == -1:
                return candidates[0]  # No reference, use first found
            
            # Prefer columns BEFORE the perf/prev columns (scenario usually comes first)
            before = [c for c in candidates if c < ref_col]
            if before:
                return before[-1]  # Closest one before reference
            return candidates[0]  # Fallback to first found

        # Reference column = min of perf/prev (the selected value columns)
        ref_col = -1
        if perf_col_index != -1 and prev_col_index != -1:
            ref_col = min(perf_col_index, prev_col_index)
        elif perf_col_index != -1:
            ref_col = perf_col_index
        elif prev_col_index != -1:
            ref_col = prev_col_index

        # First try to find "Performance Scenario" specifically
        perf_scenario_cols = find_all_cols_in_scan_rows(is_performance_scenario_col)
        scenario_col_idx = find_nearest_col(perf_scenario_cols, ref_col)
        
        # If not found, fall back to any scenario-like column
        if scenario_col_idx == -1:
            any_scenario_cols = find_all_cols_in_scan_rows(is_any_scenario_col)
            scenario_col_idx = find_nearest_col(any_scenario_cols, ref_col)

        # If we can't find scenario column, return applicable with no values
        if scenario_col_idx == -1:
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

        # Normalize the input scenario name
        normalized_scenario = self.normalize_scenario_name(scenario_name)
        
        # Log row width for diagnostic
        max_cols = max(len(row) for row in brd_data) if brd_data else 0
        logger.info(f"Standard match: scenario='{scenario_name}' -> normalized='{normalized_scenario}', "
                     f"scenario_col={scenario_col_idx}, perf_col={perf_col_index}, prev_col={prev_col_index}, "
                     f"brd_max_cols={max_cols}, brd_rows={len(brd_data)}")
        
        # Search through data rows (start from row 2 to skip headers)
        start_row = 2
        match_count = 0
        logged_samples = 0

        for row_idx, row in enumerate(brd_data[start_row:], start=start_row):
            if not row or len(row) == 0:
                continue

            # Get and normalize row scenario
            row_scenario_raw = row[scenario_col_idx] if scenario_col_idx < len(row) else ''
            row_scenario = self.normalize_scenario_name(row_scenario_raw)
            
            # Log first few BRD scenario names for debugging
            if logged_samples < 3 and row_scenario:
                logger.info(f"  BRD row {row_idx} scenario: '{row_scenario}' (cols={len(row)})")
                logged_samples += 1
            
            # Check for match
            if row_scenario != normalized_scenario:
                continue

            match_count += 1
            logger.info(f"  ✓ MATCH at row {row_idx}: row_len={len(row)}, "
                       f"perf_col={perf_col_index} (in_range={perf_col_index < len(row)}), "
                       f"prev_col={prev_col_index} (in_range={prev_col_index < len(row)})")
            
            # Found a match! Extract and sanitize values (NO device filtering here)
            perf_value = '-'
            if perf_col_index != -1 and perf_col_index < len(row):
                val = row[perf_col_index]
                perf_value = self.sanitize_numeric_value(val)
                logger.info(f"    perf raw='{val}' -> '{perf_value}'")
            else:
                logger.info(f"    perf col {perf_col_index} OUT OF RANGE (row has {len(row)} cols)")

            prev_value = '-'
            if prev_col_index != -1 and prev_col_index < len(row):
                val = row[prev_col_index]
                prev_value = self.sanitize_numeric_value(val)
                logger.info(f"    prev raw='{val}' -> '{prev_value}'")
            else:
                logger.info(f"    prev col {prev_col_index} OUT OF RANGE (row has {len(row)} cols)")

            return {
                'applicable': True,
                'perf_value': perf_value,
                'prev_value': prev_value
            }

        # No match found in BRD - task is still applicable, just no BRD values
        logger.info(f"  ✗ NO MATCH found for '{normalized_scenario}' in {len(brd_data)-start_row} data rows")
        return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

    def get_brd_data_for_oobe_task(self, scenario_name: str, device: str,
                                    component: str, sub_priority: str,
                                    brd_data: List[List[Any]], 
                                    perf_col_index: int, prev_col_index: int,
                                    debug: bool = False) -> Dict[str, Any]:
        """
        Enhanced BRD matching for OOBE tasks with multi-criteria matching.
        
        Matches on 5 criteria:
        1. Scenario Name (normalized)
        2. Device (from Template Applicable Devices - checked in main window)
        3. Dashboard Component (New_Dashboard_Component column)
        4. Priority (Sub_Priority in Template matches Priority in BRD)
        5. BRD row existence
        
        Args:
            scenario_name: The task/scenario name to match
            device: Target device (for logging only)
            component: Dashboard component value (e.g., "1X_Decanter_OOBE")
            sub_priority: Priority value (e.g., "P1", "P2")
            brd_data: Raw BRD data as list of lists
            perf_col_index: Index of the Perf BRD column
            prev_col_index: Index of the Previous Value column
            debug: Whether to print debug info
            
        Returns:
            Dict with {applicable, perf_value, prev_value}
        """
        # Default result
        if not brd_data or not scenario_name or len(brd_data) < 2:
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

        # Find scenario column (same as standard matching)
        headers0 = brd_data[0] if len(brd_data) > 0 else []
        headers1 = brd_data[1] if len(brd_data) > 1 else []

        def is_performance_scenario_col(h):
            h_str = str(h or '').lower()
            return 'performance scenario' in h_str
        
        def is_any_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or 
                    'scenario name' in h_str or 
                    h_str == 'name')
        
        scenario_col_idx = self.find_column_in_rows(headers0, headers1, is_performance_scenario_col)
        if scenario_col_idx == -1:
            scenario_col_idx = self.find_column_in_rows(headers0, headers1, is_any_scenario_col)

        if scenario_col_idx == -1:
            if debug:
                print(f"[DEBUG OOBE] No scenario column found")
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

        # Find OOBE-specific columns
        component_col, priority_col = self.find_oobe_columns(brd_data)
        
        # AUTO-DETECT BRD COLUMNS (override passed indices which may be from Template)
        # Scan first 5 rows to find headers, as they may be in different rows
        scan_rows = brd_data[:5]
        
        def find_col_in_any_row(predicate):
            for r_idx, row in enumerate(scan_rows):
                for c_idx, val in enumerate(row):
                    if predicate(val):
                        return c_idx
            return -1

        def is_perf_brd_col(h):
            h_str = str(h or '').lower().replace('_', '').replace(' ', '')
            return 'perfbrd' in h_str or ('brd' in h_str and 'perf' in h_str) or ('result' in h_str and 'brd' in h_str)
        
        def is_previous_col(h):
            h_str = str(h or '').lower().replace('_', '').replace(' ', '')
            return 'previousvalue' in h_str or h_str == 'previous' or ('baseline' in h_str and 'pisco' in h_str) or 'previous' in h_str
        
        auto_perf_col = find_col_in_any_row(is_perf_brd_col)
        auto_prev_col = find_col_in_any_row(is_previous_col)
        
        # Use auto-detected columns if found, otherwise fall back to passed indices
        final_perf_col = auto_perf_col if auto_perf_col != -1 else perf_col_index
        final_prev_col = auto_prev_col if auto_prev_col != -1 else prev_col_index

        # Normalize inputs
        normalized_scenario = self.normalize_scenario_name(scenario_name)
        normalized_component = str(component).strip()
        normalized_priority = str(sub_priority).strip().upper()
        
        # Search through data rows
        start_row = 2
        for row_idx, row in enumerate(brd_data[start_row:], start=start_row):
            if not row or len(row) == 0:
                continue

            # MATCH 1: Scenario name
            row_scenario_raw = row[scenario_col_idx] if scenario_col_idx < len(row) else ''
            row_scenario = self.normalize_scenario_name(row_scenario_raw)
            
            if row_scenario != normalized_scenario:
                continue

            # MATCH 2: Dashboard Component (REQUIRED if component provided)
            # For OOBE, component should ALWAYS be provided and matched
            if normalized_component:  # Component is provided (should always be for OOBE)
                if component_col == -1:
                    # Component column not found in BRD - can't match
                    print(f"❌ Component column NOT FOUND in BRD!")
                    return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}
                
                row_component = str(row[component_col] if component_col < len(row) else '').strip()
                
                if row_component != normalized_component:
                    continue

            # All criteria matched!
            # Extract and sanitize values
            perf_value = '-'
            if final_perf_col != -1 and final_perf_col < len(row):
                raw_perf = row[final_perf_col]
                perf_value = self.sanitize_numeric_value(raw_perf)

            prev_value = '-'
            if final_prev_col != -1 and final_prev_col < len(row):
                raw_prev = row[final_prev_col]
                prev_value = self.sanitize_numeric_value(raw_prev)

            return {
                'applicable': True,
                'perf_value': perf_value,
                'prev_value': prev_value
            }

        # No match found
        return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}

    def find_new_feature_column(self, brd_data: List[List[Any]]) -> int:
        """
        Find a 'New Feature' column in BRD data headers.
        
        This identifies BRD sheets that group multiple feature categories
        (e.g., Color Stroke, HWR Search, Keyboard Canvas) in a single sheet.
        
        Args:
            brd_data: Raw BRD data as list of lists
            
        Returns:
            Column index if found, -1 otherwise
        """
        if not brd_data or len(brd_data) < 1:
            return -1
        
        # Scan first few rows for "New Feature" or "Feature" column
        scan_rows = brd_data[:5]
        
        def is_new_feature_col(h):
            h_str = str(h or '').lower().strip()
            return (h_str == 'new feature' or 
                    h_str == 'new_feature' or
                    h_str == 'feature category' or
                    h_str == 'feature_category' or
                    'new feature' in h_str or
                    'new_feature' in h_str)
        
        for row in scan_rows:
            for c_idx, val in enumerate(row):
                if is_new_feature_col(val):
                    return c_idx
        
        return -1

    def get_brd_data_for_new_feature_task(self, scenario_name: str, device: str,
                                           feature_category: str,
                                           brd_data: List[List[Any]],
                                           perf_col_index: int, prev_col_index: int,
                                           debug: bool = False) -> Dict[str, Any]:
        """
        BRD matching for 'New Feature' sheets that contain multiple feature categories.
        
        Matches on:
        1. Scenario Name (normalized)
        2. Feature Category (from 'New Feature' column in BRD matching Template's Priority)
        
        Args:
            scenario_name: The task/scenario name to match
            device: Target device (for logging only)
            feature_category: Feature category from Template's Priority column
            brd_data: Raw BRD data as list of lists
            perf_col_index: Index of the Perf BRD column
            prev_col_index: Index of the Previous Value column
            debug: Whether to print debug info
            
        Returns:
            Dict with {applicable, perf_value, prev_value}
        """
        if not brd_data or not scenario_name or len(brd_data) < 2:
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}
        
        # Find the New Feature column
        feature_col_idx = self.find_new_feature_column(brd_data)
        if feature_col_idx == -1:
            # No New Feature column - fall back to standard matching
            logger.info(f"New Feature match: no 'New Feature' column found, falling back to standard match")
            return self.get_brd_data_for_task(
                scenario_name, device, brd_data, perf_col_index, prev_col_index, debug
            )
        
        # Find scenario column - use nearest-to-perf/prev logic (same as standard match)
        scan_rows = brd_data[:10]
        
        def is_performance_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or 
                    'performance scanrio' in h_str or
                    'performance scenarios' in h_str)
        
        def is_any_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or 
                    'performance scanrio' in h_str or
                    'scenario name' in h_str or 
                    ('performance' in h_str and 'sc' in h_str) or
                    h_str == 'name')
        
        def find_all_cols_in_scan_rows(predicate):
            found = set()
            for r_idx, row in enumerate(scan_rows):
                for c_idx, val in enumerate(row):
                    if predicate(val):
                        found.add(c_idx)
            return sorted(found)

        def find_nearest_col(candidates, ref_col):
            if not candidates:
                return -1
            if ref_col == -1:
                return candidates[0]
            before = [c for c in candidates if c < ref_col]
            if before:
                return before[-1]
            return candidates[0]

        ref_col = -1
        if perf_col_index != -1 and prev_col_index != -1:
            ref_col = min(perf_col_index, prev_col_index)
        elif perf_col_index != -1:
            ref_col = perf_col_index
        elif prev_col_index != -1:
            ref_col = prev_col_index

        perf_scenario_cols = find_all_cols_in_scan_rows(is_performance_scenario_col)
        scenario_col_idx = find_nearest_col(perf_scenario_cols, ref_col)
        
        if scenario_col_idx == -1:
            any_scenario_cols = find_all_cols_in_scan_rows(is_any_scenario_col)
            scenario_col_idx = find_nearest_col(any_scenario_cols, ref_col)
        
        if scenario_col_idx == -1:
            logger.info(f"New Feature match: no scenario column found")
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}
        
        # Normalize inputs
        normalized_scenario = self.normalize_scenario_name(scenario_name)
        normalized_feature = self.normalize_scenario_name(feature_category)
        
        max_cols = max(len(row) for row in brd_data) if brd_data else 0
        logger.info(f"New Feature match: scenario='{scenario_name}' -> '{normalized_scenario}', "
                    f"feature='{feature_category}' -> '{normalized_feature}', "
                    f"scenario_col={scenario_col_idx}, feature_col={feature_col_idx}, "
                    f"perf_col={perf_col_index}, prev_col={prev_col_index}, brd_max_cols={max_cols}")
        
        # Search through data rows
        start_row = 2
        logged_samples = 0
        for row_idx, row in enumerate(brd_data[start_row:], start=start_row):
            if not row or len(row) == 0:
                continue
            
            # MATCH 1: Scenario name
            row_scenario_raw = row[scenario_col_idx] if scenario_col_idx < len(row) else ''
            row_scenario = self.normalize_scenario_name(row_scenario_raw)
            
            # Log first few for debugging
            if logged_samples < 3 and row_scenario:
                row_feature_sample = row[feature_col_idx] if feature_col_idx < len(row) else ''
                logger.info(f"  BRD row {row_idx}: scenario='{row_scenario}', feature='{row_feature_sample}'")
                logged_samples += 1
            
            if row_scenario != normalized_scenario:
                continue
            
            # MATCH 2: Feature category (skip check if BRD feature cell is empty - likely merged cell)
            row_feature_raw = row[feature_col_idx] if feature_col_idx < len(row) else ''
            row_feature = self.normalize_scenario_name(row_feature_raw)
            
            logger.info(f"  Scenario match at row {row_idx}: brd_feature='{row_feature}' vs template_feature='{normalized_feature}'")
            
            # Only filter by feature if BOTH template feature AND BRD feature are non-empty
            # Empty BRD feature = merged cell or section-based grouping, don't reject
            if normalized_feature and row_feature and row_feature != normalized_feature:
                continue
            
            # Match found! Extract values
            perf_value = '-'
            if perf_col_index != -1 and perf_col_index < len(row):
                perf_value = self.sanitize_numeric_value(row[perf_col_index])
                logger.info(f"    ✓ perf raw='{row[perf_col_index]}' -> '{perf_value}'")
            else:
                logger.info(f"    perf col {perf_col_index} OUT OF RANGE (row has {len(row)} cols)")
            
            prev_value = '-'
            if prev_col_index != -1 and prev_col_index < len(row):
                prev_value = self.sanitize_numeric_value(row[prev_col_index])
                logger.info(f"    ✓ prev raw='{row[prev_col_index]}' -> '{prev_value}'")
            else:
                logger.info(f"    prev col {prev_col_index} OUT OF RANGE (row has {len(row)} cols)")
            
            return {
                'applicable': True,
                'perf_value': perf_value,
                'prev_value': prev_value
            }
        
        # No match found with feature filter - fall back to standard matching (scenario only)
        logger.info(f"  ✗ NO MATCH for new feature: '{normalized_scenario}' + '{normalized_feature}', "
                    f"falling back to standard match")
        return self.get_brd_data_for_task(
            scenario_name, device, brd_data, perf_col_index, prev_col_index, debug
        )

    def batch_match(self, tasks: List[Dict[str, Any]], device: str,
                    brd_data: List[List[Any]], 
                    perf_col_index: int, prev_col_index: int) -> List[Dict[str, Any]]:
        """
        Batch match multiple tasks against BRD data.
        
        NOTE: This does NOT filter by device. All tasks are returned with BRD data added.
        
        Returns list of tasks with BRD data added.
        """
        matched_tasks = []
        
        for task in tasks:
            # Try multiple possible scenario column names
            scenario = (task.get('Performance Scenario') or 
                       task.get('Scenario Name') or 
                       task.get('Name', ''))
            if not scenario:
                continue
                
            brd_match = self.get_brd_data_for_task(
                scenario, device, brd_data, perf_col_index, prev_col_index
            )
            
            task_with_brd = task.copy()
            task_with_brd['Perf_BRD'] = brd_match['perf_value']
            task_with_brd['Previous Value'] = brd_match['prev_value']
            task_with_brd['Device'] = device
            matched_tasks.append(task_with_brd)
                
        return matched_tasks
