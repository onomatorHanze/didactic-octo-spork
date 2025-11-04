import tkinter as tk
from tkinter import ttk

class StartView(tk.Frame):
    def __init__(self, master, start_callback, subjects):
        super().__init__(master)
        self.start_callback = start_callback
        self.subjects = subjects  # lijst met vakken uit Excel
        self.pack(fill="both", expand=True)

        # Titel
        tk.Label(self, text="DocQuiz", font=("Arial", 22, "bold")).pack(pady=20)

        # Beschrijving
        tk.Label(
            self,
            text="Oefen je lesstof via een slimme quiz.\nSucces!",
            justify="center",
            font=("Arial", 11)
        ).pack(pady=10)

        # Aantal vragen kiezen
        frame = tk.Frame(self)
        frame.pack(pady=10)
        tk.Label(frame, text="Aantal vragen:").pack(side="left", padx=5)
        self.num_var = tk.IntVar(value=5)
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.num_var, width=5).pack(side="left")

        # Dropdown voor vakkeuze
        tk.Label(self, text="Kies vak:").pack(pady=5)
        self.vak_var = tk.StringVar(value=self.subjects[0])
        ttk.Combobox(self, textvariable=self.vak_var, values=self.subjects, state="readonly").pack(pady=5)

        # Startknop
        ttk.Button(self, text="Start quiz", command=self.on_start).pack(pady=20)

    def on_start(self):
        n = self.num_var.get()
        vak = self.vak_var.get()
        self.start_callback(n, vak)
