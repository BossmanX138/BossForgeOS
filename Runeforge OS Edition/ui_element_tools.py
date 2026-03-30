import pywinauto
from pywinauto.application import Application
import argparse

# UI Element Interaction Tools

def click_element(app_title, element_id):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.click_input()
    print(f"Clicked element {element_id} in {app_title}")

def double_click_element(app_title, element_id):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.double_click_input()
    print(f"Double-clicked element {element_id} in {app_title}")

def right_click_element(app_title, element_id):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.right_click_input()
    print(f"Right-clicked element {element_id} in {app_title}")

def type_in_element(app_title, element_id, text):
    app = Application().connect(title_re=app_title)
    elem = app.window(auto_id=element_id)
    elem.set_focus()
    elem.type_keys(text, with_spaces=True)
    print(f"Typed in element {element_id} in {app_title}: {text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--click', nargs=2)
    parser.add_argument('--double_click', nargs=2)
    parser.add_argument('--right_click', nargs=2)
    parser.add_argument('--type', nargs=3)
    args = parser.parse_args()
    if args.click:
        click_element(args.click[0], args.click[1])
    if args.double_click:
        double_click_element(args.double_click[0], args.double_click[1])
    if args.right_click:
        right_click_element(args.right_click[0], args.right_click[1])
    if args.type:
        type_in_element(args.type[0], args.type[1], args.type[2])
