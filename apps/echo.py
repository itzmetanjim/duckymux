#!/usr/bin/env python3
print("^D/^Z to stop")
try:
    while True:
        line = input(">")
        print(f"{line}")
except EOFError:
    print("\nstop")
