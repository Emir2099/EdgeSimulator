import zlib
import lzma
import bz2
import time
from enum import Enum


class CompressionType(Enum):
    ZLIB = 'zlib'
    LZMA = 'lzma'
    BZ2  = 'bz2'


class CompressionManager:
    """
    Smart Data Optimization Engine implementing Algorithm 1 of the S-Edge paper.

    The adaptive compression logic (ZLIB -> BZ2 fallback, LZMA for anomalies)
    is encapsulated here rather than in the caller, ensuring the intelligence
    is part of the compression module itself.

    Compression efficiency threshold tau:
        If eta = (S_raw - S_comp) / S_raw < tau, ZLIB is deemed inefficient
        and BZ2 is applied to the ORIGINAL data block (not the ZLIB output),
        avoiding any double-compression penalty.

    Algorithm 1 implementation:
        Line 1-3:  if priority == HIGH -> LZMA
        Line 5-12: else -> try ZLIB; if eta < tau -> BZ2 on original D
        Line 15:   AES encrypt (handled by EncryptionManager)
    """

    def __init__(self, default_type=CompressionType.ZLIB, tau=0.5):
        """
        Parameters
        ----------
        default_type : CompressionType
            Default algorithm for normal-priority traffic (ZLIB).
        tau : float
            Compression efficiency threshold (Section 3.3, Algorithm 1 line 10).
            If ZLIB compression ratio eta < tau, fall back to BZ2.
            Default tau=0.5: ZLIB must reduce size by at least 50%.
        """
        self.compression_type = default_type
        self.tau = tau                  # efficiency threshold tau (Eq. 4)
        self.compression_stats = {
            'total_original': 0,
            'total_compressed': 0,
            'compression_ratios': [],
            'algorithm_usage': {
                'ZLIB': 0, 'BZ2': 0, 'LZMA': 0
            },
            'fallback_count': 0,        # times BZ2 fallback was triggered
            'latencies_us': []          # per-operation latency in microseconds
        }

    # ------------------------------------------------------------------
    # Core compression primitives
    # ------------------------------------------------------------------

    def _compress_zlib(self, data):
        return zlib.compress(data, level=9)

    def _compress_lzma(self, data):
        return lzma.compress(data)

    def _compress_bz2(self, data):
        return bz2.compress(data)

    def compress(self, data):
        """
        Compress using the currently selected algorithm.
        Records per-operation latency for profiling studies.
        """
        t_start = time.perf_counter()
        if self.compression_type == CompressionType.ZLIB:
            result = self._compress_zlib(data)
        elif self.compression_type == CompressionType.LZMA:
            result = self._compress_lzma(data)
        elif self.compression_type == CompressionType.BZ2:
            result = self._compress_bz2(data)
        else:
            result = self._compress_zlib(data)
        t_end = time.perf_counter()
        latency_us = (t_end - t_start) * 1_000_000
        self.compression_stats['latencies_us'].append(latency_us)
        return result

    def adaptive_compress(self, data, priority='normal'):
        """
        Full Algorithm 1 implementation.

        Parameters
        ----------
        data : bytes
            Raw data block D to compress.
        priority : str
            'high' for anomalous packets (triggers LZMA regardless of eta).
            'normal' for standard traffic (ZLIB with BZ2 fallback).

        Returns
        -------
        compressed : bytes
            Compressed output.
        algorithm_used : CompressionType
            Which algorithm was selected.
        eta : float
            Final compression ratio achieved.
        """
        s_raw = len(data)

        # Algorithm 1 Line 1-3: High priority -> LZMA (Eq. override)
        if priority == 'high':
            t0 = time.perf_counter()
            compressed = self._compress_lzma(data)
            latency_us = (time.perf_counter() - t0) * 1_000_000
            self.compression_stats['latencies_us'].append(latency_us)
            self.compression_stats['algorithm_usage']['LZMA'] += 1
            eta = (s_raw - len(compressed)) / s_raw if s_raw > 0 else 0
            self.update_stats(s_raw, len(compressed))
            return compressed, CompressionType.LZMA, eta

        # Algorithm 1 Line 5-6: Default -> ZLIB
        t0 = time.perf_counter()
        zlib_compressed = self._compress_zlib(data)
        zlib_latency_us = (time.perf_counter() - t0) * 1_000_000

        s_comp_zlib = len(zlib_compressed)
        eta = (s_raw - s_comp_zlib) / s_raw if s_raw > 0 else 0

        # Algorithm 1 Line 10-12: If eta < tau -> fallback to BZ2 on D
        if eta < self.tau:
            self.compression_stats['fallback_count'] += 1
            # BZ2 is applied to ORIGINAL data D (not ZLIB output)
            # This avoids double-compression penalty
            t0 = time.perf_counter()
            compressed = self._compress_bz2(data)
            bz2_latency_us = (time.perf_counter() - t0) * 1_000_000
            # Record both latencies: wasted ZLIB pass + BZ2 pass
            self.compression_stats['latencies_us'].append(
                zlib_latency_us + bz2_latency_us
            )
            self.compression_stats['algorithm_usage']['BZ2'] += 1
            eta = (s_raw - len(compressed)) / s_raw if s_raw > 0 else 0
            self.update_stats(s_raw, len(compressed))
            return compressed, CompressionType.BZ2, eta

        # ZLIB was sufficient
        self.compression_stats['latencies_us'].append(zlib_latency_us)
        self.compression_stats['algorithm_usage']['ZLIB'] += 1
        self.update_stats(s_raw, s_comp_zlib)
        return zlib_compressed, CompressionType.ZLIB, eta

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
        ratio = ((original_size - compressed_size) / original_size) * 100 \
                if original_size > 0 else 0
        self.compression_stats['compression_ratios'].append(ratio)
        return ratio

    def get_average_ratio(self):
        ratios = self.compression_stats['compression_ratios']
        return sum(ratios) / len(ratios) if ratios else 0

    def get_average_latency_us(self):
        """Return mean per-operation compression latency in microseconds."""
        lats = self.compression_stats['latencies_us']
        return sum(lats) / len(lats) if lats else 0
