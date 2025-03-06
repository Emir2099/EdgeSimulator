import os
import json
import hashlib
from datetime import datetime
import pandas as pd

class VersionControlEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

class DataVersionControl:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.version_dir = os.path.join(base_dir, '.versions')
        self.version_db = os.path.join(self.version_dir, 'version_db.json')
        self.versions = {}
        self._initialize()
    
    def _initialize(self):
        """Initialize version control system"""
        os.makedirs(self.version_dir, exist_ok=True)
        if os.path.exists(self.version_db):
            with open(self.version_db, 'r') as f:
                self.versions = json.load(f)
    
    def _calculate_checksum(self, data):
        """Calculate SHA-256 checksum of data"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True, cls=VersionControlEncoder).encode()
        return hashlib.sha256(data).hexdigest()
    
    def save_version(self, file_path, data, metadata=None):
        """Save a new version of the data"""
        relative_path = os.path.relpath(file_path, self.base_dir)
        checksum = self._calculate_checksum(data)
        
        version = {
            'timestamp': datetime.now().isoformat(),
            'checksum': checksum,
            'metadata': metadata or {},
            'file_path': relative_path
        }
        
        if relative_path not in self.versions:
            self.versions[relative_path] = []
        
        self.versions[relative_path].append(version)
        
        # Save version information
        version_path = os.path.join(self.version_dir, f"{checksum}.json")
        with open(version_path, 'w') as f:
            json.dump({'data': data, 'version': version}, f, cls=VersionControlEncoder)
        
        # Update version database
        with open(self.version_db, 'w') as f:
            json.dump(self.versions, f, cls=VersionControlEncoder)
        
        return version
    
    def get_version(self, file_path, version_index=-1):
        """Retrieve a specific version of the data"""
        relative_path = os.path.relpath(file_path, self.base_dir)
        if relative_path not in self.versions:
            return None
        
        try:
            version = self.versions[relative_path][version_index]
            version_path = os.path.join(self.version_dir, f"{version['checksum']}.json")
            with open(version_path, 'r') as f:
                return json.load(f)['data']
        except (IndexError, FileNotFoundError):
            return None
    
    def get_version_history(self, file_path):
        """Get version history for a file"""
        relative_path = os.path.relpath(file_path, self.base_dir)
        return self.versions.get(relative_path, [])
    
    def rollback(self, file_path, version_index=-1):
        """Rollback to a specific version"""
        data = self.get_version(file_path, version_index)
        if data:
            with open(file_path, 'w') as f:
                json.dump(data, f)
            return True
        return False