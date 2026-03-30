import pywinauto
from pywinauto.application import Application
import argparse

# Clipboard Automation Tools

def copy_from_element(app_title, element_id):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.set_focus()
    elem.type_keys('^c')
    print(f"Copied from element {element_id} in {app_title}")

def paste_to_element(app_title, element_id):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.set_focus()
    elem.type_keys('^v')
    print(f"Pasted to element {element_id} in {app_title}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--copy', nargs=2)
    parser.add_argument('--paste', nargs=2)
    args = parser.parse_args()
    if args.copy:
        copy_from_element(args.copy[0], args.copy[1])
    if args.paste:
        paste_to_element(args.paste[0], args.paste[1])
