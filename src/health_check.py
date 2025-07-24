#!/usr/bin/env python
"""
Health check script for Pokemon Discord Bot.

This script checks the health of the bot and exits with code 0 if healthy,
or non-zero if unhealthy. Used by Docker health checks.
"""
import sys
import argparse
import requests
import json
import time
from urllib.parse import urljoin


def check_health(base_url="http://localhost:8080", endpoint="/health", detailed=False, retries=3, retry_delay=1):
    """Check health of the bot."""
    if detailed:
        endpoint = "/health/detailed"
    
    health_url = urljoin(base_url, endpoint)
    
    for attempt in range(retries):
        try:
            # Try to connect to the health endpoint
            response = requests.get(health_url, timeout=5)
            
            # Check if response is successful
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get("status")
                
                if status == "healthy":
                    print("Service is healthy")
                    if detailed:
                        print(json.dumps(health_data, indent=2))
                    return True
                else:
                    print(f"Service is not healthy: {status}")
                    if detailed:
                        print(json.dumps(health_data, indent=2))
                    return False
            else:
                print(f"Health check failed with status code: {response.status_code}")
                if attempt < retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                
        except requests.RequestException as e:
            print(f"Health check failed: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
    
    return False


def check_metrics(base_url="http://localhost:8080"):
    """Check metrics endpoint."""
    try:
        metrics_url = urljoin(base_url, "/metrics")
        response = requests.get(metrics_url, timeout=5)
        
        if response.status_code == 200:
            metrics_data = response.json()
            print(json.dumps(metrics_data, indent=2))
            return True
        else:
            print(f"Metrics check failed with status code: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"Metrics check failed: {e}")
        return False


def check_status(base_url="http://localhost:8080"):
    """Check status endpoint."""
    try:
        status_url = urljoin(base_url, "/status")
        response = requests.get(status_url, timeout=5)
        
        if response.status_code == 200:
            status_data = response.json()
            print(json.dumps(status_data, indent=2))
            return True
        else:
            print(f"Status check failed with status code: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"Status check failed: {e}")
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Health check tool for Pokemon Discord Bot')
    
    parser.add_argument(
        '--url',
        default='http://localhost:8080',
        help='Base URL for health check (default: http://localhost:8080)'
    )
    
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Use detailed health check endpoint'
    )
    
    parser.add_argument(
        '--metrics',
        action='store_true',
        help='Check metrics endpoint instead of health'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check status endpoint instead of health'
    )
    
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Number of retry attempts (default: 3)'
    )
    
    parser.add_argument(
        '--retry-delay',
        type=float,
        default=1.0,
        help='Initial delay between retries in seconds (default: 1.0)'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.metrics:
        if check_metrics(args.url):
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.status:
        if check_status(args.url):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        if check_health(args.url, detailed=args.detailed, retries=args.retries, retry_delay=args.retry_delay):
            sys.exit(0)
        else:
            sys.exit(1)