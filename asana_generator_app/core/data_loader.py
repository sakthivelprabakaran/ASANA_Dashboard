import logging
import pandas as pd
import openpyxl
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger('AsanaGenerator.DataLoader')


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
            
            logger.info(f"Template '{file_path}': detected header at row {best_row_idx} "
                       f"({best_match_count} column matches)")
            
            # Reload with correct header
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0, header=best_row_idx)
            
            # Clean empty rows/cols
            df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)
            
            logger.info(f"Template loaded: {len(df)} rows, {len(df.columns)} columns")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load Template file '{file_path}': {e}")
            raise Exception(f"Failed to load Template file: {str(e)}")

    @staticmethod
    def load_brd_raw(file_path: str, sheet_name: Optional[str] = None) -> List[List[Any]]:
        """
        Loads a BRD Excel file as raw list-of-lists using openpyxl.
        Uses data_only=True to get calculated values from formula cells.
        Returns: List of rows, where each row is a list of cell values.
        """
        wb = None
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
            
            logger.info(f"BRD raw loaded: {len(raw_data)} rows from '{file_path}'")
            return raw_data
            
        except Exception as e:
            logger.error(f"Failed to load BRD file '{file_path}': {e}")
            raise Exception(f"Failed to load BRD file: {str(e)}")
        finally:
            if wb:
                wb.close()

    @staticmethod
    def get_sheet_names(file_path: str) -> List[str]:
        """Returns list of sheet names in the Excel file."""
        xls = None
        try:
            xls = pd.ExcelFile(file_path)
            return xls.sheet_names
        finally:
            if xls:
                xls.close()

    @staticmethod
    def load_all_sheets_as_raw(file_path: str) -> Dict[str, List[List[Any]]]:
        """
        Loads all sheets from an Excel file as raw data using openpyxl.
        Uses data_only=True to get calculated values from formula cells.
        Returns: Dict mapping sheet name to list-of-lists data.
        """
        wb = None
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
            
            logger.info(f"Loaded {len(sheets_data)} sheets from '{file_path}'")
            return sheets_data
            
        except Exception as e:
            logger.error(f"Failed to load Excel file '{file_path}': {e}")
            raise Exception(f"Failed to load Excel file: {str(e)}")
        finally:
            if wb:
                wb.close()

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
                except Exception as e:
                    logger.warning(f"Skipping sheet '{sheet_name}': {e}")
                    continue
            
            xls.close()
            logger.info(f"Template loaded: {len(sheets_data)} valid sheets from '{file_path}'")
            return sheets_data
            
        except Exception as e:
            logger.error(f"Failed to load Template file '{file_path}': {e}")
            raise Exception(f"Failed to load Template file: {str(e)}")
