#!/usr/bin/env python3
"""
Network Server Launcher for Exam Generation System
Launches Flask server with network discovery capabilities
Does NOT modify existing functionality - just adds network features
"""

import os
import sys
import socket
import time
import json
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def get_network_info():
    """Get laptop network information"""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        port = 5000

        return {
            "hostname": hostname,
            "ip": local_ip,
            "port": port,
            "url": f"http://{local_ip}:{port}",
            "discovery_url": f"http://{local_ip}:{port}/discover",
            "localhost_url": f"http://localhost:{port}"
        }
    except Exception as e:
        print(f"⚠️  Could not get network info: {e}")
        return None

def print_startup_banner():
    """Print beautiful startup banner with network info"""
    info = get_network_info()

    if not info:
        print("⚠️  Warning: Could not determine network information")
        return

    print("\n" + "="*90)
    print(" "*20 + "🚀 EXAM GENERATION SYSTEM - NETWORK SERVER")
    print("="*90)
    print()
    print(f"  📱 LAPTOP INFORMATION:")
    print(f"     Device Name:  {info['hostname']}")
    print(f"     Your IP:      {info['ip']}")
    print(f"     Port:         {info['port']}")
    print()
    print("="*90)
    print(f"  🌐 HOW TO ACCESS:")
    print("="*90)
    print()
    print(f"  1️⃣  THIS LAPTOP (Local):")
    print(f"      {info['localhost_url']}")
    print()
    print(f"  2️⃣  OTHER DEVICES (Same Network):")
    print(f"      {info['url']}")
    print()
    print(f"  3️⃣  AUTO-DISCOVERY PAGE (Share this with others):")
    print(f"      {info['discovery_url']}")
    print()
    print("="*90)
    print(f"  📋 SHARE THIS URL WITH OTHERS:")
    print("="*90)
    print()
    print(f"      {info['url']}")
    print()
    print("="*90)
    print()
    print(f"  ⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ Server is ready to accept connections")
    print()
    print("="*90 + "\n")

def create_discovery_routes(app):
    """Add network discovery routes to Flask app"""
    from flask import render_template_string

    info = get_network_info()

    if not info:
        return  # Skip discovery if can't get network info

    def discover():
        """Auto-discovery page for network devices"""
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Exam System - Network Discovery</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }}

                .container {{
                    background: white;
                    padding: 50px;
                    border-radius: 15px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    max-width: 650px;
                    text-align: center;
                    animation: slideIn 0.5s ease-out;
                }}

                @keyframes slideIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(-20px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}

                h1 {{
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 36px;
                }}

                .subtitle {{
                    color: #666;
                    margin-bottom: 30px;
                    font-size: 16px;
                }}

                .status-badge {{
                    display: inline-block;
                    background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
                    color: white;
                    padding: 12px 25px;
                    border-radius: 25px;
                    margin: 20px 0;
                    font-weight: bold;
                    font-size: 14px;
                    box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
                }}

                .server-info {{
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    padding: 30px;
                    border-radius: 10px;
                    margin: 30px 0;
                    border-left: 5px solid #667eea;
                }}

                .info-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 15px 0;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                }}

                .info-item:last-child {{
                    border-bottom: none;
                }}

                .label {{
                    font-weight: 600;
                    color: #333;
                    text-align: left;
                    flex: 1;
                }}

                .value {{
                    font-family: 'Courier New', monospace;
                    background: white;
                    padding: 10px 15px;
                    border-radius: 5px;
                    color: #667eea;
                    font-weight: bold;
                    text-align: right;
                    flex: 1;
                    word-break: break-all;
                }}

                .access-section {{
                    background: #e3f2fd;
                    padding: 25px;
                    border-radius: 10px;
                    margin: 30px 0;
                    border-left: 5px solid #2196f3;
                }}

                .access-section h3 {{
                    color: #1976d2;
                    margin-bottom: 15px;
                }}

                .access-url {{
                    background: white;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                    font-size: 16px;
                    color: #667eea;
                    font-weight: bold;
                    word-break: break-all;
                    margin: 15px 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}

                .copy-btn {{
                    background: #4caf50;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: 0.3s;
                }}

                .copy-btn:hover {{
                    background: #45a049;
                    transform: translateY(-2px);
                }}

                .access-button {{
                    display: inline-block;
                    padding: 15px 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                    transition: 0.3s;
                    margin: 20px 10px;
                    border: none;
                    cursor: pointer;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                }}

                .access-button:hover {{
                    transform: translateY(-3px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
                }}

                .instructions {{
                    background: #fff3e0;
                    padding: 25px;
                    border-radius: 10px;
                    margin: 30px 0;
                    text-align: left;
                    border-left: 5px solid #ff9800;
                }}

                .instructions h3 {{
                    color: #e65100;
                    margin-bottom: 15px;
                }}

                .instructions ol {{
                    margin-left: 20px;
                    color: #333;
                    line-height: 2;
                }}

                .instructions li {{
                    margin-bottom: 10px;
                }}

                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 12px;
                }}

                .qr-section {{
                    margin: 30px 0;
                    padding: 20px;
                    background: #f9f9f9;
                    border-radius: 10px;
                }}

                @media (max-width: 600px) {{
                    .container {{
                        padding: 30px 20px;
                    }}

                    h1 {{
                        font-size: 24px;
                    }}

                    .info-item {{
                        flex-direction: column;
                        align-items: flex-start;
                    }}

                    .value {{
                        text-align: left;
                        width: 100%;
                        margin-top: 8px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📚 Exam Generation System</h1>
                <p class="subtitle">Ai-Assisted Exam Generator (AWEGEN)</p>

                <div class="status-badge">✅ Server Online</div>

                <div class="server-info">
                    <div class="info-item">
                        <span class="label">📱 Device Name:</span>
                        <span class="value">{info['hostname']}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">🌐 IP Address:</span>
                        <span class="value">{info['ip']}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">🔌 Port:</span>
                        <span class="value">{info['port']}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">🔗 Full URL:</span>
                        <span class="value">{info['url']}</span>
                    </div>
                </div>

                <div class="access-section">
                    <h3>🔗 How to Access</h3>
                    <div class="access-url">
                        <span>{info['url']}</span>
                        <button class="copy-btn" onclick="copyUrl()">Copy</button>
                    </div>
                </div>

                <button class="access-button" onclick="window.location.href='http://{info['ip']}:3000'">
                    ✨ Enter Exam System →
                </button>

                <div class="instructions">
                    <h3>📖 Step-by-Step Instructions</h3>
                    <ol>
                        <li><strong>Connect:</strong> Make sure you're on the same WiFi network</li>
                        <li><strong>Open Browser:</strong> Chrome, Firefox, Safari, or Edge</li>
                        <li><strong>Enter URL:</strong> <code>{info['url']}</code></li>
                        <li><strong>Login:</strong> Use your credentials</li>
                        <li><strong>Start Exam:</strong> Begin taking the exam</li>
                    </ol>
                </div>

                <div class="footer">
                    <p>✅ System is running on: <strong>{info['hostname']}</strong></p>
                    <p>⏱️ Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>🔐 Make sure you're on the correct network before entering your credentials</p>
                </div>
            </div>

            <script>
                function copyUrl() {{
                    const url = "{info['url']}";
                    navigator.clipboard.writeText(url).then(() => {{
                        alert("URL copied to clipboard!\\n\\n" + url);
                    }}).catch(() => {{
                        prompt("Copy this URL:", url);
                    }});
                }}

                // Auto-copy on page load (optional)
                // copyUrl();
            </script>
        </body>
        </html>
        """

        return render_template_string(html_template)

    def server_info_api():
        """API endpoint for server information"""
        return json.dumps({
            "status": "online",
            "server_name": info['hostname'],
            "ip_address": info['ip'],
            "port": info['port'],
            "url": info['url'],
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }), 200, {'Content-Type': 'application/json'}

    # Register routes using add_url_rule (works better with reloader)
    app.add_url_rule('/discover', 'discover', discover, methods=['GET'])
    app.add_url_rule('/api/server-info', 'server_info_api', server_info_api, methods=['GET'])

def main():
    """Main entry point"""
    import warnings
    warnings.filterwarnings("ignore", message="Failed to load image Python extension")

    # Print startup information
    print_startup_banner()

    # Import and create app
    from app import create_app
    app = create_app('development')

    # Add discovery routes (non-breaking)
    try:
        create_discovery_routes(app)
        print("✅ Network discovery routes added")
    except Exception as e:
        print(f"⚠️  Warning: Could not add discovery routes: {e}")
        import traceback
        traceback.print_exc()

    # Run Flask server
    print("🚀 Starting Flask server...\n")
    app.run(
        host='0.0.0.0',      # Listen on ALL network interfaces
        port=5000,
        debug=False,         # Disable debug mode to avoid reloader issues
        use_reloader=False   # Disable reloader
    )

if __name__ == '__main__':
    main()
