import sys
import os

# Add the project root directory to the Python path
# This allows tests in the 'tests/' directory to import modules from 'lib/'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# You can also define project-wide fixtures here if needed in the future
