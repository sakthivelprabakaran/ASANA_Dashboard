"""
Config Manager - Centralized configuration management for the application.
Supports Team Profiles: each team can have its own configuration (fields, devices,
thresholds, assignees) loaded from a named profile JSON file.
"""

import os
import json
import copy
import shutil
import logging
import csv as csv_module
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger('AsanaGenerator.ConfigManager')

# Asana core fields that are always present in any CSV
ASANA_CORE_FIELDS = [
    "Task ID", "Created At", "Completed At", "Last Modified", "Name",
    "Section/Column", "Assignee", "Assignee Email", "Start Date", "Due Date",
    "Tags", "Notes", "Projects", "Parent task", "Blocked By (Dependencies)",
    "Blocking (Dependencies)"
]


class ConfigManager:
    """
    Singleton configuration manager with Team Profile support.
    Profiles are stored in resources/profiles/ as individual JSON files.
    A master config.json tracks the active profile name.
    """

    _instance = None
    _config: Dict[str, Any] = {}
    _config_path: str = ""       # Master config.json path
    _resources_dir: str = ""
    _profiles_dir: str = ""
    _active_profile: str = ""    # Name of active profile

    # Minimal defaults for a new profile
    DEFAULTS = {
        "devices": [],
        "csv_fields": {
            "core_fields": ["Name", "Section/Column", "Parent task", "Projects", "Devices"],
            "performance_fields": [],
            "status_fields": ["Priority"],
            "deviation_fields": [],
            "iteration_fields": [],
            "meta_fields": ["Assignee", "Estimated time"]
        },
        "display_columns": [
            {"key": "Parent task", "label": "Parent Task", "visible": True},
            {"key": "Name", "label": "Scenario", "visible": True},
        ],
        "export_headers": [],
        "thresholds": {
            "green_max_deviation": 0.005,
            "yellow_max_deviation": 0.10
        },
        "default_export_values": {},
        "assignees": []
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._resolve_paths()
        self._ensure_profiles_dir()
        self._migrate_legacy_config()
        self._load_master_config()
        self._load_active_profile()

    # ====================
    # INITIALIZATION & PROFILES
    # ====================

    def _resolve_paths(self):
        """Resolve resource and profile directory paths."""
        candidates = [
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'),
            'asana_generator_app',
        ]
        for base in candidates:
            res_dir = os.path.normpath(os.path.join(base, 'resources'))
            if os.path.isdir(res_dir):
                self._resources_dir = res_dir
                self._config_path = os.path.join(res_dir, 'config.json')
                self._profiles_dir = os.path.join(res_dir, 'profiles')
                logger.info(f"Resources dir: {res_dir}")
                return
        # Fallback
        self._resources_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources'))
        self._config_path = os.path.join(self._resources_dir, 'config.json')
        self._profiles_dir = os.path.join(self._resources_dir, 'profiles')

    def _ensure_profiles_dir(self):
        """Create profiles directory if it doesn't exist."""
        os.makedirs(self._profiles_dir, exist_ok=True)

    def _migrate_legacy_config(self):
        """
        One-time migration: if config.json has profile data (devices, csv_fields, etc.)
        but no profiles/ directory with files, migrate it to 'Performance Testing' profile.
        """
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    master = json.load(f)
            except (json.JSONDecodeError, IOError):
                return

            # If master already has active_profile key, it's already migrated
            if 'active_profile' in master:
                return

            # Legacy config has profile data directly — migrate it
            profile_name = "Performance Testing"
            profile_path = os.path.join(self._profiles_dir, f"{profile_name}.json")

            if not os.path.exists(profile_path):
                # Copy all profile-level keys to the profile file
                profile_data = {k: v for k, v in master.items()
                                if k not in ('active_profile',)}
                profile_data['profile_name'] = profile_name
                profile_data['created_at'] = datetime.now().strftime('%Y-%m-%d')

                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(profile_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Migrated legacy config to profile: '{profile_name}'")

            # Rewrite master config to just track the active profile
            new_master = {"active_profile": profile_name}
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(new_master, f, indent=2, ensure_ascii=False)
            logger.info("Master config.json updated to profile-based format")

    def _load_master_config(self):
        """Load master config.json which tracks active profile name."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    master = json.load(f)
                self._active_profile = master.get('active_profile', '')
            except (json.JSONDecodeError, IOError):
                self._active_profile = ''
        
        # If no active profile, pick the first available or create default
        if not self._active_profile:
            profiles = self.list_profiles()
            if profiles:
                self._active_profile = profiles[0]
            else:
                self._active_profile = "Default"
                self._create_default_profile()
            self._save_master_config()

    def _save_master_config(self):
        """Save master config.json with active profile name."""
        master = {"active_profile": self._active_profile}
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(master, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.error(f"Failed to save master config: {e}")

    def _create_default_profile(self):
        """Create a minimal default profile."""
        profile_data = copy.deepcopy(self.DEFAULTS)
        profile_data['profile_name'] = "Default"
        profile_data['created_at'] = datetime.now().strftime('%Y-%m-%d')
        path = os.path.join(self._profiles_dir, "Default.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)

    def _load_active_profile(self):
        """Load the active profile's config data."""
        profile_path = self._get_profile_path(self._active_profile)
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"Profile loaded: '{self._active_profile}' ({len(self._config)} keys)")
                self._validate_and_fill_defaults()
                return
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load profile '{self._active_profile}': {e}")

        self._config = copy.deepcopy(self.DEFAULTS)
        logger.warning(f"Using defaults for profile '{self._active_profile}'")

    def _validate_and_fill_defaults(self):
        """Ensure all required keys exist, filling from DEFAULTS if missing."""
        for key, default_value in self.DEFAULTS.items():
            if key not in self._config:
                self._config[key] = copy.deepcopy(default_value)
                logger.info(f"Config: filled missing key '{key}' with default")
            elif isinstance(default_value, dict):
                # Fill missing sub-keys
                for sub_key, sub_default in default_value.items():
                    if sub_key not in self._config[key]:
                        self._config[key][sub_key] = copy.deepcopy(sub_default)

    def _get_profile_path(self, profile_name: str) -> str:
        """Get the file path for a profile by name."""
        return os.path.join(self._profiles_dir, f"{profile_name}.json")

    def save(self):
        """Save current profile config to its profile JSON file."""
        profile_path = self._get_profile_path(self._active_profile)
        try:
            os.makedirs(self._profiles_dir, exist_ok=True)
            self._config['profile_name'] = self._active_profile
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Profile saved: '{self._active_profile}' -> {profile_path}")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save profile: {e}")
            return False

    def reload(self):
        """Reload the active profile from disk."""
        self._load_active_profile()

    # ====================
    # PROFILE MANAGEMENT
    # ====================

    def get_active_profile(self) -> str:
        """Get the name of the active profile."""
        return self._active_profile

    def list_profiles(self) -> List[str]:
        """List all available profile names (from profiles/ directory)."""
        if not os.path.isdir(self._profiles_dir):
            return []
        profiles = []
        for f in sorted(os.listdir(self._profiles_dir)):
            if f.endswith('.json'):
                profiles.append(f[:-5])  # Remove .json extension
        return profiles

    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a different profile. Returns True if successful."""
        profile_path = self._get_profile_path(profile_name)
        if not os.path.exists(profile_path):
            logger.error(f"Profile not found: '{profile_name}'")
            return False
        
        self._active_profile = profile_name
        self._save_master_config()
        self._load_active_profile()
        logger.info(f"Switched to profile: '{profile_name}'")
        return True

    def create_profile_from_csv(self, csv_path: str, profile_name: str) -> bool:
        """
        Create a new profile by reading column headers from an Asana CSV file.
        Auto-populates export_headers, csv_fields, and display_columns.
        """
        try:
            # Read CSV headers
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv_module.reader(f)
                headers = next(reader)
            
            headers = [h.strip() for h in headers if h.strip()]
            if not headers:
                logger.error("CSV has no headers")
                return False
            
            # Build profile from headers
            profile = copy.deepcopy(self.DEFAULTS)
            profile['profile_name'] = profile_name
            profile['created_at'] = datetime.now().strftime('%Y-%m-%d')
            profile['created_from'] = os.path.basename(csv_path)
            profile['export_headers'] = headers
            
            # Auto-categorize fields
            core = []
            custom = []
            for h in headers:
                if h in ASANA_CORE_FIELDS:
                    core.append(h)
                else:
                    custom.append(h)
            
            profile['csv_fields'] = {
                "core_fields": core if core else ["Name", "Section/Column", "Parent task", "Projects"],
                "performance_fields": [],
                "status_fields": [],
                "deviation_fields": [],
                "iteration_fields": [],
                "meta_fields": custom
            }
            
            # Auto-create display columns from all custom fields
            display_cols = [
                {"key": "Parent task", "label": "Parent Task", "visible": True},
                {"key": "Name", "label": "Scenario", "visible": True},
            ]
            for field in custom[:20]:  # Limit to first 20 custom fields
                display_cols.append({
                    "key": field, "label": field, "visible": True
                })
            profile['display_columns'] = display_cols
            
            # Save profile
            profile_path = self._get_profile_path(profile_name)
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Profile created from CSV: '{profile_name}' ({len(headers)} headers, {len(custom)} custom fields)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create profile from CSV: {e}")
            return False

    def create_empty_profile(self, profile_name: str) -> bool:
        """Create a new empty profile with defaults."""
        profile_path = self._get_profile_path(profile_name)
        if os.path.exists(profile_path):
            return False
        
        profile = copy.deepcopy(self.DEFAULTS)
        profile['profile_name'] = profile_name
        profile['created_at'] = datetime.now().strftime('%Y-%m-%d')
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Empty profile created: '{profile_name}'")
        return True

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile. Cannot delete the active profile."""
        if profile_name == self._active_profile:
            logger.warning("Cannot delete the active profile")
            return False
        
        profile_path = self._get_profile_path(profile_name)
        if os.path.exists(profile_path):
            os.remove(profile_path)
            logger.info(f"Profile deleted: '{profile_name}'")
            return True
        return False

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Rename a profile."""
        old_path = self._get_profile_path(old_name)
        new_path = self._get_profile_path(new_name)
        
        if not os.path.exists(old_path) or os.path.exists(new_path):
            return False
        
        # Update profile_name inside the file
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['profile_name'] = new_name
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.remove(old_path)
            
            # Update active profile reference if needed
            if self._active_profile == old_name:
                self._active_profile = new_name
                self._save_master_config()
            
            logger.info(f"Profile renamed: '{old_name}' -> '{new_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to rename profile: {e}")
            return False

    def export_profile(self, profile_name: str, export_path: str) -> bool:
        """Export a profile to a JSON file (for sharing)."""
        src = self._get_profile_path(profile_name)
        if not os.path.exists(src):
            return False
        try:
            shutil.copy2(src, export_path)
            logger.info(f"Profile exported: '{profile_name}' -> {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export profile: {e}")
            return False

    def import_profile(self, import_path: str) -> Optional[str]:
        """
        Import a profile from a JSON file. Returns the profile name, or None on failure.
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            profile_name = data.get('profile_name', os.path.splitext(os.path.basename(import_path))[0])
            
            # Avoid overwriting existing profile
            dest_path = self._get_profile_path(profile_name)
            if os.path.exists(dest_path):
                # Append suffix
                profile_name = f"{profile_name} (imported)"
                dest_path = self._get_profile_path(profile_name)
            
            data['profile_name'] = profile_name
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Profile imported: '{profile_name}' from {import_path}")
            return profile_name
        except Exception as e:
            logger.error(f"Failed to import profile: {e}")
            return None

    @property
    def profiles_dir(self) -> str:
        """Get the profiles directory path."""
        return self._profiles_dir

    # ====================
    # DEVICES
    # ====================

    def get_devices(self) -> List[str]:
        """Get the list of available devices."""
        return list(self._config.get('devices', []))

    def add_device(self, device_name: str) -> bool:
        """Add a new device. Returns True if added, False if already exists."""
        devices = self._config.setdefault('devices', [])
        if device_name.strip() and device_name.strip() not in devices:
            devices.append(device_name.strip())
            logger.info(f"Device added: '{device_name}'")
            return True
        return False

    def remove_device(self, device_name: str) -> bool:
        """Remove a device. Returns True if removed."""
        devices = self._config.get('devices', [])
        if device_name in devices:
            devices.remove(device_name)
            logger.info(f"Device removed: '{device_name}'")
            return True
        return False

    def set_devices(self, devices: List[str]):
        """Replace entire devices list."""
        self._config['devices'] = [d.strip() for d in devices if d.strip()]

    # ====================
    # CSV FIELDS
    # ====================

    def get_all_csv_fields(self) -> List[str]:
        """Get a flat list of all known CSV field names (all categories combined)."""
        csv_fields = self._config.get('csv_fields', {})
        all_fields = []
        for category in ['core_fields', 'performance_fields', 'status_fields',
                         'deviation_fields', 'iteration_fields', 'meta_fields']:
            all_fields.extend(csv_fields.get(category, []))
        return all_fields

    def get_csv_fields_by_category(self, category: str) -> List[str]:
        """Get CSV fields for a specific category."""
        return list(self._config.get('csv_fields', {}).get(category, []))

    def get_iteration_fields(self) -> List[str]:
        """Get iteration field names."""
        return self.get_csv_fields_by_category('iteration_fields')

    def get_performance_fields(self) -> List[str]:
        """Get performance field names (Average, Perf_BRD, Previous Value)."""
        return self.get_csv_fields_by_category('performance_fields')

    def add_csv_field(self, category: str, field_name: str) -> bool:
        """Add a field to a CSV field category."""
        csv_fields = self._config.setdefault('csv_fields', {})
        cat_list = csv_fields.setdefault(category, [])
        if field_name.strip() and field_name.strip() not in cat_list:
            cat_list.append(field_name.strip())
            logger.info(f"CSV field added: '{field_name}' to '{category}'")
            return True
        return False

    def remove_csv_field(self, category: str, field_name: str) -> bool:
        """Remove a field from a CSV field category."""
        cat_list = self._config.get('csv_fields', {}).get(category, [])
        if field_name in cat_list:
            cat_list.remove(field_name)
            logger.info(f"CSV field removed: '{field_name}' from '{category}'")
            return True
        return False

    # ====================
    # DISPLAY COLUMNS
    # ====================

    def get_display_columns(self, visible_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get display column definitions for the Report Generator table.
        Returns list of {"key": ..., "label": ..., "visible": ...}
        """
        columns = self._config.get('display_columns', [])
        if visible_only:
            return [c for c in columns if c.get('visible', True)]
        return list(columns)

    def get_display_column_keys(self, visible_only: bool = True) -> List[str]:
        """Get just the key names of display columns."""
        return [c['key'] for c in self.get_display_columns(visible_only)]

    def get_display_column_labels(self, visible_only: bool = True) -> Dict[str, str]:
        """Get a key→label mapping for display columns."""
        return {c['key']: c.get('label', c['key'])
                for c in self.get_display_columns(visible_only)}

    def add_display_column(self, key: str, label: str, visible: bool = True) -> bool:
        """Add a new display column."""
        columns = self._config.setdefault('display_columns', [])
        # Check for duplicates
        if any(c['key'] == key for c in columns):
            return False
        columns.append({"key": key, "label": label, "visible": visible})
        logger.info(f"Display column added: '{key}' ({label})")
        return True

    def remove_display_column(self, key: str) -> bool:
        """Remove a display column by key."""
        columns = self._config.get('display_columns', [])
        before_len = len(columns)
        self._config['display_columns'] = [c for c in columns if c['key'] != key]
        removed = len(self._config['display_columns']) < before_len
        if removed:
            logger.info(f"Display column removed: '{key}'")
        return removed

    def set_display_column_visibility(self, key: str, visible: bool):
        """Toggle visibility of a display column."""
        for col in self._config.get('display_columns', []):
            if col['key'] == key:
                col['visible'] = visible
                return True
        return False

    def set_display_columns(self, columns: List[Dict[str, Any]]):
        """Replace entire display columns list."""
        self._config['display_columns'] = columns

    # ====================
    # EXPORT HEADERS
    # ====================

    def get_export_headers(self) -> List[str]:
        """Get the list of Asana CSV export column headers."""
        return list(self._config.get('export_headers', []))

    def add_export_header(self, header: str) -> bool:
        """Add a new export header."""
        headers = self._config.setdefault('export_headers', [])
        if header.strip() and header.strip() not in headers:
            headers.append(header.strip())
            logger.info(f"Export header added: '{header}'")
            return True
        return False

    def remove_export_header(self, header: str) -> bool:
        """Remove an export header."""
        headers = self._config.get('export_headers', [])
        if header in headers:
            headers.remove(header)
            logger.info(f"Export header removed: '{header}'")
            return True
        return False

    def set_export_headers(self, headers: List[str]):
        """Replace entire export headers list."""
        self._config['export_headers'] = headers

    # ====================
    # THRESHOLDS
    # ====================

    def get_thresholds(self) -> Dict[str, float]:
        """Get deviation thresholds."""
        return dict(self._config.get('thresholds', self.DEFAULTS['thresholds']))

    def get_green_threshold(self) -> float:
        """Get green max deviation threshold."""
        return self._config.get('thresholds', {}).get('green_max_deviation', 0.005)

    def get_yellow_threshold(self) -> float:
        """Get yellow max deviation threshold."""
        return self._config.get('thresholds', {}).get('yellow_max_deviation', 0.10)

    def set_thresholds(self, green_max: float, yellow_max: float):
        """Update deviation thresholds."""
        thresholds = self._config.setdefault('thresholds', {})
        thresholds['green_max_deviation'] = green_max
        thresholds['yellow_max_deviation'] = yellow_max
        logger.info(f"Thresholds updated: green<{green_max}, yellow<{yellow_max}")

    # ====================
    # ASSIGNEES
    # ====================

    def get_assignees(self) -> List[Dict[str, str]]:
        """Get the list of assignees. Each is {"name": ..., "email": ...}."""
        return list(self._config.get('assignees', []))

    def get_assignee_names(self) -> List[str]:
        """Get just the display names of assignees."""
        return [a.get('name', '') for a in self.get_assignees()]

    def get_assignee_email(self, name: str) -> str:
        """Get the email for an assignee by display name."""
        for a in self.get_assignees():
            if a.get('name', '') == name:
                return a.get('email', '')
        return ''

    def add_assignee(self, name: str, email: str) -> bool:
        """Add a new assignee. Returns True if added."""
        assignees = self._config.setdefault('assignees', [])
        # Check for duplicate email
        if any(a.get('email', '').lower() == email.lower().strip() for a in assignees):
            return False
        assignees.append({"name": name.strip(), "email": email.strip()})
        logger.info(f"Assignee added: '{name}' ({email})")
        return True

    def remove_assignee(self, email: str) -> bool:
        """Remove an assignee by email."""
        assignees = self._config.get('assignees', [])
        before_len = len(assignees)
        self._config['assignees'] = [
            a for a in assignees if a.get('email', '').lower() != email.lower()
        ]
        removed = len(self._config['assignees']) < before_len
        if removed:
            logger.info(f"Assignee removed: {email}")
        return removed

    def set_assignees(self, assignees: List[Dict[str, str]]):
        """Replace entire assignees list."""
        self._config['assignees'] = assignees

    # ====================
    # DEFAULT EXPORT VALUES
    # ====================

    def get_default_export_values(self) -> Dict[str, str]:
        """Get default values for export (GREEN, YELLOW, RED columns)."""
        return dict(self._config.get('default_export_values',
                                     self.DEFAULTS['default_export_values']))

    # ====================
    # RAW ACCESS
    # ====================

    def get_raw_config(self) -> Dict[str, Any]:
        """Get a deep copy of the entire config dict."""
        return copy.deepcopy(self._config)

    def set_raw_config(self, config: Dict[str, Any]):
        """Replace the entire config (use with caution)."""
        self._config = config

    @property
    def config_path(self) -> str:
        """Get the path to the config file."""
        return self._config_path