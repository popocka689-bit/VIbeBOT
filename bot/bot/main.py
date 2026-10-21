import os
import sys
import asyncio

# Ensure parent bot directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import main

if __name__ == "__main__":
    asyncio.run(main())
