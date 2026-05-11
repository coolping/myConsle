#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import threading
import time
import re
import os
from datetime import datetime
from colorama import init, Fore

# =========================================================
# Global Config
# =========================================================

SERIAL_PORT = "COM10"
BAUDRATE = 921600
READ_TIMEOUT = 0.1

AUTO_RESET_ENABLE = True

RESET_DELAY_SEC = 1.0
RESET_COMMAND = "reset\r\n"

TRIGGER_KEYWORD = "TX3_STATUS_OFFLINE TO CONNECTED..."
STOP_KEYWORD = "SEND...(3/5)"

HEX_OUTPUT_ENABLE = False
ASCII_OUTPUT_ENABLE = True

LOG_ENABLE = True
LOG_FOLDER = "logs"

ANSI_ESCAPE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

# =========================================================
# Runtime State
# =========================================================

loop_count = 0
running = True
trigger_pending = False

log_file = None

# =========================================================
# ANSI Color Helper
# =========================================================

init(autoreset=True)

def log_info(msg):
    print(Fore.CYAN + "[INFO] " + msg)

def log_ok(msg):
    print(Fore.GREEN + "[ OK ] " + msg)

def log_warn(msg):
    print(Fore.YELLOW + "[WARN] " + msg)

def log_err(msg):
    print(Fore.RED + "[ERR ] " + msg)

def log_hex(msg):
    print(Fore.MAGENTA + msg)

# =========================================================
# Utils
# =========================================================

def bytes_to_hex(data):
    return ' '.join(f'{b:02X}' for b in data)

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def write_log(text):
    global log_file

    if LOG_ENABLE and log_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_file.write(f"[{timestamp}] {text}\n")
        log_file.flush()

# =========================================================
# Serial RX Thread
# =========================================================

def serial_rx_worker(ser):
    global running
    global loop_count
    global trigger_pending
    global AUTO_RESET_ENABLE

    line_buffer = b""

    while running:
        try:
            data = ser.read(1024)

            if data:

                if HEX_OUTPUT_ENABLE:
                    hex_msg = "[HEX] " + bytes_to_hex(data)
                    log_hex(hex_msg)
                    write_log(hex_msg)

                line_buffer += data

                while b'\n' in line_buffer:
                    line, line_buffer = line_buffer.split(b'\n', 1)

                    try:
                        raw_text = line.decode(errors='ignore').strip()
                        text = ANSI_ESCAPE.sub('', raw_text)

                    except:
                        raw_text = ""
                        text = ""

                    if ASCII_OUTPUT_ENABLE and raw_text:
                        print("[RX ] " + raw_text)
                        write_log("[RX ] " + text)

                    if STOP_KEYWORD in text:
                        log_warn("STOP KEYWORD DETECTED")
                        log_warn("AUTO RESET DISABLED")
                        write_log("[EVENT] AUTO RESET DISABLED")

                        AUTO_RESET_ENABLE = False

                    if TRIGGER_KEYWORD in text:
                        log_ok("TRIGGER DETECTED")
                        write_log("[EVENT] TRIGGER DETECTED")

                        if AUTO_RESET_ENABLE:
                            trigger_pending = True

        except Exception as e:
            log_err(f"RX Exception: {e}")
            write_log(f"[ERROR] RX Exception: {e}")
            running = False

# =========================================================
# Reset Thread
# =========================================================

def reset_worker(ser):
    global running
    global loop_count
    global trigger_pending

    while running:

        if trigger_pending:
            trigger_pending = False

            log_warn(f"Wait {RESET_DELAY_SEC} sec before reset...")
            write_log(f"[EVENT] Wait {RESET_DELAY_SEC} sec before reset")

            time.sleep(RESET_DELAY_SEC)

            try:
                ser.write(RESET_COMMAND.encode())

                loop_count += 1

                log_ok(f"RESET SENT -> Loop Count = {loop_count}")
                write_log(f"[TX ] {RESET_COMMAND.strip()}")

            except Exception as e:
                log_err(f"TX Exception: {e}")
                write_log(f"[ERROR] TX Exception: {e}")
                running = False

        time.sleep(0.05)

# =========================================================
# CLI Thread
# =========================================================

def cli_worker(ser):
    global running
    global loop_count
    global AUTO_RESET_ENABLE

    help_text = """
Commands:
------------------------------------------------
help            : show help
status          : show current status
reset           : send reset command
pause           : disable auto reset
resume          : enable auto reset
count           : show loop count
clear           : clear screen
quit            : exit
send <text>     : send custom text
------------------------------------------------
"""

    print(help_text)

    while running:
        try:
            cmd = input(Fore.BLUE + "CLI> ").strip()

            if cmd == "help":
                print(help_text)

            elif cmd == "status":
                print(f"""
Running      : {running}
Loop Count   : {loop_count}
Port         : {SERIAL_PORT}
Baudrate     : {BAUDRATE}
Auto Reset   : {AUTO_RESET_ENABLE}
Log Enable   : {LOG_ENABLE}
""")

            elif cmd == "count":
                print(f"Loop Count = {loop_count}")

            elif cmd == "reset":
                ser.write(RESET_COMMAND.encode())
                log_ok("Manual RESET sent")
                write_log("[TX ] Manual RESET")

            elif cmd == "pause":
                AUTO_RESET_ENABLE = False
                log_warn("AUTO RESET DISABLED")
                write_log("[EVENT] AUTO RESET DISABLED")

            elif cmd == "resume":
                AUTO_RESET_ENABLE = True
                log_ok("AUTO RESET ENABLED")
                write_log("[EVENT] AUTO RESET ENABLED")

            elif cmd == "clear":
                clear_screen()

            elif cmd.startswith("send "):
                text = cmd[5:]
                ser.write((text + "\r\n").encode())
                log_ok(f"SEND -> {text}\r\n")
                write_log(f"[TX ] {text}")

            elif cmd == "quit":
                log_warn("Exit requested")
                write_log("[EVENT] Program Exit Requested")
                running = False
                break

            else:
                log_warn("Unknown command")

        except EOFError:
            running = False
            break

        except Exception as e:
            log_err(f"CLI Exception: {e}")
            write_log(f"[ERROR] CLI Exception: {e}")

# =========================================================
# Main
# =========================================================

def main():
    global running
    global log_file

    clear_screen()

    if LOG_ENABLE:
        os.makedirs(LOG_FOLDER, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{LOG_FOLDER}/serial_log_{timestamp}.txt"

        log_file = open(log_filename, "w", encoding="utf-8")

        print(f"[LOG ] Save Log -> {log_filename}")

    log_info(f"Open Serial Port: {SERIAL_PORT}")

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            timeout=READ_TIMEOUT
        )

    except Exception as e:
        log_err(f"Cannot open serial: {e}")
        return

    log_ok("Serial Open Success")

    rx_thread = threading.Thread(
        target=serial_rx_worker,
        args=(ser,),
        daemon=True
    )

    reset_thread = threading.Thread(
        target=reset_worker,
        args=(ser,),
        daemon=True
    )

    cli_thread = threading.Thread(
        target=cli_worker,
        args=(ser,),
        daemon=True
    )

    rx_thread.start()
    reset_thread.start()
    cli_thread.start()

    try:
        while running:
            time.sleep(0.2)

    except KeyboardInterrupt:
        log_warn("KeyboardInterrupt")

    running = False

    try:
        ser.close()
    except:
        pass

    if log_file:
        log_file.close()

    log_warn("Program Exit")

if __name__ == "__main__":
    main()
