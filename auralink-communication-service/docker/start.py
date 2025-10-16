#!/usr/bin/env python3
"""
AuraLink Communication Service Startup Script
Initializes Matrix Synapse with AuraLink customizations
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

def generate_homeserver_config():
    """Generate homeserver.yaml from environment variables"""
    config_dir = Path(os.getenv('SYNAPSE_CONFIG_DIR', '/data'))
    config_path = config_dir / 'homeserver.yaml'
    
    if config_path.exists():
        print(f"✓ Homeserver configuration already exists at {config_path}")
        return config_path
    
    print("⚙️  Generating homeserver configuration...")
    
    # Generate base config using Synapse's built-in tool
    subprocess.run([
        'python3', '-m', 'synapse.app.homeserver',
        '--server-name', os.getenv('SYNAPSE_SERVER_NAME', 'auralink.network'),
        '--config-path', str(config_path),
        '--generate-config',
        '--report-stats', os.getenv('SYNAPSE_REPORT_STATS', 'no')
    ], check=True)
    
    # Load generated config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Apply AuraLink customizations
    config.update({
        # Database configuration
        'database': {
            'name': 'psycopg2',
            'args': {
                'user': os.getenv('POSTGRES_USER', 'auralink'),
                'password': os.getenv('POSTGRES_PASSWORD', 'auralink'),
                'database': os.getenv('POSTGRES_DB', 'auralink_comm'),
                'host': os.getenv('POSTGRES_HOST', 'postgres'),
                'port': int(os.getenv('POSTGRES_PORT', '5432')),
                'cp_min': 5,
                'cp_max': 10,
            }
        },
        
        # Redis for caching and presence
        'redis': {
            'enabled': True,
            'host': os.getenv('REDIS_HOST', 'redis'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'password': os.getenv('REDIS_PASSWORD'),
        } if os.getenv('REDIS_HOST') else {'enabled': False},
        
        # Federation settings
        'federation_ip_range_blacklist': [
            '127.0.0.0/8',
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16',
            '100.64.0.0/10',
            '169.254.0.0/16',
            '::1/128',
            'fe80::/64',
            'fc00::/7',
        ],
        
        'enable_registration': os.getenv('ENABLE_REGISTRATION', 'false').lower() == 'true',
        'registration_shared_secret': os.getenv('MATRIX_REGISTRATION_SECRET'),
        
        # Performance tuning
        'event_cache_size': '10K',
        'caches': {
            'global_factor': 1.0,
            'per_cache_factors': {
                'get_users_in_room': 5.0,
            }
        },
        
        # Metrics
        'enable_metrics': True,
        'metrics_port': 9000,
        
        # Listeners
        'listeners': [
            {
                'port': 8008,
                'tls': False,
                'type': 'http',
                'x_forwarded': True,
                'bind_addresses': ['0.0.0.0'],
                'resources': [
                    {'names': ['client', 'federation'], 'compress': True}
                ]
            },
            {
                'port': 9000,
                'tls': False,
                'type': 'http',
                'resources': [{'names': ['metrics'], 'compress': False}]
            }
        ],
        
        # AuraLink modules (placeholder for Phase 2+)
        'modules': []
    })
    
    # Write customized config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"✓ Homeserver configuration generated at {config_path}")
    return config_path


def check_database():
    """Check database connectivity"""
    import psycopg2
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER', 'auralink'),
            password=os.getenv('POSTGRES_PASSWORD', 'auralink'),
            database=os.getenv('POSTGRES_DB', 'auralink_comm'),
            connect_timeout=5
        )
        conn.close()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def main():
    """Main startup sequence"""
    print("=" * 60)
    print("AuraLink Communication Service - Starting...")
    print("=" * 60)
    
    # Wait for database
    import time
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if check_database():
            break
        retry_count += 1
        print(f"Waiting for database... ({retry_count}/{max_retries})")
        time.sleep(2)
    
    if retry_count >= max_retries:
        print("✗ Database not available after 30 retries. Exiting.")
        sys.exit(1)
    
    # Generate configuration
    config_path = generate_homeserver_config()
    
    # Run database migrations
    print("⚙️  Running database migrations...")
    subprocess.run([
        'python3', '-m', 'synapse.app.homeserver',
        '--config-path', str(config_path),
        'migrate_config'
    ])
    
    print("=" * 60)
    print("✓ Startup complete. Starting Synapse...")
    print("=" * 60)
    
    # Start Synapse
    os.execvp('python3', [
        'python3', '-m', 'synapse.app.homeserver',
        '--config-path', str(config_path)
    ])


if __name__ == '__main__':
    main()
