"""Verify YAML configuration loading across all scripts."""
import sys
import logging
import yaml
import json
import os
import traceback
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def verify_imports() -> bool:
    """Verify all required imports are available."""
    required_modules = {
        'yaml': 'pyyaml',
        'web3': 'web3',
        'prometheus_client': 'prometheus-client'
    }
    
    missing_modules = []
    for module, package in required_modules.items():
        try:
            __import__(module)
            print(f"✓ {module} imported successfully")
        except ImportError:
            missing_modules.append(f"{module} ({package})")
            print(f"✗ Failed to import {module}")
    
    if missing_modules:
        print("\nMissing required packages. Please install:")
        for module in missing_modules:
            print(f"pip install {module}")
        return False
    return True

def verify_yaml_file(path: str) -> bool:
    """Verify a YAML file can be loaded."""
    try:
        print(f"\nVerifying {path}...")
        
        # Check file existence
        if not os.path.exists(path):
            print(f"✗ File not found: {path}")
            print(f"  Current working directory: {os.getcwd()}")
            print(f"  Full path: {os.path.abspath(path)}")
            return False
        
        # Check file permissions    
        if not os.access(path, os.R_OK):
            print(f"✗ File not readable: {path}")
            return False
            
        # Try to load and validate YAML
        with open(path, 'r') as f:
            content = f.read()
            print(f"File contents ({len(content)} bytes):")
            print("-" * 40)
            print(content[:500] + "..." if len(content) > 500 else content)
            print("-" * 40)
            
            # Parse YAML
            yaml.safe_load(content)
            
        print(f"✓ Successfully loaded and validated {path}")
        return True
        
    except yaml.YAMLError as e:
        print(f"✗ YAML parsing error in {path}: {e}")
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"  Error position: line {mark.line + 1}, column {mark.column + 1}")
        return False
        
    except Exception as e:
        print(f"✗ Error reading {path}: {e}")
        print(f"  Error type: {type(e).__name__}")
        return False

def verify_json_file(path: str) -> bool:
    """Verify a JSON file can be loaded."""
    try:
        print(f"\nVerifying {path}...")
        if not os.path.exists(path):
            print(f"✗ File not found: {path}")
            return False
            
        with open(path, 'r') as f:
            content = f.read()
            print(f"File contents ({len(content)} bytes):")
            print("-" * 40)
            print(content[:500] + "..." if len(content) > 500 else content)
            print("-" * 40)
            
            # Parse JSON
            json.loads(content)
            
        print(f"✓ Successfully loaded {path}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON parsing error in {path}: {e}")
        print(f"  Error position: line {e.lineno}, column {e.colno}")
        return False
        
    except Exception as e:
        print(f"✗ Error reading {path}: {e}")
        print(f"  Error type: {type(e).__name__}")
        return False

def verify_directory_structure() -> bool:
    """Verify required directories exist and create if missing."""
    required_dirs = {
        'config': ['test.config.json', 'test.yaml'],
        'scripts': [],
        'src': [],
        'test': [],
        'reports': [],
        'rules': ['alerts.yml'],
        'grafana/provisioning/datasources': ['prometheus.yml'],
        'grafana/provisioning/dashboards': ['default.yml']
    }
    
    print("\nVerifying directory structure...")
    missing_items = {'dirs': [], 'files': []}
    
    for dir_path, required_files in required_dirs.items():
        # Check/create directory
        if not os.path.isdir(dir_path):
            print(f"✗ Directory not found: {dir_path}")
            try:
                os.makedirs(dir_path)
                print(f"  ✓ Created directory: {dir_path}")
            except Exception as e:
                print(f"  ✗ Failed to create directory: {e}")
                missing_items['dirs'].append(dir_path)
        else:
            print(f"✓ Found directory: {dir_path}")
        
        # Check required files
        for file_name in required_files:
            file_path = os.path.join(dir_path, file_name)
            if not os.path.isfile(file_path):
                print(f"  ✗ Required file not found: {file_path}")
                missing_items['files'].append(file_path)
            else:
                print(f"  ✓ Found file: {file_path}")
    
    if missing_items['dirs'] or missing_items['files']:
        print("\nMissing items:")
        if missing_items['dirs']:
            print("\nDirectories to create:")
            for dir_name in missing_items['dirs']:
                print(f"mkdir -p {dir_name}")
        if missing_items['files']:
            print("\nFiles to create:")
            for file_path in missing_items['files']:
                print(f"touch {file_path}")
        return False
    return True

def main():
    """Main verification function."""
    try:
        print("\n=== Starting YAML Configuration Verification ===\n")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Python executable: {sys.executable}")
        print(f"Python version: {sys.version}")
        
        # Step 1: Verify imports
        print("\n1. Verifying Python packages...")
        try:
            import yaml
            print(f"✓ PyYAML version: {yaml.__version__}")
        except ImportError:
            print("✗ PyYAML not installed")
            return 1
        
        # Step 2: Directory Structure
        print("\n2. Verifying directory structure...")
        if not verify_directory_structure():
            print("\n✗ Directory structure verification failed")
            return 1
        print("\n✓ Directory structure verified")
        
        # Step 3: Load and verify configurations
        print("\n3. Loading and verifying configurations...")
        try:
            # List all YAML files to verify
            yaml_files = [
                'config/test.yaml',
                'rules/alerts.yml',
                'prometheus.yml',
                'grafana/provisioning/datasources/prometheus.yml',
                'grafana/provisioning/dashboards/default.yml'
            ]
            
            verification_failed = False
            for yaml_file in yaml_files:
                if not verify_yaml_file(yaml_file):
                    verification_failed = True
            
            if verification_failed:
                print("\n✗ YAML verification failed")
                return 1
                
            print("\n✓ All YAML files verified successfully")
            
        except Exception as e:
            print(f"\n✗ Error during verification: {e}")
            print("\nStacktrace:")
            print(traceback.format_exc())
            return 1
        
        # Step 4: Generate verification report
        print("\n4. Generating verification report...")
        try:
            report_dir = Path('reports')
            report_dir.mkdir(exist_ok=True)
            report_path = report_dir / 'yaml_verification_report.md'
            
            with open(report_path, 'w') as f:
                f.write("# YAML Configuration Verification Report\n\n")
                f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("## Verified Files\n\n")
                for yaml_file in yaml_files:
                    f.write(f"- {yaml_file}\n")
            
            print(f"✓ Report generated: {report_path}")
            
        except Exception as e:
            print(f"✗ Failed to generate report: {e}")
            return 1
        
        print("\n=== Verification Complete ===")
        print("\n✅ All checks passed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Unexpected error during verification: {e}")
        print("\nStacktrace:")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
