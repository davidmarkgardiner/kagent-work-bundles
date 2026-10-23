#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
from audit_tools import main
sys.argv.insert(1, 'validate-run')
sys.exit(main())
