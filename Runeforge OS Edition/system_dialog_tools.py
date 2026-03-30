import pywinauto
from pywinauto.application import Application
import argparse

# System Dialog Automation Tools

def handle_alert(app_title, button_title="OK"):
    app = Application().connect(title_re=app_title)
    dlg = app.window(title_re=".*Alert|.*Dialog|.*Warning|.*Error|.*Confirm.*")
    dlg.set_focus()
    dlg.child_window(title=button_title, control_type="Button").click_input()
    print(f"Clicked '{button_title}' on system dialog in {app_title}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--alert', nargs=2)  # app_title, button_title
    args = parser.parse_args()
    if args.alert:
        handle_alert(args.alert[0], args.alert[1])
