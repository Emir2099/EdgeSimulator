from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import os

class EncryptionManager:
    def __init__(self):
        self.key_file = "encryption.key"
        self.key = self._load_or_generate_key()
        self.stats = {
            'total_encrypted': 0,
            'total_decrypted': 0,
            'encryption_failures': 0
        }

    def _load_or_generate_key(self):
        """Load existing 256-bit key or generate new one"""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read()
        else:
            key = get_random_bytes(32)  # 256-bit key for AES-256
            with open(self.key_file, "wb") as f:
                f.write(key)
            return key

    def encrypt(self, data):
        """Encrypt data using AES-256-GCM"""
        try:
            if isinstance(data, str):
                data = data.encode()
            cipher = AES.new(self.key, AES.MODE_GCM)
            ciphertext, tag = cipher.encrypt_and_digest(data)
            # Format: nonce (16B) + tag (16B) + ciphertext
            encrypted_data = cipher.nonce + tag + ciphertext
            self.stats['total_encrypted'] += len(encrypted_data)
            return encrypted_data
        except Exception as e:
            self.stats['encryption_failures'] += 1
            print(f"Encryption error: {str(e)}")
            return None

    def decrypt(self, encrypted_data):
        """Decrypt data using AES-256-GCM"""
        try:
            nonce      = encrypted_data[:16]
            tag        = encrypted_data[16:32]
            ciphertext = encrypted_data[32:]
            cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
            decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
            self.stats['total_decrypted'] += len(decrypted_data)
            return decrypted_data
        except Exception as e:
            self.stats['encryption_failures'] += 1
            print(f"Decryption error: {str(e)}")
            return None