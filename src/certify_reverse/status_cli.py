#!/usr/bin/env python3
"""
Status display module for Caddy reverse proxy setup.
Shows configuration, certificates, and directory structure in a nicely formatted display.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any
import logging

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich import box
except ImportError:
    print("❌ Rich library not found. Please install: pip install rich")
    sys.exit(1)

# Import our app modules
from .cli import DATADIR, ReverseProxyConfig, configure_logging

console = Console()
log = logging.getLogger(__name__)


def show_configuration_status():
    """Display current configuration in a formatted table."""
    try:
        cfg = ReverseProxyConfig.from_sources()
        
        # Configuration overview table
        config_table = Table(title="🔧 Configuration Overview", box=box.ROUNDED)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")
        
        config_table.add_row("Domain", cfg.domain)
        config_table.add_row("Email", cfg.email)
        config_table.add_row("DNS Provider", cfg.dns_provider)
        config_table.add_row("DNS Token", f"{'*' * (len(cfg.dns_token) - 4)}{cfg.dns_token[-4:]}" if len(cfg.dns_token) > 4 else "***")
        config_table.add_row("Total Upstreams", str(len(cfg.upstreams)))
        
        console.print(config_table)
        console.print()
        
        # Upstreams table
        if cfg.upstreams:
            upstream_table = Table(title="🌐 Upstream Services", box=box.ROUNDED)
            upstream_table.add_column("Subdomain", style="cyan")
            upstream_table.add_column("Full Domain", style="blue")
            upstream_table.add_column("Target", style="green")
            upstream_table.add_column("Scheme", style="yellow")
            upstream_table.add_column("HTTPS", style="red")
            upstream_table.add_column("Skip Verify", style="magenta")
            
            for upstream in cfg.upstreams:
                full_domain = f"{upstream.subdomain}.{cfg.domain}"
                target = f"{upstream.ip}:{upstream.port}"
                https_backend = "✅ Yes" if upstream.is_https else "❌ No"
                skip_verify = "⚠️ Yes" if upstream.skip_verify else "✅ No"
                
                upstream_table.add_row(
                    upstream.subdomain,
                    full_domain,
                    target,
                    upstream.scheme.upper(),
                    https_backend,
                    skip_verify
                )
            
            console.print(upstream_table)
        else:
            console.print(Panel("No upstream services configured", title="🌐 Upstream Services"))
        
        console.print()
        
    except Exception as e:
        console.print(Panel(f"❌ Failed to load configuration: {e}", title="Configuration Error", style="red"))


def show_certificate_status():
    """Display certificate information."""
    cert_table = Table(title="🔐 Certificate Status", box=box.ROUNDED)
    cert_table.add_column("Certificate Type", style="cyan")
    cert_table.add_column("Path", style="blue")
    cert_table.add_column("Status", style="green")
    cert_table.add_column("Size", style="yellow")
    
    # Check main exported certificates
    exported_dir = DATADIR / "exported-certs"
    ca_pem = exported_dir / "caddy-internal-ca.pem"
    ca_crt = exported_dir / "caddy-internal-ca.crt"
    
    cert_files = [
        ("CA Certificate (PEM)", ca_pem),
        ("CA Certificate (CRT)", ca_crt),
    ]
    
    for cert_type, cert_path in cert_files:
        if cert_path.exists():
            size = f"{cert_path.stat().st_size} bytes"
            status = "✅ Exists"
        else:
            size = "-"
            status = "❌ Missing"
        
        cert_table.add_row(cert_type, str(cert_path), status, size)
    
    console.print(cert_table)
    console.print()


def show_service_directories():
    """Display service-specific directory structure."""
    try:
        cfg = ReverseProxyConfig.from_sources()
        
        # Create a tree structure for service directories
        tree = Tree("📁 Service Directories", style="bold blue")
        
        for upstream in cfg.upstreams:
            service_dir = DATADIR / upstream.subdomain
            service_node = tree.add(f"📂 {upstream.subdomain}/", style="cyan")
            
            if service_dir.exists():
                files = list(service_dir.iterdir())
                for file_path in sorted(files):
                    if file_path.is_file():
                        size = file_path.stat().st_size
                        icon = "📄" if file_path.suffix in [".pem", ".crt"] else "📝"
                        service_node.add(f"{icon} {file_path.name} ({size} bytes)", style="green")
                    else:
                        service_node.add(f"📁 {file_path.name}/", style="blue")
                
                if not files:
                    service_node.add("📭 Empty directory", style="yellow")
            else:
                service_node.add("❌ Directory not found", style="red")
        
        if not cfg.upstreams:
            tree.add("📭 No services configured", style="yellow")
        
        console.print(Panel(tree, title="Service Directory Structure"))
        console.print()
        
    except Exception as e:
        console.print(Panel(f"❌ Failed to scan service directories: {e}", title="Directory Error", style="red"))


def show_data_directory_overview():
    """Display overview of the main data directory."""
    tree = Tree(f"📁 {DATADIR}", style="bold blue")
    
    if DATADIR.exists():
        try:
            for item in sorted(DATADIR.iterdir()):
                if item.is_dir():
                    item_node = tree.add(f"📁 {item.name}/", style="cyan")
                    try:
                        files = list(item.iterdir())
                        file_count = len([f for f in files if f.is_file()])
                        dir_count = len([f for f in files if f.is_dir()])
                        item_node.add(f"📄 {file_count} files, 📁 {dir_count} directories", style="dim")
                    except PermissionError:
                        item_node.add("🔒 Permission denied", style="red")
                else:
                    size = item.stat().st_size
                    icon = "⚙️" if item.suffix in [".yml", ".yaml", ".conf"] else "📄"
                    tree.add(f"{icon} {item.name} ({size} bytes)", style="green")
        except Exception as e:
            tree.add(f"❌ Error reading directory: {e}", style="red")
    else:
        tree.add("❌ Data directory not found", style="red")
    
    console.print(Panel(tree, title="Data Directory Overview"))
    console.print()


def show_generated_files():
    """Display information about generated configuration files."""
    files_table = Table(title="📝 Generated Files", box=box.ROUNDED)
    files_table.add_column("File", style="cyan")
    files_table.add_column("Path", style="blue")
    files_table.add_column("Status", style="green")
    files_table.add_column("Modified", style="yellow")
    
    important_files = [
        ("Caddyfile", DATADIR / "Caddyfile"),
        ("DNSmasq Config", DATADIR / "dnsmasq.conf"),
        ("TLS Setup Guide", DATADIR / "upstream-tls-setup.md"),
        ("App Log", DATADIR / "logs" / "app.log"),
    ]
    
    for file_type, file_path in important_files:
        if file_path.exists():
            import datetime
            mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
            status = "✅ Exists"
            modified = mtime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            status = "❌ Missing"
            modified = "-"
        
        files_table.add_row(file_type, str(file_path), status, modified)
    
    console.print(files_table)
    console.print()


def show_full_status():
    """Display complete status overview."""
    console.print()
    console.print(Panel.fit("🚀 Caddy Reverse Proxy Status", style="bold magenta"))
    console.print()
    
    show_configuration_status()
    show_certificate_status()
    show_service_directories()
    show_generated_files()
    show_data_directory_overview()


def main():
    """Main entry point for status display."""
    import argparse
    configure_logging()
    
    parser = argparse.ArgumentParser(description="Display Caddy reverse proxy status")
    parser.add_argument("--config", action="store_true", help="Show only configuration")
    parser.add_argument("--certs", action="store_true", help="Show only certificates")
    parser.add_argument("--services", action="store_true", help="Show only service directories")
    parser.add_argument("--files", action="store_true", help="Show only generated files")
    parser.add_argument("--data", action="store_true", help="Show only data directory")
    
    args = parser.parse_args()
    
    # If no specific section requested, show everything
    if not any([args.config, args.certs, args.services, args.files, args.data]):
        show_full_status()
        return
    
    console.print()
    console.print(Panel.fit("🚀 Caddy Reverse Proxy Status", style="bold magenta"))
    console.print()
    
    if args.config:
        show_configuration_status()
    
    if args.certs:
        show_certificate_status()
    
    if args.services:
        show_service_directories()
    
    if args.files:
        show_generated_files()
    
    if args.data:
        show_data_directory_overview()


if __name__ == "__main__":
    main()
