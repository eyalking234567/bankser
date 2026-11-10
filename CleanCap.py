
import tkinter as tk
from tkinter import ttk
import os
import tempfile
import threading
import queue
from pathlib import Path

# ==========================================
# CLEANCAP V2.0
# ==========================================

root = tk.Tk()
root.title("CLEANCAP // SECURITY SYSTEM")
root.geometry("1100x760")
root.configure(bg="#050505")
root.resizable(False, False)

GREEN = "#00ff66"
DARK = "#050505"
PANEL = "#101010"
RED = "#ff3333"
YELLOW = "#ffcc00"
WHITE = "#eeeeee"

scan_queue = queue.Queue()
scanning = False

# ==========================================
# FILE DETECTION RULES
# ==========================================

DISPOSABLE_EXTENSIONS = {
    ".tmp", ".temp", ".bak", ".old",
    ".cache", ".log", ".dmp"
}

SUSPICIOUS_EXTENSIONS = {
    ".scr", ".vbs", ".vbe", ".hta",
    ".ps1", ".bat", ".cmd", ".pif"
}

EXECUTABLE_EXTENSIONS = {
    ".exe", ".dll", ".msi", ".com",
    ".js", ".jar"
}

# ==========================================
# MAIN TITLE
# ==========================================

title = tk.Label(
    root,
    text="C L E A N C A P",
    font=("Consolas", 39, "bold"),
    fg=GREEN,
    bg=DARK
)
title.pack(pady=(18, 0))

subtitle = tk.Label(
    root,
    text=">>> ADVANCED SYSTEM CLEANER <<<",
    font=("Consolas", 11, "bold"),
    fg="#666666",
    bg=DARK
)
subtitle.pack(pady=4)

# ==========================================
# GRAFFITI CAP
# ==========================================

cap_art = r"""
                 __________________________________
              .-'                                  `-.
            .'       C L E A N C A P                  `.
           /____________________________________________\
          /  / / / / / / / / / / / / / / / / / / / / /   \
         /________________________________________________\
                 \   C L E A N   /   S C A N   /
                  \________________________________/
                       |  C C  |
                       |_______|
"""

cap = tk.Label(
    root,
    text=cap_art,
    font=("Consolas", 13, "bold"),
    fg=GREEN,
    bg=DARK,
    justify="center"
)
cap.pack(pady=8)

# ==========================================
# STATUS
# ==========================================

status = tk.Label(
    root,
    text="SYSTEM READY // WAITING FOR SCAN",
    font=("Consolas", 11, "bold"),
    fg=GREEN,
    bg=DARK
)
status.pack(pady=5)

# ==========================================
# PROGRESS BAR
# ==========================================

style = ttk.Style()
style.theme_use("clam")

style.configure(
    "Green.Horizontal.TProgressbar",
    troughcolor="#151515",
    background=GREEN,
    bordercolor="#151515",
    lightcolor=GREEN,
    darkcolor=GREEN
)

progress = ttk.Progressbar(
    root,
    orient="horizontal",
    length=850,
    mode="indeterminate",
    style="Green.Horizontal.TProgressbar"
)
progress.pack(pady=10)

# ==========================================
# STATISTICS
# ==========================================

stats_frame = tk.Frame(root, bg=DARK)
stats_frame.pack(pady=8)

def create_stat(parent, label, color):
    frame = tk.Frame(
        parent,
        bg=PANEL,
        padx=25,
        pady=10
    )
    frame.pack(side="left", padx=12)

    value = tk.Label(
        frame,
        text="0",
        font=("Consolas", 22, "bold"),
        fg=color,
        bg=PANEL
    )
    value.pack()

    tk.Label(
        frame,
        text=label,
        font=("Consolas", 9),
        fg="#888888",
        bg=PANEL
    ).pack()

    return value


files_value = create_stat(
    stats_frame, "FILES SCANNED", WHITE
)

threats_value = create_stat(
    stats_frame, "FLAGGED FILES", RED
)

disposable_value = create_stat(
    stats_frame, "DISPOSABLE", YELLOW
)

# ==========================================
# RESULTS TABLE
# ==========================================

table_frame = tk.Frame(root, bg=DARK)
table_frame.pack(
    padx=25,
    pady=12,
    fill="both",
    expand=True
)

columns = (
    "category",
    "name",
    "location",
    "reason"
)

table = ttk.Treeview(
    table_frame,
    columns=columns,
    show="headings",
    height=11
)

table.heading("category", text="CATEGORY")
table.heading("name", text="FILE NAME")
table.heading("location", text="FILE LOCATION")
table.heading("reason", text="DETECTION REASON")

table.column("category", width=140)
table.column("name", width=180)
table.column("location", width=470)
table.column("reason", width=240)

table_style = ttk.Style()

table_style.configure(
    "Treeview",
    background="#090909",
    foreground=GREEN,
    fieldbackground="#090909",
    rowheight=26,
    font=("Consolas", 9)
)

table_style.configure(
    "Treeview.Heading",
    background="#151515",
    foreground=GREEN,
    font=("Consolas", 10, "bold")
)

table.tag_configure("threat", foreground=RED)
table.tag_configure("disposable", foreground=YELLOW)
table.tag_configure("review", foreground="#ff9900")

scrollbar = ttk.Scrollbar(
    table_frame,
    orient="vertical",
    command=table.yview
)

table.configure(
    yscrollcommand=scrollbar.set
)

table.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# ==========================================
# SCAN LOCATIONS
# ==========================================

def get_scan_locations():

    home = Path.home()

    locations = [
        Path(tempfile.gettempdir()),
        home / "Downloads",
        home / "Desktop",
        home / "AppData" / "Local" / "Temp"
    ]

    unique = {}

    for folder in locations:
        try:
            if folder.exists() and folder.is_dir():
                unique[str(folder).lower()] = folder
        except OSError:
            pass

    return list(unique.values())


# ==========================================
# FILE ANALYSIS
# ==========================================

def analyze_file(path):

    results = []

    extension = path.suffix.lower()
    name = path.name.lower()

    if extension in DISPOSABLE_EXTENSIONS:
        results.append((
            "DISPOSABLE",
            "Temporary or backup file"
        ))

    if extension in SUSPICIOUS_EXTENSIONS:
        results.append((
            "POTENTIAL THREAT",
            "Script or executable format"
        ))

    if extension in EXECUTABLE_EXTENSIONS:

        location = str(path).lower()

        if "downloads" in location or "temp" in location:
            results.append((
                "REVIEW",
                "Executable in Downloads/Temp"
            ))

    parts = name.split(".")

    if len(parts) >= 3:

        dangerous = {
            ".exe", ".scr", ".bat",
            ".cmd", ".ps1", ".vbs"
        }

        if "." + parts[-1] in dangerous:
            results.append((
                "POTENTIAL THREAT",
                "Double file extension"
            ))

    return results


# ==========================================
# BACKGROUND SCANNER
# ==========================================

def scan_worker():

    total = 0
    threats = 0
    disposable = 0

    try:

        scan_queue.put(("status", "INITIALIZING SCAN..."))

        locations = get_scan_locations()

        for folder in locations:

            scan_queue.put((
                "status",
                "SCANNING: " + str(folder)
            ))

            for current, dirs, files in os.walk(
                folder,
                onerror=lambda error: None
            ):

                dirs[:] = [
                    d for d in dirs
                    if not os.path.islink(
                        os.path.join(current, d)
                    )
                ]

                for filename in files:

                    path = Path(current) / filename
                    total += 1

                    try:

                        findings = analyze_file(path)

                        for category, reason in findings:

                            if category == "DISPOSABLE":
                                disposable += 1
                            else:
                                threats += 1

                            scan_queue.put((
                                "result",
                                category,
                                filename,
                                str(path),
                                reason
                            ))

                    except OSError:
                        continue

                    if total % 100 == 0:
                        scan_queue.put((
                            "stats",
                            total,
                            threats,
                            disposable
                        ))

        scan_queue.put((
            "stats",
            total,
            threats,
            disposable
        ))

        scan_queue.put((
            "status",
            "SCAN COMPLETE!"
        ))

    except Exception as error:

        scan_queue.put((
            "status",
            "SCAN ERROR: " + str(error)
        ))

    finally:
        scan_queue.put(("finished",))


# ==========================================
# START SCAN BUTTON
# ==========================================

def start_scan():

    global scanning

    if scanning:
        return

    scanning = True

    for item in table.get_children():
        table.delete(item)

    files_value.config(text="0")
    threats_value.config(text="0")
    disposable_value.config(text="0")

    status.config(
        text=">>> SCANNING SYSTEM <<<",
        fg=YELLOW
    )

    start_button.config(
        text="SCANNING...",
        state="disabled",
        fg="#888888"
    )

    progress.start(12)

    threading.Thread(
        target=scan_worker,
        daemon=True
    ).start()


# ==========================================
# PROCESS SCAN RESULTS
# ==========================================

def process_queue():

    global scanning

    try:

        while True:

            item = scan_queue.get_nowait()

            if item[0] == "status":

                status.config(text=item[1])

            elif item[0] == "stats":

                _, total, threats, disposable = item

                files_value.config(text=str(total))
                threats_value.config(text=str(threats))
                disposable_value.config(text=str(disposable))

            elif item[0] == "result":

                _, category, name, location, reason = item

                if category == "DISPOSABLE":
                    tag = "disposable"
                elif category == "REVIEW":
                    tag = "review"
                else:
                    tag = "threat"

                table.insert(
                    "",
                    "end",
                    values=(
                        category,
                        name,
                        location,
                        reason
                    ),
                    tags=(tag,)
                )

            elif item[0] == "finished":

                scanning = False

                progress.stop()

                start_button.config(
                    text="START SCAN",
                    state="normal",
                    fg=GREEN
                )

                status.config(
                    text=">>> SCAN FINISHED <<<",
                    fg=GREEN
                )

    except queue.Empty:
        pass

    root.after(100, process_queue)


# ==========================================
# GRAFFITI START BUTTON
# ==========================================

start_button = tk.Button(
    root,
    text="▶  START SCAN",
    font=("Consolas", 19, "bold"),
    fg=GREEN,
    bg="#101010",
    activeforeground="#ffffff",
    activebackground="#164b2c",
    relief="flat",
    bd=2,
    padx=55,
    pady=15,
    cursor="hand2",
    command=start_scan
)

start_button.pack(side="top", pady=12, fill="x", padx=40),
start_button.lift()

# ==========================================
# FOOTER
# ==========================================

footer = tk.Label(
    root,
    text="CLEANCAP v2.0 // SYSTEM SECURITY INTERFACE",
    font=("Consolas", 9),
    fg="#444444",
    bg=DARK
)

footer.pack(side="bottom", pady=12)

# ==========================================
# START PROGRAM
# ==========================================

process_queue()
root.mainloop()
