#!/usr/bin/env python3
"""
Supervisor script to run both web server and Celery worker
"""

import os
import sys
import signal
import subprocess
import time
from threading import Thread

def start_process(cmd, name):
    """Start a process and monitor it"""
    print(f"Starting {name}...")
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Print output in real-time
    for line in iter(process.stdout.readline, ''):
        print(f"[{name}] {line.strip()}")
    
    process.wait()
    print(f"{name} process ended with code {process.returncode}")
    return process.returncode

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)

def main():
    # Handle shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get port from environment
    port = os.getenv('PORT', '8000')
    
    # Define commands
    web_cmd = f"uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port {port}"
    worker_cmd = "uv run --no-sync celery -A app.celery_worker:celery_app worker --loglevel=info"
    
    # Start worker in background thread
    worker_thread = Thread(target=start_process, args=(worker_cmd, "WORKER"))
    worker_thread.daemon = True
    worker_thread.start()
    
    # Small delay to let worker start
    time.sleep(2)
    
    # Start web server in main thread
    try:
        start_process(web_cmd, "WEB")
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()