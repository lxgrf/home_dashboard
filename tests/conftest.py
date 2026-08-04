import os
import sys

# The app modules import each other flat, as they do inside the container.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
