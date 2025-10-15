# Duckymux
![Screenshot of Duckymux](image.png)
Duckymux is a tool for the Raspberry Pi Pico (or anything based off of RP2040/2350/ any micropython supported thing) to manage multiple scripts.

## Features
- Full mouse cursor support
  - Click to select, click button to do action
  - Double click to open
  - Right click to run in background without opening
  - `exec` button closes DuckyMux (and all other apps) then runs the app selected.
- Keyboard support (you dont need mouse)
- Run multiple apps at the same time.
- Or, run any one app with full access. (`exec` or `shift+R` )
- Open virtual terminals/serial consoles (`open` or `o`)

## Shortcuts
These only work on the main screen (not on virtual terminals opened with `o`/`open`/doubleclick)
- `h` Show/hide help
- `q` Quit to the REPL, stopping all processes.
- arrows or `j`/`k` (vim-style)/ click: move
- `r`/`start` button/ right click: start an app in the background
- `s`/`stop` button: force-stop an app
- `o`/`open` button/ double click: open a virtual terminal to the app(and start the app if not already started)
Use `^D^X` to exit or `^D^D` to send `^D` in a virtual terminal.
- `shift+R` or `exec` button: run in foreground, instantly killing Duckymux and all other apps. This may help if an app is not working with Duckymux as it gives full permissions to that app.
