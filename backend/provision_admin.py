"""
Inkloom AI — CLI Provisioning Tool for First Organization Administrator (Milestone 5E)
Usage:
  python provision_admin.py --org-name "Apex Global" --org-slug "apex" --admin-email "admin@apex.corp" --admin-name "Apex Admin"
"""
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.cli.provision_admin import main

if __name__ == "__main__":
    main()
