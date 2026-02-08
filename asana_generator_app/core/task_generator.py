import pandas as pd
from typing import List, Dict, Any
from .brd_matcher import BrdMatcher

class TaskGenerator:
    """
    Generates the final list of tasks by combining Template data with BRD data.
    """
    
    def __init__(self):
        self.matcher = BrdMatcher()

    def generate_tasks(self, 
                       template_df: pd.DataFrame, 
                       brd_df: pd.DataFrame, 
                       config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generates tasks for a specific configuration (Device, Sheet, etc.)
        config = {
            'device': 'Malbec',
            'parent_task': 'P1 (8)',
            'project_name': 'Proj X',
            'section_name': 'Section Y',
            'perf_col': 'Malbec BRD',
            'prev_col': 'Previous Value'
        }
        """
        tasks = []
        
        # Identify Scenario Column in Template
        # Usually "Scenario Name"
        scenario_col = None
        for col in template_df.columns:
            if 'scenario name' in str(col).lower() or 'performance scenario' in str(col).lower():
                scenario_col = col
                break
        
        if not scenario_col:
            raise ValueError("Could not find 'Scenario Name' column in Template.")

        # Identify Time/Est Column
        time_col = None
        for col in template_df.columns:
            if 'estimated time' in str(col).lower() or 'est. time' in str(col).lower() or 'time' in str(col).lower():
                time_col = col
                break

        # Iterate through Template Rows
        for idx, row in template_df.iterrows():
            scenario_name = str(row[scenario_col])
            if pd.isna(scenario_name) or scenario_name.strip() == '':
                continue
                
            # Find Match in BRD
            match_result = self.matcher.find_match(
                scenario_name, 
                config['device'], 
                brd_df, 
                config.get('perf_col', ''), 
                config.get('prev_col', '')
            )
            
            # Filter non-applicable
            if not match_result['applicable']:
                continue
                
            # Create Task Object
            task = {
                '#': len(tasks) + 1,
                'Parent Task': config['parent_task'],
                'Task Name': scenario_name,
                'Device': config['device'],
                'Est. Time': str(row[time_col]) if time_col and not pd.isna(row[time_col]) else '-',
                'Perf_BRD': match_result['perf_value'],
                'Previous Value': match_result['prev_value'],
                'Match Score': match_result['match_source']
            }
            tasks.append(task)
            
        return tasks
