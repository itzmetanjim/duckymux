#!/usr/bin/env python3
import time
count = 0
print("^C to stop")
try:
    while True:
        count += 1
        print(f"{count}")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nstop")
