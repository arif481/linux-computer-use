"""Tk window driven by the integration tests. Logs the input it receives, one event per line."""
import sys
import tkinter as tk

log = open(sys.argv[1], "w", buffering=1)

root = tk.Tk()
root.title("cu-test-target")
root.geometry("600x400+200+150")
entry = tk.Entry(root, font=("TkDefaultFont", 16))
entry.pack(fill="x")
canvas = tk.Canvas(root, bg="white", highlightthickness=0)
canvas.pack(fill="both", expand=True)


def on_return(_event):
    log.write(f"text {entry.get()}\n")
    entry.delete(0, "end")


def on_press(event):
    log.write(f"press {event.x_root} {event.y_root}\n")
    entry.focus_set()


entry.bind("<Return>", on_return)
canvas.bind("<ButtonPress-1>", on_press)
canvas.bind("<ButtonRelease-1>", lambda e: log.write(f"release {e.x_root} {e.y_root}\n"))
canvas.bind("<ButtonPress-3>", lambda e: log.write(f"right {e.x_root} {e.y_root}\n"))
canvas.bind("<Button-4>", lambda e: log.write("scroll up\n"))
canvas.bind("<Button-5>", lambda e: log.write("scroll down\n"))
root.after(200, entry.focus_force)
root.mainloop()
