#!/usr/bin/env python3
import sys
import time
import os
print("specs")
print(f"running python version {sys.version}")
print(f"on {sys.platform}")
print(f"cwd {os.getcwd()}")
print(f"pid {os.getpid()}")
print("\nexiting in 5seconds")
time.sleep(5)

