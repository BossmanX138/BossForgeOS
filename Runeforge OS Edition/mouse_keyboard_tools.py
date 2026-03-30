import pywinauto
from pywinauto import mouse
from pywinauto import keyboard
import argparse

# Mouse and Keyboard Advanced Actions

def move_mouse(x, y):
    mouse.move(coords=(x, y))
    print(f"Mouse moved to ({x}, {y})")

def click(x, y, button='left', double=False):
    if double:
        mouse.double_click(button=button, coords=(x, y))
        print(f"Double-clicked {button} at ({x}, {y})")
    else:
        mouse.click(button=button, coords=(x, y))
        print(f"Clicked {button} at ({x}, {y})")

def right_click(x, y):
    mouse.click(button='right', coords=(x, y))
    print(f"Right-clicked at ({x}, {y})")

def drag(start_x, start_y, end_x, end_y):
    mouse.press(coords=(start_x, start_y))
    mouse.move(coords=(end_x, end_y))
    mouse.release(coords=(end_x, end_y))
    print(f"Dragged mouse from ({start_x}, {start_y}) to ({end_x}, {end_y})")

def scroll(coords, wheel_dist):
    mouse.scroll(coords=coords, wheel_dist=wheel_dist)
    print(f"Scrolled at {coords} by {wheel_dist}")

def type_text(text):
    keyboard.send_keys(text)
    print(f"Typed text: {text}")

def press_keys(keys):
    keyboard.send_keys(keys)
    print(f"Pressed keys: {keys}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--move', nargs=2, type=int)
    parser.add_argument('--click', nargs=2, type=int)
    parser.add_argument('--double_click', nargs=2, type=int)
    parser.add_argument('--right_click', nargs=2, type=int)
    parser.add_argument('--drag', nargs=4, type=int)
    parser.add_argument('--scroll', nargs=3, type=int)  # x y wheel_dist
    parser.add_argument('--type', type=str)
    parser.add_argument('--press', type=str)
    args = parser.parse_args()
    if args.move:
        move_mouse(*args.move)
    if args.click:
        click(*args.click)
    if args.double_click:
        click(*args.double_click, double=True)
    if args.right_click:
        right_click(*args.right_click)
    if args.drag:
        drag(*args.drag)
    if args.scroll:
        scroll((args.scroll[0], args.scroll[1]), args.scroll[2])
    if args.type:
        type_text(args.type)
    if args.press:
        press_keys(args.press)
