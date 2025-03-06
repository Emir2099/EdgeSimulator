# Edge Computing Simulator

A multi-region edge computing simulator that demonstrates efficient data aggregation and replication strategies for cloud environments.

## 🚀 Features

- Multi-region edge device simulation
- Real-time sensor data generation
- Smart data aggregation at the edge
- Inter-region data replication
- Circular replication topology
- Local storage optimization

## 📁 Project Structure

```
EdgeSimulator/
├── multiregion/
│   ├── edge.py              # Main simulation logic
│   ├── region_1_cloud_storage/      # Cloud storage for region 1
│   ├── region_2_cloud_storage/      # Cloud storage for region 2
│   ├── region_3_cloud_storage/      # Cloud storage for region 3
│   ├── region_1_replicated_storage/ # Replicated storage for region 1
│   ├── region_2_replicated_storage/ # Replicated storage for region 2
│   └── region_3_replicated_storage/ # Replicated storage for region 3
```

## 🔧 Requirements

- Python 3.7+
- pandas
- threading (built-in)
- json (built-in)
- random (built-in)

## 📦 Installation

```bash
pip install pandas
```

## 🚦 Running the Simulator

```bash
python multiregion/edge.py
```

## 💡 How It Works

1. **Edge Device Simulation**
   - Generates synthetic sensor data (temperature, humidity)
   - Aggregates data every 5 seconds
   - Stores aggregated data in regional cloud storage

2. **Data Replication**
   - Implements circular replication between regions
   - Automatic synchronization every 5 seconds
   - Maintains data consistency across regions

3. **Storage Management**
   - Separate cloud and replicated storage for each region
   - JSON-based data storage
   - Efficient data organization

## 🔑 Key Benefits

- Reduced cloud egress costs
- Optimized bandwidth usage
- Multi-region resilience
- Customizable replication strategies


