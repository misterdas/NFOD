"""
NFD - Participant OI Analysis Dashboard Server
Serves static dashboard files and provides endpoints for CSV data and fetching latest NSE data.
"""
import os
import sys
import json
import subprocess
import pandas as pd
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8000
DATA_FILE = "FDCP_Data.csv"
SCRIPT_FILE = "FDCP.py"

class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                if os.path.exists(DATA_FILE):
                    df = pd.read_csv(DATA_FILE)
                    df.columns = [c.strip() for c in df.columns]
                    # Convert to records
                    data = df.to_dict(orient='records')
                    self.wfile.write(json.dumps({'status': 'success', 'data': data}).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'Data file not found'}).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        elif path == '/api/money-flow':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                mf_file = os.path.join(os.path.dirname(__file__), 'docs', 'money_flow_data.json')
                if os.path.exists(mf_file):
                    with open(mf_file, 'r') as f:
                        mf_data = json.load(f)
                    self.wfile.write(json.dumps({'status': 'success', 'data': mf_data}).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'Money flow data not generated yet. Run pipeline first.'}).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        elif path in ['/api/update', '/api/daily-pipeline']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                print("Running After-Market Pipeline (FDCP.py -> OC.py -> money_flow_engine.py)...")
                cwd = os.path.dirname(os.path.abspath(__file__))
                
                # Step 1: Run FDCP.py
                r1 = subprocess.run([sys.executable, SCRIPT_FILE], capture_output=True, text=True, cwd=cwd)
                
                # Step 2: Run OC.py
                r2 = subprocess.run([sys.executable, "OC.py"], capture_output=True, text=True, cwd=cwd)
                
                # Step 3: Run money_flow_engine.py
                r3 = subprocess.run([sys.executable, "money_flow_engine.py"], capture_output=True, text=True, cwd=cwd)
                
                self.wfile.write(json.dumps({
                    'status': 'success',
                    'message': 'After-market pipeline executed successfully!',
                    'fdcp_output': r1.stdout,
                    'oc_output': r2.stdout,
                    'engine_output': r3.stdout
                }).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        super().do_GET()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"Server started at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
