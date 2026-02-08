import pandas as pd
import openpyxl
from typing import Dict, List, Optional, Tuple, Any

class DataLoader:
    """
    Handles robust loading of Excel files for Templates and BRDs.
    - Template: Loaded as DataFrame with auto-detected headers
    - BRD: Loaded as raw list-of-lists using openpyxl with data_only=True to evaluate formulas
    """

    @staticmethod
    def load_template(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """
        Loads a Template Excel file and returns a DataFrame.
        Auto-detects the header row by looking for key columns.
        """
        try:
            # Read first few rows to inspect structure
            raw_df = pd.read_excel(file_path, sheet_name=sheet_name or 0, header=None, nrows=10)
            
            # Key columns to identify the header row
            identifiable_columns = [
                'Test Case ID', 'Scenario Name', 'Performance Scenario', 
                'Devices', 'Test Steps', 'Estimated Time', 'Priority', 'Applicable Devices'
            ]
            
            best_match_count = 0
            best_row_idx = 0
            
            for idx, row in raw_df.iterrows():
                row_values = [str(val).lower().strip() for val in row.values]
                match_count = sum(
                    1 for col in identifiable_columns 
                    if any(col.lower() in val for val in row_values)
                )
                
                if match_count > best_match_count:
                    best_match_count = match_count
                    best_row_idx = idx
            
            # Reload with correct header
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0, header=best_row_idx)
            
            # Clean empty rows/cols
            df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)
            
            return df
            
        except Exception as e:
            raise Exception(f"Failed to load Template file: {str(e)}")

    @staticmethod
    def load_brd_raw(file_path: str, sheet_name: Optional[str] = None) -> List[List[Any]]:
        """
        Loads a BRD Excel file as raw list-of-lists using openpyxl.
        Uses data_only=True to get calculated values from formula cells.
        Returns: List of rows, where each row is a list of cell values.
        """
        try:
            # Use openpyxl with data_only=True to evaluate formulas
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            
            if sheet_name:
                ws = wb[sheet_name]
            else:
                ws = wb.active
            
            raw_data = []
            for row in ws.iter_rows():
                row_values = []
                for cell in row:
                    val = cell.value
                    # Handle None and convert to string-safe value
                    if val is None:
                        row_values.append('')
                    else:
                        row_values.append(val)
                raw_data.append(row_values)
            
            wb.close()
            return raw_data
            
        except Exception as e:
            raise Exception(f"Failed to load BRD file: {str(e)}")

    @staticmethod
    def get_sheet_names(file_path: str) -> List[str]:
        """Returns list of sheet names in the Excel file."""
        xls = pd.ExcelFile(file_path)
        return xls.sheet_names

    @staticmethod
    def load_all_sheets_as_raw(file_path: str) -> Dict[str, List[List[Any]]]:
        """
        Loads all sheets from an Excel file as raw data using openpyxl.
        Uses data_only=True to get calculated values from formula cells.
        Returns: Dict mapping sheet name to list-of-lists data.
        """
        try:
            # Use openpyxl with data_only=True to evaluate formulas
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            sheets_data = {}
            
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                sheet_data = []
                
                for row in ws.iter_rows():
                    row_values = []
                    for cell in row:
                        val = cell.value
                        # Handle None and convert to string-safe value
                        if val is None:
                            row_values.append('')
                        else:
                            row_values.append(val)
                    sheet_data.append(row_values)
                
                sheets_data[sheet_name] = sheet_data
            
            wb.close()
            return sheets_data
            
        except Exception as e:
            raise Exception(f"Failed to load Excel file: {str(e)}")

    @staticmethod
    def load_all_template_sheets(file_path: str) -> Dict[str, pd.DataFrame]:
        """
        Loads all sheets from a Template file as DataFrames with auto-detected headers.
        Returns: Dict mapping sheet name to DataFrame.
        """
        try:
            xls = pd.ExcelFile(file_path)
            sheets_data = {}
            
            for sheet_name in xls.sheet_names:
                try:
                    df = DataLoader.load_template(file_path, sheet_name)
                    if not df.empty:
                        sheets_data[sheet_name] = df
                except:
                    continue
            
            return sheets_data
            
        except Exception as e:
            raise Exception(f"Failed to load Template file: {str(e)}")
