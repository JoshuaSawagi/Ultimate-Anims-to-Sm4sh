#!/usr/bin/env python3
"""Ult2S4 GUI - point-and-click front end for ult2s4.py (Ultimate -> Smash 4 animation porter).

Put this file in the same folder as ult2s4.py and run it (double-click "Ult2S4 GUI.bat", or: py ult2s4_gui.py).
Needs Python 3 + numpy (same as ult2s4.py). Tkinter ships with the python.org installer.
"""
import os, sys, re, io, json, shutil, threading, datetime, contextlib, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import ult2s4
except Exception as e:  # numpy missing or script not next to this file
    tk.Tk().withdraw()
    messagebox.showerror("Ult2S4", "Could not load ult2s4.py from\n%s\n\n%s\n\nPut ult2s4_gui.py next to ult2s4.py and "
                         "make sure numpy is installed (py -m pip install numpy)." % (HERE, e))
    sys.exit(1)

SETTINGS = os.path.join(HERE, "ult2s4_gui_settings.json")
# colour themes: bg = window, panel = boxes, field = lists/inputs, fg = text, muted = hints, accent = selection/highlight
THEMES = {
    "Windows default": None,
    "Light":    dict(bg="#f3f3f3", panel="#f3f3f3", field="#ffffff", fg="#1b1b1b", muted="#6b6b6b", border="#c9c9c9", accent="#0a64d8", dark=False),
    "Dark":     dict(bg="#1e1f22", panel="#1e1f22", field="#2b2d31", fg="#e6e6e6", muted="#9a9ca3", border="#3f4147", accent="#5865f2", dark=True),
    "Midnight": dict(bg="#0f1729", panel="#0f1729", field="#18233d", fg="#dbe4ff", muted="#8b9bc4", border="#2a3a5f", accent="#4f8cff", dark=True),
    "Forest":   dict(bg="#16201a", panel="#16201a", field="#1f2d24", fg="#e3f1e6", muted="#8fae97", border="#30463a", accent="#3fbf6f", dark=True),
    "Peach":    dict(bg="#fff1f4", panel="#fff1f4", field="#ffffff", fg="#3a1f29", muted="#946270", border="#efc3cf", accent="#e0558b", dark=False),
    "Daisy":    dict(bg="#fff8e1", panel="#fff8e1", field="#ffffff", fg="#3b2a00", muted="#8a6d1f", border="#efd98f", accent="#e69500", dark=False),
}

SKIRT_MODES = [("auto (recommended)", "auto"), ("stock - Smash 4's own skirt", "stock"),
               ("anchored - Ultimate sway on Smash 4 shape", "anchored"),
               ("neutral - still dress, pushed out by the legs", "neutral"), ("ult - Ultimate skirt as is", "ult")]


def default_motion(path):
    b = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r'([a-z])(\d+)(.*)', b, re.I)
    if not m:
        return b
    return m.group(1).upper() + m.group(2) + m.group(3)[:1].upper() + m.group(3)[1:]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ult2S4 - Ultimate to Smash 4 animation porter")
        self.geometry("900x680")
        self.minsize(760, 560)
        self.motions = []          # motion names found in main.pac
        self.busy = False
        s = self.load_settings()

        pad = dict(padx=8, pady=4)
        top = ttk.LabelFrame(self, text="Smash 4 files")
        top.pack(fill="x", **pad)
        self.vbn = tk.StringVar(value=s.get("vbn", ""))
        self.pacs = tk.StringVar(value=s.get("pacs", ""))
        self.stock = tk.StringVar(value=s.get("stock", ""))
        self.out = tk.StringVar(value=s.get("out", os.path.join(HERE, "out")))
        self.row(top, 0, "Skeleton (model.vbn)", self.vbn, self.pick_vbn)
        self.row(top, 1, "Motion folder (.pac files)", self.pacs, self.pick_pacs)
        self.row(top, 2, "Stock reference (optional)", self.stock, self.pick_stock)
        self.row(top, 3, "Output folder", self.out, self.pick_out)
        ttk.Label(top, text="Stock reference = a folder with the fighter's untouched original .pac files. Set it once your motion "
                  "folder already has converted moves, so the skirt is always judged against the real Smash 4 dress.",
                  wraplength=760, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        top.columnconfigure(1, weight=1)

        mid = ttk.LabelFrame(self, text="Ultimate animations (.anim)  -  double-click a row to change its target slot")
        mid.pack(fill="both", expand=True, **pad)
        cols = ("file", "motion")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=8, selectmode="extended")
        self.tree.heading("file", text=".anim file")
        self.tree.heading("motion", text="Smash 4 motion slot")
        self.tree.column("file", width=520)
        self.tree.column("motion", width=220)
        self.tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=4, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self.edit_motion)
        ttk.Button(mid, text="Add .anim files...", command=self.add_anims).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Button(mid, text="Add same file to another slot", command=self.duplicate).grid(row=1, column=1, sticky="w")
        ttk.Button(mid, text="Remove selected", command=self.remove).grid(row=1, column=2, sticky="w")
        self.slot_info = ttk.Label(mid, text="", style="Muted.TLabel")
        self.slot_info.grid(row=1, column=3, sticky="e")
        mid.columnconfigure(3, weight=1)
        mid.rowconfigure(0, weight=1)
        for p, m in s.get("anims", []):
            if os.path.exists(p):
                self.tree.insert("", "end", values=(p, m))

        opt = ttk.LabelFrame(self, text="Options")
        opt.pack(fill="x", **pad)
        ttk.Label(opt, text="Skirt (Peach/Daisy):").grid(row=0, column=0, sticky="w", padx=6)
        self.skirt = tk.StringVar(value=dict((v, k) for k, v in SKIRT_MODES).get(s.get("skirt", "auto"), SKIRT_MODES[0][0]))
        ttk.Combobox(opt, textvariable=self.skirt, values=[k for k, _ in SKIRT_MODES], state="readonly", width=42).grid(row=0, column=1, sticky="w")
        self.pushout = tk.BooleanVar(value=s.get("pushout", True))
        ttk.Checkbutton(opt, text="Push skirt out where legs poke through", variable=self.pushout).grid(row=0, column=2, sticky="w", padx=12)
        ttk.Label(opt, text="Theme:").grid(row=1, column=0, sticky="w", padx=6, pady=(4, 2))
        self.theme = tk.StringVar(value=s.get("theme", "Dark") if s.get("theme", "Dark") in THEMES else "Dark")
        tcb = ttk.Combobox(opt, textvariable=self.theme, values=list(THEMES), state="readonly", width=20)
        tcb.grid(row=1, column=1, sticky="w", pady=(4, 2))
        tcb.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())
        self.accent = s.get("accent")       # custom accent colour or None
        af = ttk.Frame(opt)
        af.grid(row=1, column=2, sticky="w", padx=12, pady=(4, 2))
        ttk.Button(af, text="Accent color...", command=self.pick_accent).pack(side="left")
        ttk.Button(af, text="Reset", command=self.reset_accent).pack(side="left", padx=4)
        self.swatch = ttk.Label(af, text="      ", style="Swatch.TLabel")
        self.swatch.pack(side="left", padx=4)

        act = ttk.Frame(self)
        act.pack(fill="x", **pad)
        self.convert_btn = ttk.Button(act, text="Convert", command=self.convert)
        self.convert_btn.pack(side="left")
        self.install_btn = ttk.Button(act, text="Install into motion folder...", command=self.install)
        self.install_btn.pack(side="left", padx=8)
        ttk.Button(act, text="Open output folder", command=lambda: self.open_folder(self.out.get())).pack(side="left")
        self.status = ttk.Label(act, text="")
        self.status.pack(side="right")

        logf = ttk.LabelFrame(self, text="Log")
        logf.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logf, height=12, wrap="none", font=("Consolas", 9), relief="flat", borderwidth=4)
        self.log.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(logf, orient="vertical", command=self.log.yview)
        lsb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=lsb.set)

        self.style = ttk.Style(self)
        self.default_theme = self.style.theme_use()
        self.apply_theme()
        self.refresh_motions()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- colours ----------
    def palette(self):
        t = THEMES.get(self.theme.get())
        if t is None:
            return None
        t = dict(t)
        if self.accent:
            t["accent"] = self.accent
        return t

    def pick_accent(self):
        c = colorchooser.askcolor(color=(self.palette() or THEMES["Light"])["accent"], title="Accent color", parent=self)[1]
        if c:
            self.accent = c
            if self.theme.get() == "Windows default":
                self.theme.set("Light")
            self.apply_theme()

    def reset_accent(self):
        self.accent = None
        self.apply_theme()

    def apply_theme(self):
        st, t = self.style, self.palette()
        if t is None:                                  # native look
            st.theme_use(self.default_theme)
            for name in ("Muted.TLabel",):
                st.configure(name, foreground="gray")
            self.configure(bg=st.lookup("TFrame", "background") or "SystemButtonFace")
            self.log.configure(bg="white", fg="black", insertbackground="black", selectbackground="#0a64d8", selectforeground="white")
            st.configure("Swatch.TLabel", background=self.cget("bg"))
            self.title_bar(False)
            return
        bg, field, fg, muted, border, ac = t["bg"], t["field"], t["fg"], t["muted"], t["border"], t["accent"]
        hover = self.mix(field, ac, 0.25)
        st.theme_use("clam")
        st.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=border, lightcolor=bg,
                     darkcolor=bg, troughcolor=field, focuscolor=ac, selectbackground=ac, selectforeground="#ffffff",
                     insertcolor=fg, arrowcolor=fg)
        st.configure("TFrame", background=bg)
        st.configure("TLabel", background=bg, foreground=fg)
        st.configure("Muted.TLabel", background=bg, foreground=muted)
        st.configure("TLabelframe", background=bg, bordercolor=border)
        st.configure("TLabelframe.Label", background=bg, foreground=ac)
        st.configure("TButton", background=field, foreground=fg, bordercolor=border, padding=(10, 4))
        st.map("TButton", background=[("pressed", ac), ("active", hover)], foreground=[("pressed", "#ffffff")],
               bordercolor=[("focus", ac)])
        st.configure("TCheckbutton", background=bg, foreground=fg, indicatorbackground=field, indicatorforeground=ac)
        st.map("TCheckbutton", background=[("active", bg)], indicatorbackground=[("selected", field)])
        st.configure("TEntry", fieldbackground=field, foreground=fg, bordercolor=border, insertcolor=fg)
        st.map("TEntry", bordercolor=[("focus", ac)])
        st.configure("TCombobox", fieldbackground=field, background=field, foreground=fg, arrowcolor=fg, bordercolor=border)
        st.map("TCombobox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
               background=[("active", hover)], bordercolor=[("focus", ac)], selectbackground=[("readonly", field)],
               selectforeground=[("readonly", fg)])
        self.option_add("*TCombobox*Listbox.background", field)
        self.option_add("*TCombobox*Listbox.foreground", fg)
        self.option_add("*TCombobox*Listbox.selectBackground", ac)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        st.configure("Treeview", background=field, fieldbackground=field, foreground=fg, bordercolor=border, rowheight=22)
        st.map("Treeview", background=[("selected", ac)], foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=bg, foreground=fg, bordercolor=border, relief="flat")
        st.map("Treeview.Heading", background=[("active", hover)])
        st.configure("Vertical.TScrollbar", background=field, troughcolor=bg, bordercolor=bg, arrowcolor=muted)
        st.map("Vertical.TScrollbar", background=[("active", hover)])
        self.configure(bg=bg)
        self.log.configure(bg=field, fg=fg, insertbackground=fg, selectbackground=ac, selectforeground="#ffffff")
        st.configure("Swatch.TLabel", background=ac)
        self.title_bar(t["dark"])

    @staticmethod
    def mix(a, b, f):
        a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(a, b))

    def title_bar(self, dark):
        # Windows 10/11: dark window title bar to match (ignored elsewhere)
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            v = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0:
                    break
        except Exception:
            pass

    # ---------- helpers ----------
    def row(self, parent, r, label, var, cmd):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=r, column=1, sticky="ew", pady=3)
        ttk.Button(parent, text="Browse...", command=cmd).grid(row=r, column=2, padx=6, pady=3)

    def say(self, text):
        self.log.insert("end", text.rstrip("\n") + "\n")
        self.log.see("end")

    def load_settings(self):
        try:
            with open(SETTINGS) as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self):
        try:
            with open(SETTINGS, "w") as f:
                json.dump(dict(vbn=self.vbn.get(), pacs=self.pacs.get(), stock=self.stock.get(), out=self.out.get(),
                               skirt=dict(SKIRT_MODES)[self.skirt.get()], pushout=self.pushout.get(),
                               theme=self.theme.get(), accent=self.accent,
                               anims=[self.tree.item(i, "values") for i in self.tree.get_children()]), f, indent=1)
        except Exception:
            pass

    def on_close(self):
        self.save_settings()
        self.destroy()

    def open_folder(self, path):
        if path and os.path.isdir(path):
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                messagebox.showinfo("Ult2S4", path)
        else:
            messagebox.showinfo("Ult2S4", "That folder doesn't exist yet.")

    # ---------- pickers ----------
    def pick_vbn(self):
        p = filedialog.askopenfilename(title="Smash 4 model.vbn", filetypes=[("VBN skeleton", "*.vbn"), ("All files", "*.*")])
        if p:
            self.vbn.set(os.path.normpath(p))

    def pick_pacs(self):
        p = filedialog.askdirectory(title="Folder with main.pac, lhand.pac, rhand.pac ...")
        if p:
            self.pacs.set(os.path.normpath(p))
            self.refresh_motions()

    def pick_stock(self):
        p = filedialog.askdirectory(title="Folder with the fighter's untouched stock .pac files (main.pac, peachsw1.pac ...)")
        if p:
            self.stock.set(os.path.normpath(p))

    def pick_out(self):
        p = filedialog.askdirectory(title="Output folder")
        if p:
            self.out.set(os.path.normpath(p))

    def refresh_motions(self):
        self.motions = []
        mp = os.path.join(self.pacs.get(), "main.pac")
        if os.path.isfile(mp):
            try:
                files, _ = ult2s4.read_pac(mp)
                names = sorted({re.sub(r'^Fit\w+?BodyMain', '', k)[:-4] for k in files if k.endswith('.omo')})
                self.motions = names
                self.slot_info.config(text="%d motion slots found in main.pac" % len(names))
            except Exception as e:
                self.slot_info.config(text="couldn't read main.pac: %s" % e)
        else:
            self.slot_info.config(text="pick the motion folder to list slots")

    # ---------- anim list ----------
    def add_anims(self):
        ps = filedialog.askopenfilenames(title="Ultimate animations exported from StudioSB",
                                         filetypes=[("Maya anim", "*.anim"), ("All files", "*.*")])
        for p in ps:
            m = default_motion(p)
            if self.motions:   # match case-insensitively to a real slot name
                hit = [x for x in self.motions if x.lower() == m.lower()]
                m = hit[0] if hit else m
            self.tree.insert("", "end", values=(os.path.normpath(p), m))

    def duplicate(self):
        for i in self.tree.selection():
            p, m = self.tree.item(i, "values")
            self.tree.insert("", "end", values=(p, m))

    def remove(self):
        for i in self.tree.selection():
            self.tree.delete(i)

    def edit_motion(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        p, m = self.tree.item(item, "values")
        win = tk.Toplevel(self)
        win.title("Target slot")
        win.transient(self)
        win.configure(bg=self.cget("bg"))
        ttk.Label(win, text=os.path.basename(p)).pack(padx=10, pady=(10, 4))
        var = tk.StringVar(value=m)
        cb = ttk.Combobox(win, textvariable=var, values=self.motions, width=36)
        cb.pack(padx=10, pady=4)
        cb.focus_set()

        def ok(*_):
            self.tree.item(item, values=(p, var.get().strip()))
            win.destroy()
        ttk.Button(win, text="OK", command=ok).pack(pady=(4, 10))
        win.bind("<Return>", ok)

    # ---------- run ----------
    def check_inputs(self):
        if not os.path.isfile(self.vbn.get()):
            return "Pick the Smash 4 model.vbn."
        if not os.path.isfile(os.path.join(self.pacs.get(), "main.pac")):
            return "The motion folder must contain main.pac (and the fighter's other .pac files)."
        if not self.tree.get_children():
            return "Add at least one .anim file."
        if self.stock.get().strip() and not os.path.isfile(os.path.join(self.stock.get().strip(), "main.pac")):
            return "The stock reference folder must contain the original main.pac (or leave it empty)."
        if os.path.normcase(os.path.abspath(self.out.get())) == os.path.normcase(os.path.abspath(self.pacs.get())):
            return "Use an output folder different from the motion folder (then use Install)."
        if self.motions:
            bad = [m for _, m in (self.tree.item(i, "values") for i in self.tree.get_children())
                   if m.lower() not in {x.lower() for x in self.motions}]
            if bad and not messagebox.askyesno("Ult2S4", "These slots aren't in main.pac and will be skipped:\n%s\n\nContinue?" % ", ".join(bad)):
                return ""
        return None

    def convert(self):
        if self.busy:
            return
        err = self.check_inputs()
        if err is not None:
            if err:
                messagebox.showwarning("Ult2S4", err)
            return
        argv = ["ult2s4.py", "--vbn", self.vbn.get(), "--pacs", self.pacs.get(), "--out", self.out.get(),
                "--skirt", dict(SKIRT_MODES)[self.skirt.get()]]
        if self.stock.get().strip():
            argv += ["--stock", self.stock.get().strip()]
        if not self.pushout.get():
            argv.append("--no-pushout")
        argv += ["%s=%s" % (p, m) for p, m in (self.tree.item(i, "values") for i in self.tree.get_children())]
        self.save_settings()
        self.busy = True
        self.convert_btn.state(["disabled"])
        self.install_btn.state(["disabled"])
        self.status.config(text="Converting...")
        self.say("\n=== Convert %s ===" % datetime.datetime.now().strftime("%H:%M:%S"))
        self.result = None
        threading.Thread(target=self.worker, args=(argv,), daemon=True).start()
        self.after(150, self.poll)

    def poll(self):
        # Tk must only be touched from the main thread: the worker just leaves its result here
        if self.result is None:
            self.after(150, self.poll)
        else:
            self.done(*self.result)

    def worker(self, argv):
        buf = io.StringIO()
        ok = True
        old = sys.argv
        try:
            sys.argv = argv
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                ult2s4.main()
        except SystemExit as e:
            ok = not e.code
            if e.code and not isinstance(e.code, int):
                buf.write(str(e.code) + "\n")
        except Exception:
            ok = False
            buf.write(traceback.format_exc())
        finally:
            sys.argv = old
        self.result = (ok, buf.getvalue())

    def done(self, ok, text):
        self.say(text)
        self.busy = False
        self.convert_btn.state(["!disabled"])
        self.install_btn.state(["!disabled"])
        if ok:
            self.status.config(text="Done - new .pac files are in the output folder")
            self.say("Done. New .pac files: %s\nUse 'Install into motion folder' to copy them over (your current files get backed up)." % self.out.get())
        else:
            self.status.config(text="Failed - see log")

    def install(self):
        out, dst = self.out.get(), self.pacs.get()
        pacs = [f for f in os.listdir(out) if f.lower().endswith(".pac")] if os.path.isdir(out) else []
        if not pacs:
            messagebox.showinfo("Ult2S4", "Convert first - the output folder has no .pac files.")
            return
        if not os.path.isdir(dst):
            messagebox.showwarning("Ult2S4", "The motion folder doesn't exist.")
            return
        if not messagebox.askyesno("Ult2S4", "Copy %d .pac files into\n%s ?\n\nYour current files there are backed up first to\n%s"
                                   % (len(pacs), dst, os.path.join(HERE, "backups"))):
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bdir = os.path.join(HERE, "backups", stamp)   # kept outside the workspace so it never ends up in the patch
        os.makedirs(bdir, exist_ok=True)
        for f in pacs:
            if os.path.isfile(os.path.join(dst, f)):
                shutil.copy2(os.path.join(dst, f), os.path.join(bdir, f))
            shutil.copy2(os.path.join(out, f), os.path.join(dst, f))
        self.say("Installed %s into %s\nBackup of the previous files: %s\nRebuild the patch in Sm4shExplorer to test." % (", ".join(pacs), dst, bdir))
        self.status.config(text="Installed - rebuild the patch to test")
        self.refresh_motions()


if __name__ == "__main__":
    App().mainloop()
