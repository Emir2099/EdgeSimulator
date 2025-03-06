# Edge Simulator

A multi-region edge computing simulator that demonstrates efficient data aggregation and replication strategies for cloud environments

## Features and Components

### 1. Data Management
- **Sensor Data Generation**: Simulates IoT sensor data generation
- **Edge Pre-Processing**: Aggregates data at edge devices
- **Cloud Storage**: Simulates cloud storage with local directories
- **Replication**: Ensures data redundancy across regions
- **Error Handling**: Handles corrupted files and system failures

### 2. Advanced Features

#### Health Monitoring System
```python
class HealthMonitor:
    """Monitors system health metrics including CPU, memory, disk usage"""
```
- Real-time system metrics tracking
- Configurable thresholds
- Alert generation for threshold violations

#### Smart Caching
```python
class SmartCache:
    """Implements LRU caching with TTL for frequent data access"""
```
- Optimizes data access
- Time-based cache invalidation
- Memory-efficient storage

#### Version Control
```python
class DataVersionControl:
    """Manages data versions and maintains checksums"""
```
- File versioning
- Checksum verification
- Metadata tracking

#### Load Balancing
```python
class LoadBalancer:
    """Distributes load across regions dynamically"""
```
- Dynamic load distribution
- Region health monitoring
- Automatic failover

#### Compression Management
```python
class CompressionManager:
    """Handles data compression with multiple algorithms"""
```
- Multiple compression algorithms
- Adaptive compression based on priority
- Compression statistics tracking

#### Encryption
```python
class EncryptionManager:
    """Manages data encryption and key handling"""
```
- Secure data encryption
- Key management
- Protected data transfer

#### Anomaly Detection
```python
class AnomalyDetector:
    """Detects anomalies in sensor data"""
```
- Real-time anomaly detection
- Self-learning capabilities
- Priority-based handling

#### Monitoring Dashboard
```python
class MonitoringDashboard:
    """Real-time system monitoring interface"""
```
- System metrics visualization
- Alert monitoring
- Resource usage tracking
- Compression statistics
- Region load visualization

### 3. Efficiency Features

#### Priority-Based Processing
```python
def determine_priority(summary, anomaly_prediction):
    """Determines data priority based on content and anomalies"""
```
- Adaptive processing based on data importance
- Resource allocation optimization
- Critical data prioritization

#### Smart Data Replication
```python
def replicate_data(source_region, target_region):
    """Handles intelligent cross-region data replication"""
```
- Selective replication
- Bandwidth optimization
- Cost-effective data transfer

### 4. Impact

- Reduced egress costs through edge aggregation
- Optimized bandwidth usage
- Enhanced fault tolerance
- Customizable replication strategies
- Improved data security and integrity
- Real-time monitoring and alerts

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
cd multiregion
python edge.py
```


