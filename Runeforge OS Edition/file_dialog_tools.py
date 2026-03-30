import pywinauto
from pywinauto.application import Application
import argparse

# File Dialog Automation Tools

def open_file_dialog(app_title):
    app = Application().connect(title_re=app_title)
    dlg = app.window(title_re="Open|Open File|Open.*")
    dlg.set_focus()
    dlg.child_window(title="Open", control_type="Button").click_input()
    print(f"Activated Open dialog in {app_title}")

def save_file_dialog(app_title):
    app = Application().connect(title_re=app_title)
    dlg = app.window(title_re="Save|Save As|Save.*")
    dlg.set_focus()
    dlg.child_window(title="Save", control_type="Button").click_input()
    print(f"Activated Save dialog in {app_title}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', type=str)
    parser.add_argument('--save', type=str)
    args = parser.parse_args()
    if args.open:
        open_file_dialog(args.open)
    if args.save:
        save_file_dialog(args.save)
