
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich import box
from datetime import datetime
import time
import os
import sys
import json

# Add the parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(current_dir))

from multiregion.health_monitor import HealthMonitor
from multiregion.load_balancer import LoadBalancer
from multiregion.compression_manager import CompressionManager, CompressionType

# Shared data path
SHARED_DATA_PATH = os.path.join(current_dir, 'shared_dashboard_data.json')

def read_shared_data():
    try:
        with open(SHARED_DATA_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def generate_layout():
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
        Layout(name="system_metrics", size=15),
        Layout(name="alerts")
    )
    layout["right"].split(
        Layout(name="region_stats", size=15),
        Layout(name="compression_stats")
    )
    return layout

def run_dashboard():
    """Run the dashboard with all panels"""
    try:
        console = Console()
        layout = generate_layout()
        
        with Live(layout, refresh_per_second=4, screen=True):
            while True:
                shared_data = read_shared_data()
                
                # Update header
                layout["header"].update(
                    Panel(f"Edge Simulator Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                          style="bold white")
                )
                
                # System Metrics Panel
                metrics_table = Table(box=box.ROUNDED)
                metrics_table.add_column("Metric")
                metrics_table.add_column("Current")
                metrics_table.add_column("Average")
                metrics_table.add_column("Max")
                metrics_table.add_column("Min")
                
                metrics = shared_data.get('metrics', {})
                for metric, values in metrics.items():
                    if metric != 'timestamp':
                        metrics_table.add_row(
                            metric,
                            f"{values['current']:>6.2f}",
                            f"{values['avg']:>6.2f}",
                            f"{values['max']:>6.2f}",
                            f"{values['min']:>6.2f}"
                        )
                layout["left"]["system_metrics"].update(
                    Panel(metrics_table, title="System Metrics", border_style="blue")
                )
                
                # Alerts Panel
                alerts_table = Table(box=box.ROUNDED)
                alerts_table.add_column("Time")
                alerts_table.add_column("Metric")
                alerts_table.add_column("Value")
                alerts_table.add_column("Threshold")
                
                alerts = shared_data.get('alerts', [])
                for alert in alerts[:5]:
                    alerts_table.add_row(
                        alert['timestamp'],
                        alert['metric'],
                        f"{alert['value']:.2f}",
                        f"{alert['threshold']:.2f}",
                        style="red"
                    )
                layout["left"]["alerts"].update(
                    Panel(alerts_table, title="Recent Alerts", border_style="red")
                )
                
                # Region Stats Panel
                region_table = Table(box=box.ROUNDED)
                region_table.add_column("Region")
                region_table.add_column("Load")
                region_table.add_column("Status")
                
                region_loads = shared_data.get('region_loads', {})
                for region, load in region_loads.items():
                    status = "OK" if load < 1000 else "HIGH"
                    style = "green" if status == "OK" else "yellow"
                    region_table.add_row(region, str(load), status, style=style)
                layout["right"]["region_stats"].update(
                    Panel(region_table, title="Region Statistics", border_style="green")
                )
                
                # Compression Stats Panel
                comp_table = Table(box=box.ROUNDED)
                comp_table.add_column("Metric")
                comp_table.add_column("Value")
                
                compression_stats = shared_data.get('compression_stats', {})
                if compression_stats:
                    comp_table.add_row("Average Ratio", f"{compression_stats.get('avg_ratio', 0):.2f}%")
                    comp_table.add_row("Total Original", f"{compression_stats.get('total_original', 0)/1024:.2f} KB")
                    comp_table.add_row("Total Compressed", f"{compression_stats.get('total_compressed', 0)/1024:.2f} KB")
                    comp_table.add_row("Compression Type", compression_stats.get('type', 'unknown'))
                
                layout["right"]["compression_stats"].update(
                    Panel(comp_table, title="Compression Statistics", border_style="magenta")
                )
                
                # Update footer
                layout["footer"].update(
                    Panel("Press Ctrl+C to exit", style="dim")
                )
                
                time.sleep(0.25)
                
    except KeyboardInterrupt:
        print("\nDashboard shutting down...")
    except Exception as e:
        print(f"Error in dashboard: {str(e)}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    run_dashboard()
