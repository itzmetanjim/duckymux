import curses
import os
import logging
import subprocess
import signal
import time
import sys
import tty
import termios
import select
import pty
import fcntl
BSTATE_SCROLLUP=65536
BSTATE_SCROLLDOWN=2097152
BSTATE_CLICK = 4
BSTATE_RCLICK = 4096 # right click
BSTATE_DBLCLICK = 8
current_index=0
current_scroll=0
logging.basicConfig(filename='duckymux.log', level=logging.DEBUG)
header ="Duckymux 0.0.1 q:quit h:help"
helptext = """
Duckymux - manage multiple RPI Pico scripts
h: show this help or exit this help
arrows or j/k or click: move up/down
r or right click: run current app in background
o or double click: open the serial monitor for current app
shift+r: run app in foreground, exiting Duckymux and all other apps
restart your Pico to return to duckymux
use ^D^X to return to duckymux; use ^D^D to send ^D
s: force stop current app
q: quit"""
use_colors=False
def print_app_list(apps,states,stdscr):
    global current_index
    global current_scroll
    global use_colors
    global header
    max_y, max_x = stdscr.getmaxyx()
    ststr=["RUNNING" if s else "       " for s in states]
    app_list = []
    
    # Calculate visible range
    visible_count = max_y - 1  # subtract 1 for header
    if current_index < current_scroll:
        current_scroll = current_index
    if current_index >= current_scroll + visible_count:
        current_scroll = current_index - visible_count + 1
    
    for i in range(current_scroll, min(current_scroll + visible_count, len(apps))):
        if i == current_index:
            app_list.append(addpad(f"> {apps[i]} {ststr[i]}", max_x))
        else:
            app_list.append(addpad(f"  {apps[i]} {ststr[i]}", max_x))
    
    # Draw header
    if use_colors:
        header_line = (header[:max_x]).ljust(max_x)
        stdscr.addstr(0, 0, header_line, curses.color_pair(1))
    else:
        stdscr.addstr(0, 0, header[:max_x])
    
    # Draw app list
    for i, e in enumerate(app_list):
        row = i + 1
        if row < max_y:
            if e.startswith(">"):
                if use_colors:
                    stdscr.addstr(row, 0, e, curses.color_pair(1))
                else:
                    stdscr.addstr(row, 0, e)
            else:
                stdscr.addstr(row, 0, e)
    
    # Clear remaining lines
    for row in range(len(app_list) + 1, max_y):
        logging.debug(f'{row=}, 0, [{" " * max_x}] {max_x=}')
        try:
            if row == max_y - 1:
                # Last row: avoid writing to the last cell
                stdscr.addstr(row, 0, " " * (max_x - 1))
            else:
                stdscr.addstr(row, 0, " " * max_x)
        except curses.error:
            # Ignore errors when writing to screen boundaries
            pass
    
    stdscr.refresh()

def handle_click(mx,my,bstate,apps,stdscr):
    global current_index
    global current_scroll
    max_y, max_x = stdscr.getmaxyx()
    
    # Handle scroll wheel
    if bstate & BSTATE_SCROLLUP:
        if current_index > 0:
            current_index -= 1
        return None
    elif bstate & BSTATE_SCROLLDOWN:
        if current_index < len(apps) - 1:
            current_index += 1
        return None
    
    # Handle clicks in app area (row 1 and below)
    if my >= 1:
        clicked_index = current_scroll + (my - 1)
        if clicked_index < len(apps):
            current_index = clicked_index
            
            # Right click - run in background
            if bstate & BSTATE_RCLICK:
                return 'run_bg'
            # Double click - open serial monitor
            elif bstate & BSTATE_DBLCLICK:
                return 'monitor'
            # Single click - just select
            elif bstate & BSTATE_CLICK:
                return None
    
    return None  

def addpad(s, width):
    """Pad or truncate string s to exactly width characters."""
    return s[:width].ljust(width)

def run_app_background(app_path):
    """Run an app in background using subprocess with pty. Returns (process, master_fd, output_buffer)."""
    try:
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Make master_fd non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Start process with pty as stdout/stderr
        proc = subprocess.Popen(
            ['python3', app_path],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True
        )
        
        # Close slave_fd in parent process (child has its own copy)
        os.close(slave_fd)
        
        return (proc, master_fd, bytearray())  # proc, master_fd, output_buffer
    except Exception as e:
        logging.error(f"Error starting app: {e}")
        return None

def run_app_foreground(app_path):
    """Run app in foreground, replacing current process."""
    os.execvp('python3', ['python3', app_path])

def open_serial_monitor(stdscr, app_path, proc_tuple):
    """Open serial monitor mode for an app - works like 'screen'."""
    if proc_tuple is None:
        return None
    
    proc, master_fd, output_buffer = proc_tuple
    
    # Completely exit curses mode
    curses.endwin()
    
    # Save terminal settings
    stdin_fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin_fd)
    
    try:
        # Set terminal to raw mode
        tty.setraw(stdin_fd)
        
        # First, display all buffered output that hasn't been shown yet
        if output_buffer:
            sys.stdout.buffer.write(output_buffer)
            sys.stdout.buffer.flush()
            # Clear the buffer after displaying
            output_buffer.clear()
        
        ctrl_d_pressed = False
        
        while proc.poll() is None:
            # Use select to wait for input or output
            readable, _, _ = select.select([sys.stdin, master_fd], [], [], 0.1)
            
            # Check if app output is available
            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        # Write output directly to terminal
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                except OSError:
                    # master_fd closed or no data
                    pass
            
            # Check if user input is available
            if sys.stdin in readable:
                try:
                    char = sys.stdin.read(1)
                    
                    if char == '\x04':  # Ctrl+D
                        if ctrl_d_pressed:
                            # Second Ctrl+D: send it to the app
                            try:
                                os.write(master_fd, b'\x04')
                            except:
                                pass
                            ctrl_d_pressed = False
                        else:
                            # First Ctrl+D: remember it
                            ctrl_d_pressed = True
                    elif char == '\x18' and ctrl_d_pressed:  # Ctrl+X after Ctrl+D
                        # Exit serial monitor
                        break
                    else:
                        # Any other key: reset Ctrl+D state and forward to app
                        ctrl_d_pressed = False
                        try:
                            os.write(master_fd, char.encode('utf-8', errors='ignore'))
                        except:
                            # Process might have closed stdin
                            break
                except:
                    break
        
        # Process ended or user exited
        if proc.poll() is not None:
            # Process ended naturally - read any remaining output
            try:
                while True:
                    data = os.read(master_fd, 4096)
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    else:
                        break
            except:
                pass
            print("\n[Process exited]")
            time.sleep(1)
    
    finally:
        # Restore terminal settings
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
    
    return proc_tuple

def show_help(stdscr):
    """Display help text."""
    global helptext
    stdscr.clear()
    lines = helptext.strip().split('\n')
    for i, line in enumerate(lines):
        try:
            stdscr.addstr(i, 0, line)
        except:
            pass
    stdscr.refresh()
    
    # Wait for 'h' or 'q' to exit
    while True:
        key = stdscr.getch()
        if key == ord('h') or key == ord('q'):
            break
    stdscr.clear()

def main(stdscr):
    global header
    global use_colors
    global current_index
    global current_scroll
    
    # Enter cbreak mode and hide cursor if supported
    curses.cbreak()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()

    # Initialize colors and ensure terminal supports them
    use_colors = False
    if not curses.has_colors():
        stdscr.addstr(0, 0, "WARN: Terminal does not support colors. Press any key to continue.")
        stdscr.refresh()
        stdscr.getch()
    else:
        curses.start_color()
        try:
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
            use_colors = True
        except curses.error:
            use_colors = False

    # Enable mouse events and keypad mode
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    stdscr.keypad(True)

    # Initialize app list and state tracking
    apps = sorted([f for f in os.listdir("apps") if f.endswith('.py')])
    if not apps:
        stdscr.addstr(0, 0, "No apps found in 'apps' directory. Press any key to exit.")
        stdscr.refresh()
        stdscr.getch()
        return
    
    processes = {}  # app_name -> (process, master_fd, output_buffer)
    states = [False] * len(apps)  # running state for each app
    current_index = 0
    current_scroll = 0
    
    # Initial render
    print_app_list(apps, states, stdscr)
    stdscr.timeout(100)  # 100ms timeout for non-blocking getch

    while True:
        # Update running states and collect background output
        for i, app in enumerate(apps):
            if app in processes:
                proc_tuple = processes[app]
                proc, master_fd, output_buffer = proc_tuple
                
                if proc.poll() is not None:
                    # Process has ended
                    try:
                        os.close(master_fd)
                    except:
                        pass
                    del processes[app]
                    states[i] = False
                else:
                    states[i] = True
                    # Collect output from background apps (buffer it, don't display)
                    try:
                        while True:
                            data = os.read(master_fd, 4096)
                            if data:
                                output_buffer.extend(data)
                            else:
                                break
                    except (OSError, BlockingIOError):
                        # No data available (non-blocking read)
                        pass
            else:
                states[i] = False
        
        # Refresh display
        print_app_list(apps, states, stdscr)
        
        key = stdscr.getch()
        if key == -1:
            # Timeout, continue loop
            continue
        
        if key == ord('q'):
            # Kill all running processes
            for proc_tuple in processes.values():
                proc, master_fd, _ = proc_tuple
                try:
                    proc.terminate()
                    os.close(master_fd)
                except:
                    pass
            break
        
        elif key == ord('h'):
            show_help(stdscr)
            print_app_list(apps, states, stdscr)
        
        elif key == curses.KEY_UP or key == ord('k'):
            if current_index > 0:
                current_index -= 1
        
        elif key == curses.KEY_DOWN or key == ord('j'):
            if current_index < len(apps) - 1:
                current_index += 1
        
        elif key == ord('r'):
            # Run current app in background
            app_path = os.path.join("apps", apps[current_index])
            proc_tuple = run_app_background(app_path)
            if proc_tuple:
                processes[apps[current_index]] = proc_tuple
                states[current_index] = True
        
        elif key == ord('R'):
            # Run app in foreground (exec - will not return)
            # Kill all other apps first
            for proc_tuple in processes.values():
                proc, master_fd, _ = proc_tuple
                try:
                    proc.terminate()
                    os.close(master_fd)
                except:
                    pass
            app_path = os.path.join("apps", apps[current_index])
            curses.endwin()
            run_app_foreground(app_path)
        
        elif key == ord('o'):
            # Open serial monitor
            app_name = apps[current_index]
            app_path = os.path.join("apps", app_name)
            
            # Start app if not running
            if app_name not in processes:
                proc_tuple = run_app_background(app_path)
                if proc_tuple:
                    processes[app_name] = proc_tuple
                    states[current_index] = True
            else:
                proc_tuple = processes[app_name]
            
            proc_tuple = open_serial_monitor(stdscr, app_path, proc_tuple)
            
            # Update process tracking after exiting monitor
            if proc_tuple:
                proc, master_fd, _ = proc_tuple
                if proc.poll() is None:
                    processes[app_name] = proc_tuple
                    states[current_index] = True
                else:
                    try:
                        os.close(master_fd)
                    except:
                        pass
                    if app_name in processes:
                        del processes[app_name]
                    states[current_index] = False
            
            # Reinitialize curses after returning from serial monitor
            stdscr.clear()
            stdscr.refresh()
            print_app_list(apps, states, stdscr)
        
        elif key == ord('s'):
            # Stop current app
            app_name = apps[current_index]
            if app_name in processes:
                proc, master_fd, _ = processes[app_name]
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
                try:
                    os.close(master_fd)
                except:
                    pass
                del processes[app_name]
                states[current_index] = False
        
        elif key == curses.KEY_MOUSE:
            try:
                id, mx, my, mz, bstate = curses.getmouse()
            except curses.error:
                continue
            
            action = handle_click(mx, my, bstate, apps, stdscr)
            if action == 'run_bg':
                app_path = os.path.join("apps", apps[current_index])
                proc_tuple = run_app_background(app_path)
                if proc_tuple:
                    processes[apps[current_index]] = proc_tuple
                    states[current_index] = True
            elif action == 'monitor':
                app_name = apps[current_index]
                app_path = os.path.join("apps", app_name)
                if app_name not in processes:
                    proc_tuple = run_app_background(app_path)
                    if proc_tuple:
                        processes[app_name] = proc_tuple
                        states[current_index] = True
                else:
                    proc_tuple = processes[app_name]
                proc_tuple = open_serial_monitor(stdscr, app_path, proc_tuple)
                
                # Update process tracking after exiting monitor
                if proc_tuple:
                    proc, master_fd, _ = proc_tuple
                    if proc.poll() is None:
                        processes[app_name] = proc_tuple
                        states[current_index] = True
                    else:
                        try:
                            os.close(master_fd)
                        except:
                            pass
                        if app_name in processes:
                            del processes[app_name]
                        states[current_index] = False
                
                # Reinitialize curses after returning from serial monitor
                stdscr.clear()
                stdscr.refresh()
                print_app_list(apps, states, stdscr)

curses.wrapper(main)
