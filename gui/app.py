"""TurboQuant GUI — واجهة سحب وإفلات بسيطة (stdlib فقط: tkinter).

التشغيل:
    python -m gui.app
    # أو بعد التثبيت: turboquant-gui
"""
from __future__ import annotations
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import turboquant as tq


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TurboQuant — ضغط بدون فقد جودة")
        self.geometry("560x430")
        self.path = tk.StringVar()
        self.mode = tk.StringVar(value="balanced")
        self.status = tk.StringVar(value="اختر ملفاً ثم اضغط.")
        self._tok = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Entry(frm, textvariable=self.path, width=60).pack(fill="x")
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text="اختر ملف...", command=self.pick).pack(side="left")
        ttk.OptionMenu(row, self.mode, "balanced", "fast", "balanced", "max", "ultra").pack(side="left", padx=8)
        ttk.Button(row, text="اضغط", command=lambda: self.run("compress")).pack(side="left")
        ttk.Button(row, text="فك", command=lambda: self.run("decompress")).pack(side="left", padx=4)
        ttk.Button(row, text="إلغاء", command=self.cancel).pack(side="left", padx=4)
        ttk.Button(row, text="شهادة", command=self.cert).pack(side="left", padx=4)

        self.bar = ttk.Progressbar(frm, maximum=100)
        self.bar.pack(fill="x", pady=6)
        ttk.Label(frm, textvariable=self.status, wraplength=520).pack(fill="x")
        self.log = tk.Text(frm, height=12)
        self.log.pack(fill="both", expand=True, pady=6)

    def pick(self):
        p = filedialog.askopenfilename()
        if p:
            self.path.set(p)

    def cancel(self):
        if self._tok:
            self._tok.cancel()
            self.status.set("جارٍ الإلغاء...")

    def _progress(self, done, total, phase):
        pct = (done / total * 100) if total else 0
        self.after(0, lambda: (self.bar.config(value=pct),
                               self.status.set(f"{phase}: {pct:.0f}%")))

    def _say(self, msg):
        self.after(0, lambda: (self.log.insert("end", msg + "\n"), self.log.see("end")))

    def run(self, action):
        src = self.path.get().strip()
        if not src or not os.path.exists(src):
            return messagebox.showwarning("تنبيه", "اختر ملفاً موجوداً أولاً")
        self._tok = tq.CancelToken()
        self.bar.config(value=0)
        threading.Thread(target=self._work, args=(action, src, self.mode.get()), daemon=True).start()

    def _work(self, action, src, mode):
        try:
            if action == "compress":
                dst = src + ".tqz"
                info = tq.compress_lossless(src, dst, mode=mode,
                                            on_progress=self._progress, cancel=self._tok)
                self._say(f"OK: {info['orig_h']} -> {info['new_h']} ({info['codec']}) verified={info['verified']}")
                self.after(0, lambda: self.status.set(f"تم: {dst}"))
            else:
                info = tq.decompress_auto(src, None, on_progress=self._progress, cancel=self._tok)
                self._say(f"OK فك: {info['output']} verified={info.get('verified')}")
                self.after(0, lambda: self.status.set(f"تم: {info['output']}"))
        except tq.CancelledError:
            self.after(0, lambda: self.status.set("أُلغي بنجاح."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("خطأ", str(e)[:400]))

    def cert(self):
        src = self.path.get().strip()
        if not src:
            return
        try:
            from turboquant import verify_package, format_certificate
            self.log.insert("end", format_certificate(verify_package(src)) + "\n")
        except Exception as e:
            messagebox.showerror("خطأ", str(e)[:400])


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
