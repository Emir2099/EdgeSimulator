from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich import box
from datetime import datetime
import threading
import time
import subprocess
import sys
import os
import json
import pickle 
class MonitoringDashboard:
    def __init__(self, health_monitor, load_balancer, compression_manager):
        self.console = Console()
        self.health_monitor = health_monitor
        self.load_balancer = load_balancer
        self.compression_manager = compression_manager
        self.is_running = False
        self.update_interval = 1.0  # Update every second
        self.dashboard_process = None
        
    def generate_layout(self):
        """Generate the dashboard layout"""
        layout = Layout()
        
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split(
            Layout(name="system_metrics"),
            Layout(name="alerts")
        )
        
        layout["right"].split(
            Layout(name="region_stats"),
            Layout(name="compression_stats")
        )
        
        return layout
    
    def generate_system_metrics(self, metrics):
        """Generate system metrics panel"""
        table = Table(box=box.ROUNDED)
        table.add_column("Metric")
        table.add_column("Current")
        table.add_column("Average")
        table.add_column("Max")
        table.add_column("Min")
        
        for metric, values in metrics.items():
            if metric != 'timestamp':
                table.add_row(
                    metric,
                    f"{values['current']:>6.2f}",
                    f"{values['avg']:>6.2f}",
                    f"{values['max']:>6.2f}",
                    f"{values['min']:>6.2f}"
                )
        
        return Panel(table, title="System Metrics", border_style="blue")
    
    def generate_alerts_panel(self, alerts):
        """Generate alerts panel"""
        table = Table(box=box.ROUNDED)
        table.add_column("Time")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_column("Threshold")
        
        for alert in alerts[:5]:  # Show last 5 alerts
            table.add_row(
                alert['timestamp'].strftime('%H:%M:%S'),
                alert['metric'],
                f"{alert['value']:.2f}",
                f"{alert['threshold']:.2f}",
                style="red"
            )
        
        return Panel(table, title="Recent Alerts", border_style="red")
    
    def generate_region_stats(self):
        """Generate region statistics panel"""
        table = Table(box=box.ROUNDED)
        table.add_column("Region")
        table.add_column("Load")
        table.add_column("Status")
        
        for region, load in self.load_balancer.region_loads.items():
            status = "OK" if load < self.load_balancer.load_threshold else "HIGH"
            style = "green" if status == "OK" else "yellow"
            table.add_row(region, str(load), status, style=style)
        
        return Panel(table, title="Region Statistics", border_style="green")
    
    def generate_compression_stats(self):
        """Generate compression statistics panel"""
        table = Table(box=box.ROUNDED)
        table.add_column("Metric")
        table.add_column("Value")
        
        avg_ratio = self.compression_manager.get_average_ratio()
        total_original = self.compression_manager.compression_stats['total_original']
        total_compressed = self.compression_manager.compression_stats['total_compressed']
        
        table.add_row("Average Ratio", f"{avg_ratio:.2f}%")
        table.add_row("Total Original", f"{total_original/1024:.2f} KB")
        table.add_row("Total Compressed", f"{total_compressed/1024:.2f} KB")
        table.add_row("Compression Type", str(self.compression_manager.compression_type.value))
        
        return Panel(table, title="Compression Statistics", border_style="magenta")
    
    def update_dashboard(self, layout):
        """Update dashboard content"""
        metrics = self.health_monitor.get_metrics_summary()
        alerts = self.health_monitor.get_recent_alerts()
        
        # Update header
        layout["header"].update(
            Panel(f"Edge Simulator Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                  style="bold white")
        )
        
        # Update main sections
        layout["left"]["system_metrics"].update(self.generate_system_metrics(metrics))
        layout["left"]["alerts"].update(self.generate_alerts_panel(alerts))
        layout["right"]["region_stats"].update(self.generate_region_stats())
        layout["right"]["compression_stats"].update(self.generate_compression_stats())
        
        # Update footer
        layout["footer"].update(
            Panel("Press Ctrl+C to exit", style="dim")
        )
    
    def run(self):
        """Run the dashboard"""
        layout = self.generate_layout()
        self.is_running = True
        
        with Live(layout, refresh_per_second=4, screen=True):
            try:
                while self.is_running:
                    self.update_dashboard(layout)
                    time.sleep(self.update_interval)
            except KeyboardInterrupt:
                self.is_running = False

    def start(self):
        """Start dashboard in a new terminal window"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dashboard_script = os.path.join(current_dir, 'dashboard_window.py')
            
            # Start data sharing first
            shared_data_path = os.path.join(current_dir, 'shared_dashboard_data.json')
            self._start_data_sharing(shared_data_path)

            # For Windows, use a simpler command that's more reliable
            if sys.platform == 'win32':
                # Create a batch file to run the dashboard
                batch_file = os.path.join(current_dir, 'run_dashboard.bat')
                with open(batch_file, 'w') as f:
                    f.write(f'@echo off\n')
                    f.write(f'title Edge Simulator Dashboard\n')
                    f.write(f'python "{dashboard_script}"\n')
                    f.write('pause\n')

                # Run the batch file in a new window
                self.dashboard_process = subprocess.Popen(
                    ['start', 'cmd', '/c', batch_file],
                    shell=True,
                    cwd=current_dir
                )
            else:
                self.dashboard_process = subprocess.Popen(
                    ['gnome-terminal', '--', 'python', dashboard_script],
                    cwd=current_dir
                )
            
            return self.dashboard_process

        except Exception as e:
            print(f"Error launching dashboard: {str(e)}")
            return None

    def _start_data_sharing(self, shared_data_path):
        """Start thread to update shared data file"""
        def update_shared_data():
            while self.is_running:
                try:
                    # Get fresh metrics
                    metrics = self.health_monitor.get_metrics_summary()
                    alerts = self.health_monitor.get_recent_alerts()
                    
                    # Format data for sharing
                    shared_data = {
                        'metrics': metrics,
                        'alerts': [
                            {
                                'timestamp': alert['timestamp'].strftime('%H:%M:%S'),
                                'metric': alert['metric'],
                                'value': alert['value'],
                                'threshold': alert['threshold']
                            }
                            for alert in alerts
                        ],
                        'region_loads': {
                            region: load 
                            for region, load in self.load_balancer.region_loads.items()
                        },
                        'compression_stats': {
                            'avg_ratio': self.compression_manager.get_average_ratio(),
                            'total_original': self.compression_manager.compression_stats.get('total_original', 0),
                            'total_compressed': self.compression_manager.compression_stats.get('total_compressed', 0),
                            'type': str(self.compression_manager.compression_type.value)
                        }
                    }
                    
                    # Write to shared file
                    with open(shared_data_path, 'w', encoding='utf-8') as f:
                        json.dump(shared_data, f, indent=2, ensure_ascii=False)
                    
                    time.sleep(0.25)
                    
                except Exception as e:
                    print(f"Error updating shared data: {str(e)}")
                    time.sleep(1)
        
        # Initialize shared data file
        initial_data = {
            'metrics': self.health_monitor.get_metrics_summary(),
            'alerts': [],
            'region_loads': self.load_balancer.region_loads,
            'compression_stats': {
                'avg_ratio': 0.0,
                'total_original': 0,
                'total_compressed': 0,
                'type': str(self.compression_manager.compression_type.value)
            }
        }
        
        with open(shared_data_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        
        self.is_running = True
        threading.Thread(target=update_shared_data, daemon=True).start()