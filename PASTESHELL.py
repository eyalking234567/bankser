
import tkinter as tk
import subprocess
import threading
import concurrent.futures
import ipaddress
import socket
import re
import queue

# ==========================================
# PASTESHELL CONFIG
# ==========================================

root = tk.Tk()
root.title("PASTESHELL v2.0")
root.geometry("850x700")
root.configure(bg="#050505")
root.resizable(False, False)

skull_color = "#00ff66"
animation_index = 0

terminal_window = None
terminal_output = None
terminal_entry = None

scan_queue = queue.Queue()
scan_running = False

COLORS = {
    1: "#00ff66",
    2: "#00ccff",
    3: "#ff0000",
    4: "#bb00ff",
    5: "#ffff00",
    6: "#ffffff",
    7: "#ff8800",
    8: "#ff69b4"
}

# ==========================================
# ASCII SKULL
# ==========================================

frames = [
r'''
       .-""""-.
      /  .--.  \
     |  /    \  |
     | | O  O | |
     | |  /\  | |
     |  \_==_/  |
      \  ____  /
       /| || |\
      /_|_||_|_\
        /  \
       /____\
''',

r'''
          .---.
        .'     `.
       /  O   O  \
      |     ^     |
      |   .---.   |
       \  `---'  /
        `._____.'
          | | |
         _|_|_|_
        /_______\
''',

r'''
       .-""""-.
      /  .--.  \
     |  /    \  |
     | | 0  0 | |
     | |  /\  | |
     |  \_==_/  |
      \  ____  /
       /| || |\
      /_|_||_|_\
        /  \
       /____\
''',

r'''
          .---.
        .'     `.
       /  o   o  \
      |     ^     |
      |   .---.   |
       \  `---'  /
        `._____.'
          | | |
         _|_|_|_
        /_______\
'''
]

# ==========================================
# TITLE
# ==========================================

title = tk.Label(
    root,
    text="PASTESHELL",
    font=("Impact", 48, "bold"),
    fg=skull_color,
    bg="#050505"
)
title.pack(pady=20)

subtitle = tk.Label(
    root,
    text=">>> SYSTEM INITIALIZED <<<",
    font=("Consolas", 12),
    fg="#777777",
    bg="#050505"
)
subtitle.pack()

# ==========================================
# SKULL DISPLAY
# ==========================================

skull = tk.Label(
    root,
    text="",
    font=("Consolas", 19, "bold"),
    fg=skull_color,
    bg="#050505",
    justify="center"
)
skull.pack(pady=15)


def animate():
    global animation_index

    skull.config(text=frames[animation_index])
    animation_index = (animation_index + 1) % len(frames)

    root.after(250, animate)


# ==========================================
# TERMINAL OUTPUT
# ==========================================

def terminal_print(message):
    if terminal_output is None:
        return

    try:
        if not terminal_output.winfo_exists():
            return

        terminal_output.config(state="normal")
        terminal_output.insert("end", str(message) + "\n")
        terminal_output.see("end")
        terminal_output.config(state="disabled")

    except tk.TclError:
        pass


# ==========================================
# NETWORK SCANNER
# ==========================================

def scan_network_worker():
    global scan_running

    try:
        scan_queue.put("Starting IPSEA scan...")

        output = subprocess.check_output(
            ["ipconfig"],
            encoding="utf-8",
            errors="ignore"
        )

        # Find an IPv4 address and subnet mask
        blocks = re.split(r"\r?\n\r?\n", output)

        network = None

        for block in blocks:
            ip_match = re.search(
                r"IPv4 Address[^\n]*:\s*([\d.]+)",
                block
            )

            mask_match = re.search(
                r"Subnet Mask[^\n]*:\s*([\d.]+)",
                block
            )

            if ip_match and mask_match:
                local_ip = ip_match.group(1)
                subnet_mask = mask_match.group(1)

                try:
                    candidate = ipaddress.ip_network(
                        f"{local_ip}/{subnet_mask}",
                        strict=False
                    )

                    if candidate.num_addresses <= 256:
                        network = candidate
                        break

                except ValueError:
                    continue

        if network is None:
            scan_queue.put(
                "Could not find a suitable local IPv4 network."
            )
            return

        scan_queue.put(f"Network detected: {network}")
        scan_queue.put("Checking devices...")

        def ping_device(ip):
            try:
                subprocess.run(
                    [
                        "ping",
                        "-n", "1",
                        "-w", "300",
                        str(ip)
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
            except (subprocess.SubprocessError, OSError):
                pass

        # Discover devices that respond to ping
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=32
        ) as executor:

            list(executor.map(
                ping_device,
                network.hosts()
            ))

        # Read ARP table
        arp_output = subprocess.check_output(
            ["arp", "-a"],
            encoding="utf-8",
            errors="ignore"
        )

        pattern = (
            r"(\d{1,3}(?:\.\d{1,3}){3})"
            r"\s+([0-9a-fA-F-]{17})"
            r"\s+(dynamic|static)"
        )

        devices = re.findall(
            pattern,
            arp_output,
            re.IGNORECASE
        )

        found = set()

        scan_queue.put("")
        scan_queue.put("=" * 65)
        scan_queue.put(
            "IP ADDRESS       MAC ADDRESS          ENTRY"
        )
        scan_queue.put("=" * 65)

        for ip, mac, entry in devices:

            if ip in found:
                continue

            if ipaddress.ip_address(ip) not in network:
                continue

            found.add(ip)

            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except (socket.herror, socket.gaierror, OSError):
                hostname = "Unknown"

            scan_queue.put(
                f"{ip:<16} {mac:<20} {entry.upper()}"
            )

            scan_queue.put(f"Hostname: {hostname}")
            scan_queue.put("-" * 65)

        scan_queue.put("")
        scan_queue.put(
            f"IPSEA COMPLETE: {len(found)} ARP entries found."
        )

    except Exception as error:
        scan_queue.put(f"IPSEA ERROR: {error}")

    finally:
        scan_queue.put("__SCAN_FINISHED__")


def start_network_scan():
    global scan_running

    if scan_running:
        terminal_print("A scan is already running!")
        return

    scan_running = True

    threading.Thread(
        target=scan_network_worker,
        daemon=True
    ).start()


def process_scan_queue():
    global scan_running

    try:
        while True:
            message = scan_queue.get_nowait()

            if message == "__SCAN_FINISHED__":
                scan_running = False
            else:
                terminal_print(message)

    except queue.Empty:
        pass

    root.after(100, process_scan_queue)


# ==========================================
# COMMAND SYSTEM
# ==========================================

def scan_weak_wifi():
    terminal_print("\n[ WEAKWIFI ] Scanning nearby Wi-Fi...\n")

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        if result.returncode != 0:
            terminal_print("Wi-Fi scan failed. Check your Wi-Fi adapter.")
            return

        networks = {}
        current_ssid = None

        for line in result.stdout.splitlines():

            ssid_match = re.match(
                r"\s*SSID \d+ :\s*(.*)", line
            )

            signal_match = re.match(
                r"\s*Signal\s*:\s*(\d+)%", line
            )

            if ssid_match:
                current_ssid = ssid_match.group(1).strip()

                if not current_ssid:
                    current_ssid = "[Hidden network]"

                networks.setdefault(current_ssid, [])

            elif signal_match and current_ssid:
                networks[current_ssid].append(
                    int(signal_match.group(1))
                )

        results = []

        for name, signals in networks.items():
            if signals:
                average = sum(signals) / len(signals)
                results.append((name, average))

        results.sort(key=lambda x: x[1])

        terminal_print("=" * 45)
        terminal_print(" NETWORK NAME          SIGNAL")
        terminal_print("=" * 45)

        for name, signal in results:
            terminal_print(
                f"{name[:22]:<24} {signal:.0f}%"
            )

            if signal < 30:
                terminal_print("  STATUS: VERY WEAK")
            elif signal < 60:
                terminal_print("  STATUS: WEAK")
            elif signal < 80:
                terminal_print("  STATUS: GOOD")
            else:
                terminal_print("  STATUS: STRONG")

            terminal_print("-" * 45)

        terminal_print(
            f"\nFound {len(results)} Wi-Fi networks."
        )

    except Exception as error:
        terminal_print(f"Error: {error}")


def execute_command(event=None):
    global skull_color

    if terminal_entry is None:
        return

    command = terminal_entry.get().strip().lower()
    terminal_entry.delete(0, "end")

    if not command:
        return

    terminal_print("root@pasteshell:~$ " + command)

    if command.startswith("color "):

        try:
            number = int(command.split()[1])

            if number in COLORS:
                skull_color = COLORS[number]

                skull.config(fg=skull_color)
                title.config(fg=skull_color)

                terminal_print("Color changed successfully!")

            else:
                terminal_print("Invalid color. Use 1-8.")

        except (ValueError, IndexError):
            terminal_print("Usage: color <number>")

    elif command == "ipsea":
        start_network_scan()

    elif command == "weakwifi":
        scan_weak_wifi()

    elif command == "help":

        terminal_print("AVAILABLE COMMANDS:")
        terminal_print("color 1-8  - Change skull color")
        terminal_print("ipsea      - Scan local network")
        terminal_print("weakwifi   - Scans weak wifi spots")
        terminal_print("help       - Show commands")
        terminal_print("clear      - Clear terminal")
        terminal_print("exit       - Close terminal")


    elif command == "clear":

        terminal_output.config(state="normal")
        terminal_output.delete("1.0", "end")
        terminal_output.config(state="disabled")

    elif command == "exit":

        terminal_window.destroy()

    else:
        terminal_print("Unknown command. Type help.")

    try:
        terminal_entry.focus_set()
    except tk.TclError:
        pass


# ==========================================
# TERMINAL WINDOW
# ==========================================

def open_terminal():
    global terminal_window
    global terminal_output
    global terminal_entry

    if terminal_window is not None:
        try:
            if terminal_window.winfo_exists():
                terminal_window.lift()
                return
        except tk.TclError:
            pass

    terminal_window = tk.Toplevel(root)
    terminal_window.title("PASTESHELL TERMINAL")
    terminal_window.geometry("650x450")
    terminal_window.configure(bg="#080808")

    header = tk.Label(
        terminal_window,
        text="PASTESHELL // COMMAND INTERFACE",
        font=("Consolas", 14, "bold"),
        fg=skull_color,
        bg="#080808"
    )
    header.pack(pady=12)

    terminal_output = tk.Text(
        terminal_window,
        bg="#020202",
        fg="#00ff66",
        insertbackground="#00ff66",
        font=("Consolas", 11),
        height=17,
        width=75,
        relief="flat",
        state="disabled"
    )
    terminal_output.pack(
        padx=15,
        pady=5,
        fill="both",
        expand=True
    )

    terminal_print("PASTESHELL TERMINAL READY.")
    terminal_print("Type help to see available commands.")
    terminal_print("")

    terminal_entry = tk.Entry(
        terminal_window,
        bg="#111111",
        fg="#00ff66",
        insertbackground="#00ff66",
        font=("Consolas", 12),
        relief="flat"
    )
    terminal_entry.pack(
        fill="x",
        padx=15,
        pady=12
    )

    terminal_entry.bind("<Return>", execute_command)
    terminal_entry.focus_set()

    def on_close():
        global terminal_window
        global terminal_entry
        global terminal_output

        terminal_window.destroy()
        terminal_window = None
        terminal_entry = None
        terminal_output = None

    terminal_window.protocol(
        "WM_DELETE_WINDOW",
        on_close
    )


# ==========================================
# MAIN BUTTON
# ==========================================

button = tk.Button(
    root,
    text="[ OPEN TERMINAL ]",
    font=("Consolas", 14, "bold"),
    fg="#00ff66",
    bg="#101010",
    activeforeground="#ffffff",
    activebackground="#222222",
    relief="flat",
    bd=0,
    padx=25,
    pady=12,
    command=open_terminal
)

button.pack(pady=15)

footer = tk.Label(
    root,
    text="PASTESHELL v2.0 | ASCII SYSTEM",
    font=("Consolas", 10),
    fg="#444444",
    bg="#050505"
)
footer.pack(side="bottom", pady=15)


# ==========================================
# START APPLICATION
# ==========================================

animate()
process_scan_queue()
root.mainloop()
