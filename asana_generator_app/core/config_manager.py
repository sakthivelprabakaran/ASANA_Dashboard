"""
Config Manager - Centralized configuration management for the application.
Loads settings from config.json, provides getters, and supports runtime editing + saving.
Ensures no hardcoded devices, fields, or thresholds in application code.
"""

import os
import json
import copy
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger('AsanaGenerator.ConfigManager')


class ConfigManager:
    """
    Singleton configuration manager.
    Loads from config.json at startup, provides typed accessors,
    and saves changes back to disk.
    """

    _instance = None
    _config: Dict[str, Any] = {}
    _config_path: str = ""
    _default_config_path: str = ""

    # Minimal defaults if config.json is missing or corrupt
    DEFAULTS = {
        "devices": [],
        "csv_fields": {
            "core_fields": ["Name", "Section/Column", "Parent task", "Projects", "Devices"],
            "performance_fields": ["Average", "Perf_BRD", "Previous Value"],
            "status_fields": ["Priority", "BRD Status", "Previous Status"],
            "deviation_fields": ["Deviation % Current Vs BRD", "Deviation % Current vs Previous"],
            "iteration_fields": [],
            "meta_fields": []
        },
        "display_columns": [],
        "export_headers": [],
        "thresholds": {
            "green_max_deviation": 0.005,
            "yellow_max_deviation": 0.10
        },
        "default_export_values": {
            "GREEN": "0",
            "YELLOW": "0.1",
            "RED": "0.1"
        }
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
        self._resolve_config_path()
        self._load()

    # ====================
    # INITIALIZATION
    # ====================

    def _resolve_config_path(self):
        """Find config.json in resources/ relative to the app package."""
        # Try multiple paths to locate config.json
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'resources', 'config.json'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'resources', 'config.json'),
            os.path.join('asana_generator_app', 'resources', 'config.json'),
            os.path.join('resources', 'config.json'),
        ]

        for path in candidates:
            normalized = os.path.normpath(path)
            if os.path.exists(normalized):
                self._config_path = normalized
                self._default_config_path = normalized
                logger.info(f"Config found: {normalized}")
                return

        # Fallback: use the first candidate (will be created on save)
        self._config_path = os.path.normpath(candidates[0])
        self._default_config_path = self._config_path
        logger.warning(f"Config not found, will use default path: {self._config_path}")

    def _load(self):
        """Load config from JSON file, falling back to defaults."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"Config loaded: {len(self._config)} top-level keys")
                self._validate_and_fill_defaults()
                return
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load config: {e}. Using defaults.")

        self._config = copy.deepcopy(self.DEFAULTS)
        logger.warning("Using default configuration (no config.json found)")

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

    def save(self):
        """Save current config to disk."""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved to {self._config_path}")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def reload(self):
        """Reload config from disk."""
        self._load()

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