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

h: show this help or exit help

arrows or j/k or click: move up/down

r or right click:  run current app in background

o or double click: open the serial monitor for current app
                   use ^D^X to return to duckymux; use ^D^D to send ^D

shift+r:           run app in foreground, exiting Duckymux and all other apps
                   with this, restart your Pico to return to duckymux
                   only one app can be run this way

s: force stop current app
q: quit

=== PRESS q OR h TO RETURN TO DUCKYMUX ==="""
use_colors=False
def print_app_list(apps,states,stdscr):
    global current_index
    global current_scroll
    global use_colors
    global header
    max_y, max_x = stdscr.getmaxyx()
    ststr=["RUNNING" if s else "       " for s in states]
    
    # Calculate visible range
    visible_count = max_y - 1  # subtract 1 for header
    
    # Ensure current_scroll is within valid bounds
    max_scroll = max(0, len(apps) - visible_count)
    current_scroll = max(0, min(current_scroll, max_scroll))
    
    # Adjust scroll to keep current_index visible
    if current_index < current_scroll:
        current_scroll = current_index
    if current_index >= current_scroll + visible_count:
        current_scroll = current_index - visible_count + 1
    
    # Build visible app list with buttons
    app_list = []
    for i in range(current_scroll, min(current_scroll + visible_count, len(apps))):
        prefix = "> " if i == current_index else "  "
        app_name = apps[i]
        status = ststr[i]
        
        # Determine which button to show (start or stop)
        action_btn = "stop " if states[i] else "start"
        buttons = f"{action_btn} open exec"
        
        # Calculate space: prefix(2) + app_name + space(1) + status(7) + space(1) + buttons(~20)
        # Minimum space needed for buttons is about 25 characters
        base_len = len(prefix) + len(app_name) + 1 + len(status)
        buttons_len = len(buttons) + 1  # +1 for space before buttons
        
        if base_len + buttons_len + 3 <= max_x:  # +3 for padding
            # Enough space for buttons
            # Calculate padding to right-align buttons
            padding_len = max_x - base_len - buttons_len - 1
            line = f"{prefix}{app_name} {status}" + " " * padding_len + buttons
        else:
            # Not enough space, truncate app name if needed
            available_for_name = max_x - len(prefix) - 1 - len(status) - 1
            if len(app_name) > available_for_name:
                app_name = app_name[:available_for_name-3] + "..."
            line = f"{prefix}{app_name} {status}"
        
        app_list.append(line[:max_x].ljust(max_x))
    
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
            try:
                if e.startswith(">"):
                    if use_colors:
                        stdscr.addstr(row, 0, e, curses.color_pair(1))
                    else:
                        stdscr.addstr(row, 0, e)
                else:
                    stdscr.addstr(row, 0, e)
            except curses.error:
                # Ignore errors when writing to screen boundaries
                pass
    
    # Clear remaining lines
    for row in range(len(app_list) + 1, max_y):
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

def handle_click(mx,my,bstate,apps,states,stdscr):
    global current_index
    global current_scroll
    max_y, max_x = stdscr.getmaxyx()
    visible_count = max_y - 1  # subtract 1 for header
    
    # Handle scroll wheel
    if bstate & BSTATE_SCROLLUP:
        if current_index > 0:
            current_index -= 1
            # Scroll viewport if needed to keep selection visible
            if current_index < current_scroll:
                current_scroll = current_index
        return None
    elif bstate & BSTATE_SCROLLDOWN:
        if current_index < len(apps) - 1:
            current_index += 1
            # Scroll viewport if needed to keep selection visible
            if current_index >= current_scroll + visible_count:
                current_scroll = current_index - visible_count + 1
        return None
    
    # Handle clicks in app area (row 1 and below)
    if my >= 1:
        clicked_index = current_scroll + (my - 1)
        if clicked_index < len(apps):
            # Calculate button positions for this line
            app_name = apps[clicked_index]
            status = "RUNNING" if states[clicked_index] else "       "
            action_btn = "stop " if states[clicked_index] else "start"
            
            # Calculate where buttons would be
            base_len = 2 + len(app_name) + 1 + len(status)
            buttons = f"{action_btn} open exec"
            buttons_len = len(buttons) + 1
            
            if base_len + buttons_len + 3 <= max_x:
                # Buttons are present
                padding_len = max_x - base_len - buttons_len - 1
                buttons_start = base_len + padding_len
                
                # Check if click is on a button
                if mx >= buttons_start:
                    # Calculate which button was clicked
                    relative_x = mx - buttons_start
                    
                    # Button positions: "start/stop open exec"
                    # start: 0-4, stop: 0-3
                    # open: after start/stop + 1 space
                    # exec: after open + 1 space
                    
                    action_len = len(action_btn)
                    open_start = action_len + 1
                    exec_start = open_start + 5  # "open " is 5 chars
                    
                    if relative_x < action_len:
                        # Clicked on start/stop
                        current_index = clicked_index
                        return 'toggle_run'
                    elif relative_x >= open_start and relative_x < exec_start - 1:
                        # Clicked on open
                        current_index = clicked_index
                        return 'monitor'
                    elif relative_x >= exec_start:
                        # Clicked on exec
                        current_index = clicked_index
                        return 'exec_fg'
                    else:
                        # Clicked on space between buttons
                        current_index = clicked_index
                        return None
                else:
                    # Clicked on app name/status area
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
            else:
                # No buttons present, just select
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
    """Display help text with scrolling support."""
    global helptext
    lines = helptext.strip().split('\n')
    max_y, max_x = stdscr.getmaxyx()
    scroll_pos = 0
    
    # Enable mouse for help screen
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    
    while True:
        stdscr.clear()
        
        # Calculate visible range
        visible_count = max_y
        max_scroll = max(0, len(lines) - visible_count)
        scroll_pos = max(0, min(scroll_pos, max_scroll))
        
        # Display visible lines
        for i in range(visible_count):
            line_idx = scroll_pos + i
            if line_idx < len(lines):
                try:
                    stdscr.addstr(i, 0, lines[line_idx][:max_x])
                except curses.error:
                    pass
        
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('h') or key == ord('q'):
            break
        elif key == curses.KEY_UP or key == ord('k'):
            if scroll_pos > 0:
                scroll_pos -= 1
        elif key == curses.KEY_DOWN or key == ord('j'):
            if scroll_pos < max_scroll:
                scroll_pos += 1
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, mz, bstate = curses.getmouse()
                if bstate & BSTATE_SCROLLUP:
                    if scroll_pos > 0:
                        scroll_pos -= 1
                elif bstate & BSTATE_SCROLLDOWN:
                    if scroll_pos < max_scroll:
                        scroll_pos += 1
            except curses.error:
                pass
    
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
                # Scroll viewport if needed
                max_y = stdscr.getmaxyx()[0]
                visible_count = max_y - 1
                if current_index < current_scroll:
                    current_scroll = current_index
        
        elif key == curses.KEY_DOWN or key == ord('j'):
            if current_index < len(apps) - 1:
                current_index += 1
                # Scroll viewport if needed
                max_y = stdscr.getmaxyx()[0]
                visible_count = max_y - 1
                if current_index >= current_scroll + visible_count:
                    current_scroll = current_index - visible_count + 1
        
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
            
            action = handle_click(mx, my, bstate, apps, states, stdscr)
            if action == 'toggle_run':
                # Start or stop based on current state
                app_name = apps[current_index]
                app_path = os.path.join("apps", app_name)
                
                if states[current_index]:
                    # Stop the app
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
                else:
                    # Start the app
                    proc_tuple = run_app_background(app_path)
                    if proc_tuple:
                        processes[app_name] = proc_tuple
                        states[current_index] = True
            
            elif action == 'run_bg':
                app_path = os.path.join("apps", apps[current_index])
                proc_tuple = run_app_background(app_path)
                if proc_tuple:
                    processes[apps[current_index]] = proc_tuple
                    states[current_index] = True
            
            elif action == 'exec_fg':
                # Run app in foreground (exec - will not return)
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
