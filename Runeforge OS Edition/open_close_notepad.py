from pywinauto.application import Application
import time

# Open Notepad
app = Application().start("notepad.exe")
print("Notepad opened.")

# Wait for 5 seconds
time.sleep(5)

# Close Notepad
app.window(title_re=".*Notepad").close()
print("Notepad closed.")
