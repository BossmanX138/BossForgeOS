import ctypes
import win32clipboard

def set_clipboard(text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text)
    win32clipboard.CloseClipboard()
    print("Clipboard set.")

def get_clipboard():
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData()
    win32clipboard.CloseClipboard()
    print(f"Clipboard contents: {data}")
    return data

if __name__ == "__main__":
    set_clipboard("Hello from script!")
    get_clipboard()
