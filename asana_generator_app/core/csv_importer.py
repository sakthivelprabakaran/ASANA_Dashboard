"""
CSV Importer - Parses Asana exported CSV files for the Report Generator.
Extracts sections, parent tasks, subtasks with their Average, Perf_BRD, and Previous Value.
"""

import logging
import pandas as pd
from typing import Dict, List, Any, Optional

logger = logging.getLogger('AsanaGenerator.CsvImporter')


class CsvImporter:
    """
    Parses Asana exported CSV files and builds a structured representation
    of sections, parent tasks, and subtasks with performance data.
    """

    # Key columns we extract from Asana CSV
    KEY_COLUMNS = [
        'Name', 'Section/Column', 'Parent task', 'Projects', 'Devices',
        'Average', 'Perf_BRD', 'Previous Value', 'Priority',
        'BRD Status', 'Previous Status', 'Deviation % Current Vs BRD',
        'Deviation % Current vs Previous', 'Estimated time',
        'Iteration_01', 'Iteration_02', 'Iteration_03', 'Iteration_04',
        'iteration_05', 'iteration_06', 'iteration_07', 'iteration_08',
        'iteration_09', 'iteration_10', 'Iteration count',
        'GREEN', 'YELLOW', 'RED', 'Assignee', 'Task Progress',
        'Tester Remark', 'Audited By', 'Auditor Pass'
    ]

    @staticmethod
    def load_csv(file_path: str) -> pd.DataFrame:
        """
        Load an Asana exported CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            DataFrame with all CSV data
        """
        try:
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
            logger.info(f"CSV loaded: {len(df)} rows, {len(df.columns)} columns from '{file_path}'")
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV '{file_path}': {e}")
            raise Exception(f"Failed to load CSV file: {str(e)}")

    @staticmethod
    def parse_asana_csv(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Parse Asana CSV into structured data.
        
        Asana CSV structure:
        - Rows with Section/Column but no Parent task = Section headers or parent tasks
        - Rows with Parent task = Subtasks
        - Parent tasks have Section/Column and Projects set
        - Subtasks have Parent task set but Section/Column is empty
        
        Returns:
            Dict with:
                'tasks': List of all task dicts (flat list)
                'parent_tasks': List of unique parent task names
                'sections': List of unique section names
                'projects': List of unique project names
                'devices': List of unique device names
                'summary': Dict with counts
        """
        tasks = []
        parent_tasks = set()
        sections = set()
        projects = set()
        devices = set()
        
        for _, row in df.iterrows():
            name = str(row.get('Name', '')).strip()
            if not name:
                continue
            
            parent_task = str(row.get('Parent task', '')).strip()
            section = str(row.get('Section/Column', '')).strip()
            project = str(row.get('Projects', '')).strip()
            device = str(row.get('Devices', '')).strip()
            
            # Skip section-only rows (rows that are just section headers)
            # These typically have Section/Column set but no other meaningful data
            # In Asana export, section rows have Name = section name and no Parent task
            
            # Determine row type
            is_subtask = bool(parent_task)
            is_parent = bool(section) and not is_subtask
            
            # Collect unique values
            if parent_task:
                parent_tasks.add(parent_task)
            if section:
                sections.add(section)
            if project:
                projects.add(project)
            if device:
                devices.add(device)
            
            # Extract performance values
            average = str(row.get('Average', '')).strip()
            perf_brd = str(row.get('Perf_BRD', '')).strip()
            prev_value = str(row.get('Previous Value', '')).strip()
            priority = str(row.get('Priority', '')).strip()
            brd_status = str(row.get('BRD Status', '')).strip()
            prev_status = str(row.get('Previous Status', '')).strip()
            deviation_brd = str(row.get('Deviation % Current Vs BRD', '')).strip()
            deviation_prev = str(row.get('Deviation % Current vs Previous', '')).strip()
            
            task = {
                'Name': name,
                'Parent task': parent_task,
                'Section/Column': section,
                'Projects': project,
                'Devices': device,
                'Average': average,
                'Perf_BRD': perf_brd,
                'Previous Value': prev_value,
                'Priority': priority,
                'BRD Status': brd_status,
                'Previous Status': prev_status,
                'Deviation_BRD': deviation_brd,
                'Deviation_Prev': deviation_prev,
                'is_subtask': is_subtask,
                'is_parent': is_parent,
            }
            
            # Add iteration values
            for iter_col in ['Iteration_01', 'Iteration_02', 'Iteration_03', 
                           'Iteration_04', 'iteration_05', 'iteration_06',
                           'iteration_07', 'iteration_08', 'iteration_09', 'iteration_10']:
                task[iter_col] = str(row.get(iter_col, '')).strip()
            
            task['Iteration count'] = str(row.get('Iteration count', '')).strip()
            task['Assignee'] = str(row.get('Assignee', '')).strip()
            task['Task Progress'] = str(row.get('Task Progress', '')).strip()
            task['Tester Remark'] = str(row.get('Tester Remark', '')).strip()
            task['GREEN'] = str(row.get('GREEN', '')).strip()
            task['YELLOW'] = str(row.get('YELLOW', '')).strip()
            task['RED'] = str(row.get('RED', '')).strip()
            
            tasks.append(task)
        
        # Sort parent tasks and other lists
        result = {
            'tasks': tasks,
            'parent_tasks': sorted(parent_tasks),
            'sections': sorted(sections),
            'projects': sorted(projects),
            'devices': sorted(devices),
            'summary': {
                'total_rows': len(tasks),
                'subtasks': sum(1 for t in tasks if t['is_subtask']),
                'parent_tasks': len(parent_tasks),
                'sections': len(sections),
                'with_average': sum(1 for t in tasks if t['Average'] and t['Average'] not in ['', '-', '0']),
            }
        }
        
        logger.info(f"CSV parsed: {result['summary']['total_rows']} rows, "
                    f"{result['summary']['subtasks']} subtasks, "
                    f"{result['summary']['parent_tasks']} parent tasks, "
                    f"{result['summary']['with_average']} with Average values")
        
        return result

    @staticmethod
    def filter_tasks(tasks: List[Dict], 
                     parent_task: str = None,
                     section: str = None,
                     device: str = None,
                     search: str = None,
                     subtasks_only: bool = True) -> List[Dict]:
        """
        Filter tasks by various criteria.
        
        Args:
            tasks: List of task dicts
            parent_task: Filter by parent task name (exact match)
            section: Filter by section name
            device: Filter by device name
            search: Search in scenario name (case-insensitive)
            subtasks_only: If True, only return subtasks (not parent task rows)
            
        Returns:
            Filtered list of task dicts
        """
        filtered = tasks
        
        if subtasks_only:
            filtered = [t for t in filtered if t.get('is_subtask', False)]
        
        if parent_task and parent_task != 'All':
            filtered = [t for t in filtered if t.get('Parent task', '') == parent_task]
        
        if section and section != 'All':
            # For subtasks, section comes from the parent task, not the subtask itself
            # We need to check if the parent task's section matches
            # But subtasks don't have Section/Column set — their parent does
            # So we filter by checking parent tasks that belong to the section
            filtered = [t for t in filtered 
                       if t.get('Section/Column', '') == section or
                       t.get('_parent_section', '') == section]
        
        if device and device != 'All':
            device_lower = device.lower().strip()
            filtered = [t for t in filtered 
                       if device_lower in str(t.get('Devices', '')).lower()]
        
        if search:
            search_lower = search.lower().strip()
            filtered = [t for t in filtered 
                       if search_lower in str(t.get('Name', '')).lower()]
        
        return filtered

    @staticmethod
    def calculate_deviations(tasks: List[Dict]) -> List[Dict]:
        """
        Calculate deviation percentages and status for each task.
        
        Dev% BRD = (Average - Perf_BRD) / Perf_BRD
        Dev% Prev = (Average - Previous Value) / Previous Value
        
        Status thresholds (based on absolute deviation):
        - GREEN: < 0.005 (0.5%)
        - YELLOW: 0 to 0.1 (0% to 10%)
        - RED: >= 0.1 (10%+)
        
        PASS = GREEN or YELLOW (< 10%)
        FAIL = RED (>= 10%)
        """
        for task in tasks:
            average_str = task.get('Average', '')
            perf_brd_str = task.get('Perf_BRD', '')
            prev_value_str = task.get('Previous Value', '')
            
            # Parse numeric values
            average = CsvImporter._parse_number(average_str)
            perf_brd = CsvImporter._parse_number(perf_brd_str)
            prev_value = CsvImporter._parse_number(prev_value_str)
            
            # Calculate Dev% BRD
            if average is not None and perf_brd is not None and perf_brd != 0:
                dev_brd = (average - perf_brd) / perf_brd
                task['Deviation_BRD'] = f"{dev_brd * 100:.2f}%"
                task['_dev_brd_value'] = dev_brd
                task['BRD Status'] = CsvImporter._get_status(dev_brd)
                task['_brd_color'] = CsvImporter._get_color(dev_brd)
            else:
                task['Deviation_BRD'] = task.get('Deviation_BRD', '')
                task['_dev_brd_value'] = None
                task['_brd_color'] = ''
                if not task.get('BRD Status'):
                    task['BRD Status'] = ''
            
            # Calculate Dev% Prev
            if average is not None and prev_value is not None and prev_value != 0:
                dev_prev = (average - prev_value) / prev_value
                task['Deviation_Prev'] = f"{dev_prev * 100:.2f}%"
                task['_dev_prev_value'] = dev_prev
                task['Previous Status'] = CsvImporter._get_status(dev_prev)
                task['_prev_color'] = CsvImporter._get_color(dev_prev)
            else:
                task['Deviation_Prev'] = task.get('Deviation_Prev', '')
                task['_dev_prev_value'] = None
                task['_prev_color'] = ''
                if not task.get('Previous Status'):
                    task['Previous Status'] = ''
        
        return tasks

    @staticmethod
    def _parse_number(val_str: str) -> Optional[float]:
        """Parse a string to float, returning None if not numeric."""
        if not val_str or val_str in ['', '-', '0', 'NA', 'N/A', 'nan', 'None', 'Blocked']:
            return None
        try:
            return float(val_str.replace(',', ''))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_color(deviation: float) -> str:
        """
        Get color based on deviation value.
        Negative deviation = current is BETTER (faster) than baseline = always GREEN
        Positive deviation = current is WORSE (slower) than baseline = check thresholds
        """
        if deviation <= 0:
            # Negative or zero = better or same as baseline = GREEN
            return 'green'
        elif deviation < 0.005:
            # Very small positive deviation (< 0.5%) = GREEN
            return 'green'
        elif deviation < 0.1:
            # Small positive deviation (0.5% to 10%) = YELLOW
            return 'yellow'
        else:
            # Large positive deviation (>= 10%) = RED
            return 'red'

    @staticmethod
    def _get_status(deviation: float) -> str:
        """
        Get PASS/FAIL status based on deviation.
        Negative = PASS (better than baseline)
        Positive < 10% = PASS (acceptable)
        Positive >= 10% = FAIL (regression)
        """
        if deviation <= 0:
            return 'PASS'
        elif deviation < 0.1:
            return 'PASS'
        else:
            return 'FAIL'

    @staticmethod
    def enrich_subtasks_with_parent_info(tasks: List[Dict]) -> List[Dict]:
        """
        Enrich subtasks with their parent task's section and project info.
        In Asana CSV, subtasks don't have Section/Column set — their parent does.
        
        This method propagates parent task's Section/Column and Projects to subtasks.
        """
        # Build parent task lookup
        parent_info = {}
        for task in tasks:
            if task.get('is_parent', False):
                parent_info[task['Name']] = {
                    'section': task.get('Section/Column', ''),
                    'project': task.get('Projects', ''),
                }
        
        # Enrich subtasks
        for task in tasks:
            if task.get('is_subtask', False):
                parent_name = task.get('Parent task', '')
                if parent_name in parent_info:
                    task['_parent_section'] = parent_info[parent_name].get('section', '')
                    task['_parent_project'] = parent_info[parent_name].get('project', '')
                else:
                    task['_parent_section'] = ''
                    task['_parent_project'] = ''
        
        return tasks