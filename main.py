import os
import sys
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from bot.main import main

if __name__ == "__main__":
    asyncio.run(main())
