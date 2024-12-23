#!/usr/bin/env python3
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/setup.log')
    ]
)
logger = logging.getLogger(__name__)

class TestEnvironmentSetup:
    def __init__(self):
        self.project_root = Path(os.getcwd())
        
    def setup(self):
        try:
            logger.info("\nStarting test environment setup...\n")
            
            # Clean up old test data
            self.cleanup_old_data()
            
            # Verify dependencies
            self.verify_dependencies()
            
            # Setup directories
            self.setup_directories()
            
            # Start local network
            self.setup_local_network()
            
            logger.info("✅ Test environment setup complete!")
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Setup failed: {e}")
            self.cleanup()
            return False

    def cleanup_old_data(self):
        try:
            logger.info("Cleaning up old test data...")
            dirs_to_clean = ['logs', 'metrics', 'reports/test_results', 'data/ganache', 'tmp']
            for dir_path in dirs_to_clean:
                path = self.project_root / dir_path
                if path.exists():
                    shutil.rmtree(path)
            logger.info("✅ Old test data cleaned up")
        except Exception as e:
            logger.error(f"Failed to clean up old data: {e}")
            raise

    def verify_dependencies(self):
        try:
            logger.info("Verifying dependencies...")
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Node.js version: {result.stdout.strip()}")
            else:
                raise Exception("Node.js not found")
            subprocess.run(['pip', 'install', '-r', 'test-requirements.txt'], check=True)
            logger.info("✅ Dependencies verified and installed")
        except Exception as e:
            logger.error(f"Failed to verify dependencies: {e}")
            raise

    def setup_directories(self):
        try:
            logger.info("Setting up directories...")
            dirs_to_create = ['logs', 'metrics', 'reports/test_results', 'data/ganache', 'tmp']
            for dir_path in dirs_to_create:
                path = self.project_root / dir_path
                path.mkdir(parents=True, exist_ok=True)
                os.chmod(str(path), 0o777)
            logger.info("✅ Directories created")
        except Exception as e:
            logger.error(f"Failed to setup directories: {e}")
            raise

    def setup_local_network(self):
        try:
            logger.info("Setting up local network...")
            subprocess.run(['docker-compose', '-f', 'docker-compose.test.yml', 'up', '-d'], check=True)
            self.wait_for_services()
            logger.info("✅ Local network setup complete")
        except Exception as e:
            logger.error(f"Failed to setup local network: {e}")
            self.cleanup()
            raise

    def wait_for_services(self, timeout=300):
        services = {
            'geth': {'port': 8545},
            'prometheus': {'port': 9090},
            'grafana': {'port': 3000},
            'redis': {'port': 6379}
        }
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_ready = True
            for service_name, service_info in services.items():
                try:
                    logger.info(f"Checking {service_name}...")
                    result = subprocess.run(
                        ['nc', '-z', 'localhost', str(service_info['port'])],
                        capture_output=True
                    )
                    if result.returncode != 0:
                        logger.info(f"{service_name} not ready")
                        all_ready = False
                        break
                except Exception as e:
                    logger.info(f"Error checking {service_name}: {e}")
                    all_ready = False
                    break
            
            if all_ready:
                logger.info("✅ All services are ready")
                return
            
            logger.info("Waiting for services to be ready...")
            time.sleep(10)
        
        raise Exception("Timeout waiting for services")

    def cleanup(self):
        try:
            logger.info("\nStopping local network...")
            subprocess.run(['docker-compose', '-f', 'docker-compose.test.yml', 'down', '-v'], check=True)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    setup = TestEnvironmentSetup()
    success = setup.setup()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
