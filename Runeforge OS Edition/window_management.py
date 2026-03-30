import pywinauto
from pywinauto.application import Application

# Example: Notepad window management
def move_window(title, x, y):
    app = Application().connect(title_re=title)
    win = app.top_window()
    win.move_window(x, y)
    print(f"Moved window '{title}' to ({x},{y})")

def resize_window(title, width, height):
    app = Application().connect(title_re=title)
    win = app.top_window()
    win.resize(width, height)
    print(f"Resized window '{title}' to {width}x{height}")

def minimize_window(title):
    app = Application().connect(title_re=title)
    win = app.top_window()
    win.minimize()
    print(f"Minimized window '{title}'")

def maximize_window(title):
    app = Application().connect(title_re=title)
    win = app.top_window()
    win.maximize()
    print(f"Maximized window '{title}'")

def close_window(title):
    app = Application().connect(title_re=title)
    win = app.top_window()
    win.close()
    print(f"Closed window '{title}'")

if __name__ == "__main__":
    # Demo usage
    move_window("Notepad", 100, 100)
    resize_window("Notepad", 800, 600)
    minimize_window("Notepad")
    maximize_window("Notepad")
    close_window("Notepad")
