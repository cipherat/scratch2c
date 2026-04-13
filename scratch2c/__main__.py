"""Allow running as `python -m scratch2c`."""

import sys
from .cli import main

sys.exit(main())
