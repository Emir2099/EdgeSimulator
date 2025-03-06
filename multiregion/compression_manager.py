import zlib
import lzma
import bz2
from enum import Enum

class CompressionType(Enum):
    ZLIB = 'zlib'
    LZMA = 'lzma'
    BZ2 = 'bz2'

class CompressionManager:
    def __init__(self, default_type=CompressionType.ZLIB):
        self.compression_type = default_type
        self.compression_stats = {
            'total_original': 0,
            'total_compressed': 0,
            'compression_ratios': []
        }
    
    def compress(self, data):
        if self.compression_type == CompressionType.ZLIB:
            return zlib.compress(data, level=9)  # Maximum compression
        elif self.compression_type == CompressionType.LZMA:
            return lzma.compress(data)
        elif self.compression_type == CompressionType.BZ2:
            return bz2.compress(data)
    
    def decompress(self, compressed_data):
        try:
            if self.compression_type == CompressionType.ZLIB:
                return zlib.decompress(compressed_data)
            elif self.compression_type == CompressionType.LZMA:
                return lzma.decompress(compressed_data)
            elif self.compression_type == CompressionType.BZ2:
                return bz2.decompress(compressed_data)
        except Exception as e:
            print(f"Decompression error: {str(e)}")
            return None
    
    def update_stats(self, original_size, compressed_size):
        self.compression_stats['total_original'] += original_size
        self.compression_stats['total_compressed'] += compressed_size
        ratio = ((original_size - compressed_size) / original_size) * 100
        self.compression_stats['compression_ratios'].append(ratio)
        return ratio
    
    def get_average_ratio(self):
        ratios = self.compression_stats['compression_ratios']
        return sum(ratios) / len(ratios) if ratios else 0