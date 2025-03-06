import time
import threading
import psutil
import os
from datetime import datetime
from collections import defaultdict

class HealthMonitor:
    def __init__(self, check_interval=5):
        self.check_interval = check_interval
        self.metrics = defaultdict(list)
        self.alerts = []
        self.is_monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # Get project directory
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # More lenient thresholds
        self.thresholds = {
            'cpu_percent': 80.0,      # Alert if CPU usage > 80%
            'memory_percent': 85.0,    # Alert if memory usage > 85%
            'disk_percent': 90.0,      # Alert if disk usage > 90%
            'response_time': 2.0,      # Alert if response time > 2s
            'thread_count': 100        # Alert if thread count > 100
        }
        
        # Add alert cooldown to prevent spam
        self.last_alert_time = defaultdict(float)
        self.alert_cooldown = 60  # seconds
    
    def start(self):
        """Start health monitoring"""
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """Stop health monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            self.collect_metrics()
            time.sleep(self.check_interval)
    
    def collect_metrics(self):
        """Collect system metrics"""
        timestamp = datetime.now()
        
        # Get disk usage for project directory
        try:
            disk_usage = psutil.disk_usage(self.project_dir)
            disk_percent = disk_usage.free / disk_usage.total * 100
        except Exception as e:
            print(f"Error getting disk usage: {e}")
            disk_percent = 0.0
        
        metrics = {
            'timestamp': timestamp,
            'cpu_percent': psutil.cpu_percent(interval=0.5),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': disk_percent,
            'network_connections': len(psutil.net_connections()),
            'thread_count': threading.active_count()
        }
        
        with self.lock:
            for key, value in metrics.items():
                if key != 'timestamp':
                    self.metrics[key].append(value)
                    if len(self.metrics[key]) > 720:
                        self.metrics[key].pop(0)
        
        self._check_thresholds(metrics)
    
    def _check_thresholds(self, metrics):
        """Check if any metrics exceed thresholds with cooldown"""
        current_time = time.time()
        
        for metric, value in metrics.items():
            if (metric in self.thresholds and 
                value > self.thresholds[metric] and 
                current_time - self.last_alert_time[metric] > self.alert_cooldown):
                
                alert = {
                    'timestamp': datetime.now(),
                    'metric': metric,
                    'value': value,
                    'threshold': self.thresholds[metric]
                }
                self.add_alert(alert)
                self.last_alert_time[metric] = current_time
    
    def add_alert(self, alert):
        """Add a new alert"""
        with self.lock:
            self.alerts.append(alert)
            print(f"ALERT: {alert['metric']} exceeded threshold: "
                  f"{alert['value']:.2f} > {alert['threshold']:.2f}")
    
    def get_metrics_summary(self):
        """Get summary of recent metrics"""
        with self.lock:
            summary = {}
            for metric, values in self.metrics.items():
                if values:
                    summary[metric] = {
                        'current': values[-1],
                        'avg': sum(values) / len(values),
                        'max': max(values),
                        'min': min(values)
                    }
            return summary
    
    def get_recent_alerts(self, limit=10):
        """Get most recent alerts"""
        with self.lock:
            return list(reversed(self.alerts))[:limit]
    
    def update_threshold(self, metric, value):
        """Update threshold for a specific metric"""
        with self.lock:
            if metric in self.thresholds:
                self.thresholds[metric] = value
                print(f"Updated threshold for {metric} to {value}")
                return True
            return False