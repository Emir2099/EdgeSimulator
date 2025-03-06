from cryptography.fernet import Fernet
import os

class EncryptionManager:
    def __init__(self):
        self.key_file = "encryption.key"
        self.key = self._load_or_generate_key()
        self.cipher_suite = Fernet(self.key)
        self.stats = {
            'total_encrypted': 0,
            'total_decrypted': 0,
            'encryption_failures': 0
        }

    def _load_or_generate_key(self):
        """Load existing key or generate new one"""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(key)
            return key

    def encrypt(self, data):
        """Encrypt data"""
        try:
            if isinstance(data, str):
                data = data.encode()
            encrypted_data = self.cipher_suite.encrypt(data)
            self.stats['total_encrypted'] += len(encrypted_data)
            return encrypted_data
        except Exception as e:
            self.stats['encryption_failures'] += 1
            print(f"Encryption error: {str(e)}")
            return None

    def decrypt(self, encrypted_data):
        """Decrypt data"""
        try:
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            self.stats['total_decrypted'] += len(decrypted_data)
            return decrypted_data
        except Exception as e:
            self.stats['encryption_failures'] += 1
            print(f"Decryption error: {str(e)}")
            return None