import sys, os
os.chdir(r'c:\Users\sakthimx\Desktop\ASANA_Dashboard')
sys.path.insert(0, 'asana_generator_app')
import logging
logging.basicConfig(level=logging.INFO, handlers=[logging.NullHandler()])

from core.data_loader import DataLoader
from core.brd_matcher import BrdMatcher

out = []
loader = DataLoader()

# Try both files
for fname in ['Juno_Mainline_Performance_Results_Mar_J19.3 (6).xlsx']:
    if not os.path.exists(fname):
        continue
    brd_sheets = loader.load_all_sheets_as_raw(fname)
    brd_data = brd_sheets.get('GPC New Feature', [])
    
    matcher = BrdMatcher()
    feat_col = matcher.find_new_feature_column(brd_data)
    header_row = matcher._find_header_row(brd_data, ['scenario', 'new feature', 's.no'])
    filled = matcher.fill_down_column(brd_data, feat_col, start_row=header_row+1)
    
    out.append(f"=== ALL rows in GPC New Feature ({len(brd_data)} total) ===")
    out.append(f"Header row: {header_row}, Feature col: {feat_col}")
    out.append("")
    
    # Show ALL unique features and their scenarios
    features = {}
    for r in range(header_row+1, len(brd_data)):
        row = brd_data[r]
        feature = filled.get(r, '')
        scenario = row[4] if len(row) > 4 else ''
        scenario_str = str(scenario or '')
        if feature not in features:
            features[feature] = []
        features[feature].append((r, scenario_str[:80]))
    
    for feat_name, scenarios in features.items():
        out.append(f"\n--- Feature: '{feat_name}' ({len(scenarios)} rows) ---")
        for r_idx, sc in scenarios:
            out.append(f"  Row {r_idx}: '{sc}'")
    
    # Now show what's in the Template Color_stroke sheet
    out.append(f"\n\n=== Template Color_stroke scenarios ===")
    template_sheets = loader.load_all_template_sheets(
        os.path.join('asana_generator_app', 'resources', 'Template.xlsx'))
    
    for sheet_name, df in template_sheets.items():
        if 'color' in sheet_name.lower() or 'hwr' in sheet_name.lower() or 'keyboard' in sheet_name.lower() or 'q_a' in sheet_name.lower() or 'qa' in sheet_name.lower():
            out.append(f"\n--- Template sheet: '{sheet_name}' ({len(df)} rows) ---")
            out.append(f"  Columns: {list(df.columns)}")
            for _, row in df.iterrows():
                scenario = ''
                for col in ['Performance Scenario', 'Scenario Name', 'Name']:
                    if col in row.index:
                        val = row.get(col)
                        if val and str(val).lower() not in ['nan', 'none', '']:
                            scenario = str(val).strip()
                            break
                priority = row.get('Priority', '')
                out.append(f"  scenario='{scenario[:70]}' priority='{priority}'")

with open('debug_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print("Done")
