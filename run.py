#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import threading
import time
import sys
from colorama import init, Fore, Style
import re

# =========================================================
# Global Config
# =========================================================
ANSI_ESCAPE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
SERIAL_PORT = "COM10"
BAUDRATE = 921600
READ_TIMEOUT = 0.1

AUTO_RESET_ENABLE = True

RESET_DELAY_SEC = 1.0
RESET_COMMAND = "reset\r\n"

TRIGGER_KEYWORD = "TX3_STATUS_OFFLINE TO CONNECTED..."
STOP_KEYWORD = "Retrying ...(5/5)"

HEX_OUTPUT_ENABLE = False
ASCII_OUTPUT_ENABLE = True

# =========================================================
# Runtime State
# =========================================================

loop_count = 0
running = True
trigger_pending = False

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
# HEX Display
# =========================================================

def bytes_to_hex(data):
    return ' '.join(f'{b:02X}' for b in data)

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
                # HEX Output
                if HEX_OUTPUT_ENABLE:
                    log_hex("[HEX] " + bytes_to_hex(data))

                line_buffer += data

                while b'\n' in line_buffer:
                    line, line_buffer = line_buffer.split(b'\n', 1)

                    try:
                        raw_text = line.decode(errors='ignore').strip()

                        # Remove ANSI Escape Codes
                        text = ANSI_ESCAPE.sub('', raw_text)

                    except:
                        raw_text = ""
                        text = ""

                    # 顯示原始內容（保留ANSI色彩）
                    if ASCII_OUTPUT_ENABLE and raw_text:
                        print("[RX ] " + raw_text)

                    # keyword matching 使用 clean text
                    if STOP_KEYWORD in text:
                        log_warn("STOP KEYWORD DETECTED")
                        log_warn("AUTO RESET DISABLED")

                        AUTO_RESET_ENABLE = False

                    if TRIGGER_KEYWORD in text:
                        log_ok("TRIGGER DETECTED")

                        if AUTO_RESET_ENABLE:
                            trigger_pending = True

        except Exception as e:
            log_err(f"RX Exception: {e}")
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
            time.sleep(RESET_DELAY_SEC)

            try:
                ser.write(RESET_COMMAND.encode())

                loop_count += 1

                log_ok(
                    f"RESET SENT -> Loop Count = {loop_count}"
                )

            except Exception as e:
                log_err(f"TX Exception: {e}")
                running = False

        time.sleep(0.05)

# =========================================================
# CLI Thread
# =========================================================

def cli_worker(ser):
    global running
    global loop_count

    help_text = f"""
Commands:
------------------------------------------------
help            : show help
status          : show current status
reset           : send reset command
count           : show loop count
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
""")

            elif cmd == "count":
                print(f"Loop Count = {loop_count}")

            elif cmd == "reset":
                ser.write(RESET_COMMAND.encode())
                log_ok("Manual RESET sent")

            elif cmd.startswith("send "):
                text = cmd[5:]
                ser.write(text.encode())
                log_ok(f"SEND -> {text}")

            elif cmd == "quit":
                log_warn("Exit requested")
                running = False
                break
            elif cmd == "resume":
                AUTO_RESET_ENABLE = True
                log_ok("AUTO RESET ENABLED")
            elif cmd == "pause":
                AUTO_RESET_ENABLE = False
                log_warn("AUTO RESET DISABLED")
            else:
                log_warn("Unknown command")

        except EOFError:
            running = False
            break

        except Exception as e:
            log_err(f"CLI Exception: {e}")

# =========================================================
# Main
# =========================================================

def main():
    global running

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

    log_warn("Program Exit")


if __name__ == "__main__":
    main()
