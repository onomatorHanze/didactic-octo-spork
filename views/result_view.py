import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


class ResultView(tk.Frame):
    def __init__(self, master, restart_callback):
        super().__init__(master)
        self.restart_callback = restart_callback
        self.pack(fill="both", expand=True)

        tk.Label(self, text="Resultaten", font=("Arial", 20, "bold")).pack(pady=10)
        self.summary_label = tk.Label(self, text="", font=("Arial", 12))
        self.summary_label.pack(pady=5)

        # Grafiekcontainer
        self.chart_frame = tk.Frame(self)
        self.chart_frame.pack(pady=10)

        ttk.Button(self, text="Opnieuw starten", command=self.on_restart).pack(pady=15)

    def show_results(self, results, tag_stats):
        """
        results = {'correct': x, 'wrong': y}
        tag_stats = {'DC': {'correct': 5, 'wrong': 2}, 'AC': {...}}
        """
        total = results["correct"] + results["wrong"]
        perc = 100 * results["correct"] / total if total > 0 else 0
        self.summary_label.config(
            text=f"Goed: {results['correct']}  |  Fout: {results['wrong']}  |  Score: {perc:.1f}%"
        )

        # Oude grafiek wissen
        for w in self.chart_frame.winfo_children():
            w.destroy()

        # Grafiek tekenen
        if tag_stats:
            tags = list(tag_stats.keys())
            correct = [v["correct"] for v in tag_stats.values()]
            wrong = [v["wrong"] for v in tag_stats.values()]

            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar(tags, correct, label="Goed")
            ax.bar(tags, wrong, bottom=correct, label="Fout")
            ax.set_ylabel("Aantal antwoorden")
            ax.legend()
            ax.set_title("Voortgang per onderwerp")

            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack()

    def on_restart(self):
        self.restart_callback()
