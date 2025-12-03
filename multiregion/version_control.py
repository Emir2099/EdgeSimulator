import os
import json
import hashlib
import sqlite3
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
        self.db_path = os.path.join(self.version_dir, 'version_history.db')
        self._initialize()
    
    def _initialize(self):
        """Initialize version control system with SQLite"""
        os.makedirs(self.version_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Create a table that mimics a production-grade metadata store
        c.execute('''CREATE TABLE IF NOT EXISTS versions
                     (checksum TEXT PRIMARY KEY,
                      file_path TEXT,
                      timestamp TEXT,
                      metadata TEXT)''')
        conn.commit()
        conn.close()
    
    def _calculate_checksum(self, data):
        """Calculate SHA-256 checksum"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True, cls=VersionControlEncoder).encode()
        return hashlib.sha256(data).hexdigest()
    
    def save_version(self, file_path, data, metadata=None):
        """Save a new version using Transactional SQL"""
        relative_path = os.path.relpath(file_path, self.base_dir)
        checksum = self._calculate_checksum(data)
        timestamp = datetime.now().isoformat()
        meta_json = json.dumps(metadata or {})
        
        # 1. Save the actual data payload to disk (Blob storage pattern)
        version_path = os.path.join(self.version_dir, f"{checksum}.json")
        with open(version_path, 'w') as f:
            json.dump({'data': data}, f, cls=VersionControlEncoder)
        
        # 2. Write metadata to SQLite (Atomic Transaction)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute("INSERT OR REPLACE INTO versions VALUES (?, ?, ?, ?)",
                      (checksum, relative_path, timestamp, meta_json))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            conn.close()
        
        return {'checksum': checksum, 'timestamp': timestamp}
    
    def get_version(self, file_path, version_index=-1):
        """Retrieve version using SQL query"""
        relative_path = os.path.relpath(file_path, self.base_dir)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get all versions for this file, ordered by time
        c.execute("SELECT checksum FROM versions WHERE file_path=? ORDER BY timestamp ASC", (relative_path,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return None
            
        try:
            target_checksum = rows[version_index][0]
            version_path = os.path.join(self.version_dir, f"{target_checksum}.json")
            with open(version_path, 'r') as f:
                return json.load(f)['data']
        except (IndexError, FileNotFoundError):
            return None

    def rollback(self, file_path, version_index=-1):
        """Rollback mechanism"""
        data = self.get_version(file_path, version_index)
        if data:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        return False