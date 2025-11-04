import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from models import Question
from tkinter import messagebox


class QuizView(tk.Frame):
    def __init__(self, master, next_callback):
        super().__init__(master)
        self.next_callback = next_callback
        self.pack(fill="both", expand=True)

        self.score_var = tk.StringVar(value="Score: 0 goed | 0 fout")
        self.score_label = tk.Label(self, textvariable=self.score_var, font=("Arial", 11, "bold"))
        self.score_label.pack(pady=5)

        self.question_label = tk.Label(self, text="", font=("Arial", 14), wraplength=450, justify="left")
        self.question_label.pack(pady=15)

        self.answer_frame = tk.Frame(self)
        self.answer_frame.pack(pady=10)

        self.image_label = tk.Label(self)
        self.image_label.pack(pady=10)

        self.formula_frame = tk.Frame(self)
        self.formula_frame.pack(pady=10)

        ttk.Button(self, text="Volgende", command=self.on_next).pack(pady=15)

        self.current_question = None
        self.selected_value = tk.StringVar()
        self.image_cache = None  # voorkom dat de afbeelding verdwijnt

    def show_question(self, q: Question):
        """Toon een nieuwe vraag op het scherm."""
        self.current_question = q
        self.question_label.config(text=q.text)

        # Oude widgets wissen
        for widget in self.answer_frame.winfo_children():
            widget.destroy()
        for widget in self.formula_frame.winfo_children():
            widget.destroy()
        self.image_label.config(image="")

        self.selected_value.set("")

        # ---- antwoordopties ----
        if q.type == "mc":
            for i, choice in enumerate(q.choices):
                ttk.Radiobutton(self.answer_frame, text=choice, value=str(i),
                                variable=self.selected_value).pack(anchor="w")
        elif q.type == "tf":
            for val in ["Waar", "Onwaar"]:
                ttk.Radiobutton(self.answer_frame, text=val, value=val,
                                variable=self.selected_value).pack(anchor="w")
        elif q.type == "input":
            ttk.Entry(self.answer_frame, textvariable=self.selected_value).pack()
        else:
            tk.Label(self.answer_frame, text="Onbekend vraagtype.").pack()

        # ---- afbeelding tonen ----
        if hasattr(q, "image_path") and q.image_path:
            try:
                img = Image.open(q.image_path)
                img = img.resize((300, 200))
                self.image_cache = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.image_cache)
            except Exception as e:
                print(f"Kon afbeelding niet laden: {e}")

        # ---- formule tonen ----
        if hasattr(q, "formula_latex") and q.formula_latex:
            try:
                fig, ax = plt.subplots(figsize=(3, 1))
                ax.text(0.5, 0.5, f"${q.formula_latex}$", fontsize=18, ha="center", va="center")
                ax.axis("off")

                canvas = FigureCanvasTkAgg(fig, master=self.formula_frame)
                canvas.draw()
                canvas.get_tk_widget().pack()
            except Exception as e:
                print(f"Kon formule niet renderen: {e}")

    def on_next(self):
            answer = self.selected_value.get()
            if not answer:
                tk.messagebox.showinfo("Let op", "Kies of vul eerst een antwoord in!")
                return

            # Controleer antwoord
            q = self.current_question
            correct = False

            if q.type == "mc":
                correct = int(answer) == q.answer
            elif q.type == "tf":
                tf_map = {"Waar": True, "Onwaar": False}
                correct = tf_map.get(answer) == q.answer
            elif q.type == "input":
                try:
                    val = float(answer.replace(",", "."))
                    correct = abs(val - q.answer_numeric) <= q.tolerance
                except:
                    correct = False

            # Toon feedback + uitleg
            result_text = "✅ Goed!" if correct else "❌ Fout!"
            explanation = q.explanation if hasattr(q, "explanation") else ""
            msg = f"{result_text}\n\n{explanation}"

            tk.messagebox.showinfo("Resultaat", msg)

            # Ga daarna verder
            self.next_callback(q, answer)
    def update_score(self, correct_count, wrong_count):
            """Werk de scorebalk bij."""
            self.score_var.set(f"Score: {correct_count} goed | {wrong_count} fout")        
