from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

from .clipboard import write_clipboard_text
from .storage import ClipboardStore


class AnimatedBorder:
    def __init__(self, canvas: tk.Canvas, enabled: bool = True):
        self.canvas = canvas
        self.phase = 0
        self.palette = ["#49dfff", "#6b7dff", "#9a64ff", "#ff67d0", "#49dfff"]
        self.enabled = enabled

    def redraw(self) -> None:
        self.canvas.delete("border")
        if not self.enabled:
            return
        w = max(2, self.canvas.winfo_width())
        h = max(2, self.canvas.winfo_height())
        if w <= 4 or h <= 4:
            return
        glow_layers = [
            (1, 1, 4, 0.18),
            (2, 2, 3, 0.38),
            (3, 3, 2, 0.72),
        ]
        if self.enabled:
            for inset_x, inset_y, width, alpha in glow_layers:
                color = self.palette[self.phase % len(self.palette)]
                self.canvas.create_rectangle(
                    inset_x,
                    inset_y,
                    w - inset_x,
                    h - inset_y,
                    outline=color,
                    width=width,
                    tags="border",
                )
        points = [
            (2, 2, w - 2, 2),
            (w - 2, 2, w - 2, h - 2),
            (w - 2, h - 2, 2, h - 2),
            (2, h - 2, 2, 2),
        ]
        for idx, (x1, y1, x2, y2) in enumerate(points):
            color = self.palette[(self.phase + idx) % len(self.palette)]
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2, tags="border")

    def tick(self) -> None:
        if not self.enabled:
            self.canvas.after(160, self.tick)
            return
        self.phase = (self.phase + 1) % len(self.palette)
        self.redraw()
        self.canvas.after(120, self.tick)


class ClipboardWindow:
    def __init__(self, db_path: Path):
        self.store = ClipboardStore(db_path)
        self.entries = []
        self.divider_x = 360
        self.dragging_divider = False
        self.visual_neon = True
        self.visual_transparency = True
        self.visual_border = True
        self.visual_divider_glow = True

        self.root = tk.Tk()
        self.root.title("CleepWheel")
        self.root.geometry("980x640")
        self.root.minsize(760, 480)
        self.root.configure(bg="#0e1320")
        self._apply_transparency()
        self._configure_theme()

        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0, bg="#0e1320")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.border = AnimatedBorder(self.canvas, enabled=self.visual_neon and self.visual_border)

        self.shell = tk.Frame(self.canvas, bg="#0e1320")
        self.shell_id = self.canvas.create_window(12, 12, window=self.shell, anchor="nw")

        self.header = tk.Frame(self.shell, bg="#0e1320")
        self.header.pack(fill=tk.X, padx=4, pady=(4, 8))

        tk.Label(
            self.header,
            text="CleepWheel",
            bg="#0e1320",
            fg="#f3f7ff",
            font=("Helvetica Neue", 18, "bold"),
        ).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            self.header,
            textvariable=self.status_var,
            bg="#0e1320",
            fg="#8fa1c9",
            font=("Helvetica Neue", 10),
        ).pack(side=tk.RIGHT)

        self.body = tk.Frame(self.shell, bg="#0e1320")
        self.body.pack(fill=tk.BOTH, expand=True)

        self.left = tk.Frame(self.body, bg="#141b2d", highlightthickness=1, highlightbackground="#2e3a59")
        self.divider = tk.Frame(self.body, bg="#61dafb", width=8, cursor="sb_h_double_arrow")
        self.right = tk.Frame(self.body, bg="#141b2d", highlightthickness=1, highlightbackground="#2e3a59")

        self.left.place(x=0, y=0, width=self.divider_x, relheight=1)
        self.divider.place(x=self.divider_x, y=0, width=8, relheight=1)
        self.right.place(x=self.divider_x + 8, y=0, relwidth=1, relheight=1, width=-(self.divider_x + 8))

        self._build_left_panel()
        self._build_right_panel()
        self._build_toolbar()

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.divider.bind("<ButtonPress-1>", self._start_drag)
        self.divider.bind("<B1-Motion>", self._drag_divider)
        self.divider.bind("<ButtonRelease-1>", self._stop_drag)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<Control-n>", lambda _event: self.toggle_neon())
        self.root.bind("<Control-t>", lambda _event: self.toggle_transparency())
        self.root.bind("<Control-b>", lambda _event: self.toggle_border())
        self.root.bind("<Control-d>", lambda _event: self.toggle_divider_glow())

        self.refresh()
        self.border.redraw()
        self.border.tick()

    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Cleep.TButton",
            padding=(12, 8),
            background="#141b2d",
            foreground="#f3f7ff",
            borderwidth=1,
        )
        style.map(
            "Cleep.TButton",
            background=[("active", "#24304b"), ("pressed", "#2e3a59")],
            foreground=[("disabled", "#8fa1c9")],
        )

    def _apply_transparency(self) -> None:
        if not self.visual_transparency:
            try:
                self.root.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
            return
        try:
            self.root.attributes("-alpha", 0.94)
        except tk.TclError:
            pass

    def _build_left_panel(self) -> None:
        tk.Label(
            self.left,
            text="History",
            bg="#141b2d",
            fg="#f3f7ff",
            font=("Helvetica Neue", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.listbox = tk.Listbox(
            self.left,
            activestyle="none",
            bg="#101726",
            fg="#f3f7ff",
            selectbackground="#24304b",
            selectforeground="#f3f7ff",
            highlightthickness=1,
            highlightbackground="#2e3a59",
            highlightcolor="#61dafb",
            borderwidth=0,
            relief="flat",
            exportselection=False,
            font=("Menlo", 11),
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self.show_selected())

    def _build_right_panel(self) -> None:
        tk.Label(
            self.right,
            text="Details",
            bg="#141b2d",
            fg="#f3f7ff",
            font=("Helvetica Neue", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.detail = tk.Text(
            self.right,
            wrap=tk.WORD,
            bg="#101726",
            fg="#f3f7ff",
            insertbackground="#61dafb",
            selectbackground="#24304b",
            highlightthickness=1,
            highlightbackground="#2e3a59",
            highlightcolor="#61dafb",
            borderwidth=0,
            relief="flat",
            font=("Menlo", 11),
        )
        self.detail.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.detail.configure(state="disabled")

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.shell, bg="#0e1320")
        bar.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(bar, text="Copy", style="Cleep.TButton", command=self.copy_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Edit", style="Cleep.TButton", command=self.edit_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Delete", style="Cleep.TButton", command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Refresh", style="Cleep.TButton", command=self.refresh).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Quit", style="Cleep.TButton", command=self.root.destroy).pack(side=tk.RIGHT)

        controls = tk.Frame(bar, bg="#0e1320")
        controls.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(controls, text="Neon", style="Cleep.TButton", command=self.toggle_neon).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="Transparency", style="Cleep.TButton", command=self.toggle_transparency).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="Border", style="Cleep.TButton", command=self.toggle_border).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="Divider Glow", style="Cleep.TButton", command=self.toggle_divider_glow).pack(side=tk.LEFT, padx=(0, 8))
        self.effect_state = tk.Label(controls, text=self._effect_summary(), bg="#0e1320", fg="#49dfff", font=("Helvetica Neue", 10, "bold"))
        self.effect_state.pack(side=tk.RIGHT)

        self.hint = tk.Label(
            bar,
            text="Drag the bright divider to resize.",
            bg="#0e1320",
            fg="#8fa1c9",
            font=("Helvetica Neue", 10),
        )
        self.hint.pack(side=tk.BOTTOM, anchor="w", pady=(10, 0))

    def _on_canvas_resize(self, _event) -> None:
        width = max(0, self.canvas.winfo_width() - 24)
        height = max(0, self.canvas.winfo_height() - 24)
        self.canvas.coords(self.shell_id, 12, 12)
        self.canvas.itemconfigure(self.shell_id, width=width, height=height)
        self.border.redraw()
        self._layout_splitter()

    def _layout_splitter(self) -> None:
        body_w = max(1, self.body.winfo_width())
        body_h = max(1, self.body.winfo_height())
        divider_w = 8
        min_left = 240
        min_right = 320
        usable = max(min_left + min_right + divider_w, body_w)
        self.divider_x = max(min_left, min(self.divider_x, usable - divider_w - min_right))
        left_w = self.divider_x
        right_x = self.divider_x + divider_w
        right_w = max(min_right, body_w - right_x)

        self.left.place(x=0, y=0, width=left_w, height=body_h)
        self.divider.place(x=self.divider_x, y=0, width=divider_w, height=body_h)
        self.right.place(x=right_x, y=0, width=right_w, height=body_h)

        self.divider.configure(bg=self._divider_color())
        if self.visual_divider_glow and self.visual_neon:
            self.left.configure(highlightbackground=self._divider_color())
            self.right.configure(highlightbackground=self._divider_color())
        else:
            self.left.configure(highlightbackground="#2e3a59")
            self.right.configure(highlightbackground="#2e3a59")

    def _divider_color(self) -> str:
        if not self.visual_neon:
            return "#31415e"
        palette = ["#61dafb", "#8a5cff", "#ff67d0", "#3ddcff", "#61dafb"]
        return palette[(self.divider_x // 8) % len(palette)]

    def _start_drag(self, _event) -> None:
        self.dragging_divider = True

    def _drag_divider(self, event) -> None:
        if not self.dragging_divider:
            return
        body_w = max(1, self.body.winfo_width())
        self.divider_x = max(240, min(event.x_root - self.root.winfo_rootx() - 12, body_w - 328))
        self._layout_splitter()
        self.status_var.set("Divider adjusted")

    def _stop_drag(self, _event) -> None:
        self.dragging_divider = False

    def refresh(self) -> None:
        self.entries = self.store.list(200)
        self.listbox.delete(0, tk.END)
        for entry in self.entries:
            snippet = entry.content.replace("\n", " ")
            if len(snippet) > 90:
                snippet = snippet[:87] + "..."
            self.listbox.insert(tk.END, f"{entry.id}: {snippet}")
        if self.entries:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.show_selected()
            self.status_var.set(f"{len(self.entries)} entries loaded")
        else:
            self.detail.configure(state="normal")
            self.detail.delete("1.0", tk.END)
            self.detail.insert(tk.END, "No clipboard history yet.")
            self.detail.configure(state="disabled")
            self.status_var.set("No entries")

    def _effect_summary(self) -> str:
        parts = []
        parts.append("Neon ON" if self.visual_neon else "Neon OFF")
        parts.append("Transparency ON" if self.visual_transparency else "Transparency OFF")
        parts.append("Border ON" if self.visual_border else "Border OFF")
        parts.append("Divider Glow ON" if self.visual_divider_glow else "Divider Glow OFF")
        return " | ".join(parts)

    def _sync_effects(self) -> None:
        self.border.enabled = self.visual_neon and self.visual_border
        self._apply_transparency()
        self._layout_splitter()
        self.border.redraw()
        self.effect_state.configure(text=self._effect_summary())
        self.status_var.set(self._effect_summary())

    def toggle_neon(self) -> None:
        self.visual_neon = not self.visual_neon
        self._sync_effects()

    def toggle_transparency(self) -> None:
        self.visual_transparency = not self.visual_transparency
        self._sync_effects()

    def toggle_border(self) -> None:
        self.visual_border = not self.visual_border
        self._sync_effects()

    def toggle_divider_glow(self) -> None:
        self.visual_divider_glow = not self.visual_divider_glow
        self._sync_effects()

    def selected_entry(self):
        selection = self.listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx >= len(self.entries):
            return None
        return self.entries[idx]

    def show_selected(self) -> None:
        entry = self.selected_entry()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", tk.END)
        if not entry:
            self.detail.insert(tk.END, "Select an item to inspect it here.")
            self.detail.configure(state="disabled")
            return
        self.detail.insert(tk.END, f"ID: {entry.id}\n")
        self.detail.insert(tk.END, f"Created: {entry.created_at}\n")
        self.detail.insert(tk.END, f"Hash: {entry.content_hash[:16]}...\n")
        self.detail.insert(tk.END, "\n")
        self.detail.insert(tk.END, entry.content)
        self.detail.configure(state="disabled")

    def copy_selected(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        write_clipboard_text(entry.content)
        self.status_var.set(f"Copied entry {entry.id}")

    def edit_selected(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        new_text = simpledialog.askstring(
            "Edit entry",
            "Edit content:",
            initialvalue=entry.content,
            parent=self.root,
        )
        if new_text is None:
            return
        if self.store.update(entry.id, new_text):
            self.refresh()
            self.status_var.set(f"Edited entry {entry.id}")

    def delete_selected(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        if messagebox.askyesno("Delete entry", "Delete selected clipboard entry?"):
            if self.store.delete(entry.id):
                self.refresh()
                self.status_var.set(f"Deleted entry {entry.id}")

    def run(self) -> int:
        self.root.mainloop()
        return 0


def open_window(db_path: Path) -> int:
    return ClipboardWindow(db_path).run()
