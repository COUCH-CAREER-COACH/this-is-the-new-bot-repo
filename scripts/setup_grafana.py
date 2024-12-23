"""Set up Grafana with comprehensive arbitrage bot monitoring."""
import requests
import asyncio
import json
import time
import logging
import sys
import yaml
from pathlib import Path
import os
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('grafana_setup.log')
    ]
)
logger = logging.getLogger(__name__)

class GrafanaSetup:
    def __init__(self):
        self.load_config()
        self.setup_status = {
            'grafana_ready': False,
            'api_key_created': False,
            'datasource_configured': False,
            'dashboards_imported': False,
            'alerts_configured': False,
            'users_configured': False
        }

    def load_config(self):
        """Load configuration from environment and config files."""
        try:
            # Load Grafana configuration
            self.grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')
            self.grafana_user = os.getenv('GRAFANA_ADMIN_USER', 'admin')
            self.grafana_password = os.getenv('GRAFANA_ADMIN_PASSWORD', 'admin')
            
            # Load monitoring configuration
            with open('config/test.config.json', 'r') as f:
                config = json.load(f)
                self.monitoring_config = config.get('monitoring', {})

            # Load alert rules
            with open('rules/alerts.yml', 'r') as f:
                self.alert_rules = yaml.safe_load(f)
            
            # Validate configuration
            self.validate_config()
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def validate_config(self):
        """Validate required configuration settings."""
        required_settings = [
            'grafana_url',
            'grafana_user',
            'grafana_password'
        ]
        
        missing_settings = [
            setting for setting in required_settings 
            if not getattr(self, setting, None)
        ]
        
        if missing_settings:
            raise ValueError(f"Missing required settings: {missing_settings}")

    async def wait_for_grafana(self, max_retries: int = 30, retry_interval: int = 2) -> bool:
        """Wait for Grafana to be ready with health check."""
        logger.info("Waiting for Grafana to be ready...")
        
        for i in range(max_retries):
            try:
                response = requests.get(f"{self.grafana_url}/api/health")
                if response.status_code == 200:
                    logger.info("✅ Grafana is ready")
                    self.setup_status['grafana_ready'] = True
                    return True
                    
            except requests.exceptions.ConnectionError:
                pass
            
            logger.info(f"Waiting for Grafana... ({i+1}/{max_retries})")
            time.sleep(retry_interval)
        
        logger.error("❌ Grafana failed to start")
        return False

    async def create_api_key(self) -> Optional[str]:
        """Create Grafana API key with proper permissions."""
        try:
            # Check for existing key
            existing_keys = requests.get(
                f"{self.grafana_url}/api/auth/keys",
                auth=(self.grafana_user, self.grafana_password)
            ).json()
            
            for key in existing_keys:
                if key['name'] == 'arbitrage-bot-key':
                    logger.info("Found existing API key")
                    self.setup_status['api_key_created'] = True
                    return key['id']
            
            # Create new key
            response = requests.post(
                f"{self.grafana_url}/api/auth/keys",
                json={
                    "name": "arbitrage-bot-key",
                    "role": "Admin",
                    "secondsToLive": 0  # Never expires
                },
                auth=(self.grafana_user, self.grafana_password)
            )
            
            if response.status_code == 200:
                key = response.json()["key"]
                logger.info("✅ Created Grafana API key")
                self.setup_status['api_key_created'] = True
                
                # Save key securely
                self.save_api_key(key)
                return key
            else:
                logger.error(f"❌ Failed to create API key: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating API key: {e}")
            return None

    def save_api_key(self, key: str):
        """Save API key securely."""
        key_path = Path('.env.grafana')
        with open(key_path, 'w') as f:
            f.write(f"GRAFANA_API_KEY={key}\n")
        os.chmod(key_path, 0o600)  # Secure file permissions

    async def setup_datasources(self, api_key: str) -> bool:
        """Set up all required data sources."""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            
            # Configure Prometheus
            prometheus_config = {
                "name": "Prometheus",
                "type": "prometheus",
                "url": "http://prometheus:9090",
                "access": "proxy",
                "isDefault": True,
                "jsonData": {
                    "timeInterval": "10s",
                    "queryTimeout": "60s"
                }
            }
            
            response = requests.post(
                f"{self.grafana_url}/api/datasources",
                json=prometheus_config,
                headers=headers
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ Failed to configure Prometheus: {response.text}")
                return False
            
            # Configure additional datasources if needed
            # Example: Loki for logs
            loki_config = {
                "name": "Loki",
                "type": "loki",
                "url": "http://loki:3100",
                "access": "proxy"
            }
            
            response = requests.post(
                f"{self.grafana_url}/api/datasources",
                json=loki_config,
                headers=headers
            )
            
            if response.status_code not in [200, 201]:
                logger.warning(f"⚠️ Failed to configure Loki: {response.text}")
            
            self.setup_status['datasource_configured'] = True
            logger.info("✅ Configured data sources")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configuring data sources: {e}")
            return False

    async def import_dashboards(self, api_key: str) -> bool:
        """Import all required dashboards."""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            dashboard_dir = Path("grafana/dashboards")
            
            # Create dashboard folder
            folder_response = requests.post(
                f"{self.grafana_url}/api/folders",
                json={"title": "Arbitrage Bot"},
                headers=headers
            )
            
            if folder_response.status_code not in [200, 201]:
                logger.error(f"❌ Failed to create dashboard folder: {folder_response.text}")
                return False
            
            folder_id = folder_response.json()["id"]
            
            # Import all dashboard JSON files
            dashboard_files = list(dashboard_dir.glob("*.json"))
            imported_dashboards = []
            
            for dashboard_file in dashboard_files:
                try:
                    with open(dashboard_file) as f:
                        dashboard_json = json.load(f)
                    
                    # Prepare dashboard import
                    import_payload = {
                        "dashboard": dashboard_json,
                        "folderId": folder_id,
                        "overwrite": True,
                        "inputs": []
                    }
                    
                    response = requests.post(
                        f"{self.grafana_url}/api/dashboards/db",
                        json=import_payload,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        dashboard_url = f"{self.grafana_url}/d/{dashboard_json['uid']}"
                        imported_dashboards.append(dashboard_url)
                        logger.info(f"✅ Imported dashboard: {dashboard_file.name}")
                    else:
                        logger.error(f"❌ Failed to import {dashboard_file.name}: {response.text}")
                        
                except Exception as e:
                    logger.error(f"❌ Error importing {dashboard_file.name}: {e}")
            
            if imported_dashboards:
                self.setup_status['dashboards_imported'] = True
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Error importing dashboards: {e}")
            return False

    async def configure_alerts(self, api_key: str) -> bool:
        """Configure alerting rules and notification channels."""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            
            # Configure notification channels
            channels = [
                {
                    "name": "Discord",
                    "type": "discord",
                    "settings": {
                        "url": os.getenv('DISCORD_WEBHOOK_URL')
                    }
                },
                {
                    "name": "Email",
                    "type": "email",
                    "settings": {
                        "addresses": os.getenv('ALERT_EMAIL')
                    }
                }
            ]
            
            for channel in channels:
                response = requests.post(
                    f"{self.grafana_url}/api/alert-notifications",
                    json=channel,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    logger.warning(f"⚠️ Failed to configure {channel['name']} alerts: {response.text}")
            
            # Import alert rules from YAML
            for group in self.alert_rules.get('groups', []):
                response = requests.post(
                    f"{self.grafana_url}/api/ruler/grafana/api/v1/rules",
                    json=group,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    logger.warning(f"⚠️ Failed to import alert rule: {response.text}")
            
            self.setup_status['alerts_configured'] = True
            logger.info("✅ Configured alerting")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configuring alerts: {e}")
            return False

    def generate_setup_report(self):
        """Generate setup report."""
        report_path = Path('reports/grafana_setup.md')
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write("# Grafana Setup Report\n\n")
            f.write(f"Setup Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Setup Status
            f.write("## Setup Status\n\n")
            for component, status in self.setup_status.items():
                status_icon = "✅" if status else "❌"
                f.write(f"- {component}: {status_icon}\n")
            f.write("\n")
            
            # Access Information
            f.write("## Access Information\n\n")
            f.write(f"- URL: {self.grafana_url}\n")
            f.write(f"- Admin Username: {self.grafana_user}\n")
            f.write("- Admin Password: [Set during setup]\n\n")
            
            # Next Steps
            f.write("## Next Steps\n\n")
            if all(self.setup_status.values()):
                f.write("1. Change default admin password\n")
                f.write("2. Verify dashboard access\n")
                f.write("3. Test alert notifications\n")
                f.write("4. Review metric collection\n")
            else:
                f.write("1. Review setup logs\n")
                f.write("2. Address failed components\n")
                f.write("3. Re-run setup script\n")
        
        return report_path

async def main():
    """Main setup function."""
    try:
        setup = GrafanaSetup()
        
        # Wait for Grafana
        if not await setup.wait_for_grafana():
            sys.exit(1)
        
        # Create API key
        api_key = await setup.create_api_key()
        if not api_key:
            sys.exit(1)
        
        # Setup components
        setup_steps = [
            ("Data Sources", setup.setup_datasources(api_key)),
            ("Dashboards", setup.import_dashboards(api_key)),
            ("Alerts", setup.configure_alerts(api_key))
        ]
        
        for step_name, coro in setup_steps:
            logger.info(f"Setting up {step_name}...")
            if not await coro:
                logger.error(f"{step_name} setup failed")
                sys.exit(1)
        
        # Generate setup report
        report_path = setup.generate_setup_report()
        logger.info(f"Setup report generated: {report_path}")
        
        if all(setup.setup_status.values()):
            logger.info("\n🎉 Grafana Setup Complete!")
            logger.info("------------------------")
            logger.info(f"URL: {setup.grafana_url}")
            logger.info("Default credentials:")
            logger.info(f"  Username: {setup.grafana_user}")
            logger.info(f"  Password: {setup.grafana_password}")
            logger.info("\nPlease change the default password after logging in.")
            sys.exit(0)
        else:
            logger.error("\n❌ Setup incomplete. Please review the logs and retry.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
