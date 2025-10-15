#!/usr/bin/env python3
import curses
import json
import base64
import hmac
import struct
import sys
import time
import json
import colorama


def hotp(key, counter, digits=6, digest='sha1'):
    key = base64.b32decode(key.upper() + '=' * ((8 - len(key)) % 8))
    counter = struct.pack('>Q', counter)
    mac = hmac.new(key, counter, digest).digest()
    offset = mac[-1] & 0x0f
    binary = struct.unpack('>L', mac[offset:offset+4])[0] & 0x7fffffff
    return str(binary)[-digits:].zfill(digits)


def totp(key, time_step=30, digits=6, digest='sha1'):
    return hotp(key, int(time.time() / time_step), digits, digest)

def addpad(s, width):
    """Pad or truncate string s to exactly width characters."""
    return s[:width].ljust(width)
def main():
    try:
        with open('totp.json') as f:
            data = json.load(f)
    except Exception as e:
        example = {
            "keys": [
                {
                    "name": "example key 1",
                    "secret": "JBSWY3DPEHPK3PXP",
                    "time_step": 30,
                    "digits": 6,
                    "digest": "sha1"
                },
                {
                    "name": "very fast key",
                    "secret": "JBSWY3DPEHPK3PXW",
                    "time_step": 1, # for testing
                    "digits": 6,
                    "digest": "sha1"
                },
                {
                    "name": "example 10 digit key",
                    "secret": "JBSWY3DPEHPK3PWX",
                    "time_step": 30,
                    "digits": 10,
                    "digest": "sha1"
                },
                {
                    "name": "example sha256 key",
                    "secret": "JBSWY3DPEHPK3PXQ",
                    "time_step": 30,
                    "digits": 6,
                    "digest": "sha256"
                },
                {
                    "name": "fast key",
                    "secret": "JBSWY3DPEHPK3PXQ",
                    "time_step": 5,
                    "digits": 6,
                    "digest": "sha256"
                },

            ]
        }
        with open('totp.json', 'w') as f:
            json.dump(example, f, indent=4)
        data=example
    """commented, will replace with curses implementation now
    try:
        while True:
            print(colorama.Cursor.POS(1,1), end='')
            print(colorama.ansi.clear_screen(), end='')
            print("\n\nTOTP codes ^C to exit\n")
            for key in data['keys']:
                print(key['name'], ":", totp(key['secret'], key.get('time_step', 30), key.get('digits', 6), key.get('digest', 'sha1')))
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
    """
    
    def wrapperythingy(stdscr):
        curses.curs_set(0)
        width = stdscr.getmaxyx()[1]
        try:
            while True:
                stdscr.clear()
                stdscr.addstr(0, 0, addpad("Ducky TOTP -  ^C to exit",width)+"\n\n",curses.A_REVERSE)
                for key in data['keys']:
                    stdscr.addstr(key['name'], curses.A_BOLD)
                    stdscr.addstr(": " + totp(key['secret'], key.get('time_step', 30), key.get('digits', 6), key.get('digest', 'sha1')) + "\n")
                stdscr.refresh()
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            stdscr.addstr(0, 0, "Error: " + str(e) + "\n")
            stdscr.refresh()
            stdscr.getch()
            sys.exit(1)
    curses.wrapper(wrapperythingy)

    """commented
    args = [int(x) if x.isdigit() else x for x in sys.argv[1:]]
    for key in sys.stdin:
        print(totp(key.strip(), *args))
    """


if __name__ == '__main__':
    main()