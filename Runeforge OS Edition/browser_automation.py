"""
browser_automation.py

Provides browser automation for WindowsWorld agent using Selenium.
Supports opening browsers, navigating to URLs, clicking elements, typing, and scrolling.

Dependencies:
- selenium (pip install selenium)
- ChromeDriver or EdgeDriver (download and add to PATH)

Example usage:
    python browser_automation.py open_browser chrome
    python browser_automation.py navigate https://example.com
    python browser_automation.py click_by_selector "#submit"
    python browser_automation.py type_by_selector "#input" "hello world"
    python browser_automation.py scroll down
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import sys
import time

# Global driver instance
_driver = None

def get_driver(browser='chrome'):
    global _driver
    if _driver is not None:
        return _driver
    if browser == 'chrome':
        _driver = webdriver.Chrome()
    elif browser == 'edge':
        _driver = webdriver.Edge()
    else:
        raise ValueError('Unsupported browser')
    return _driver

def open_browser(browser='chrome'):
    driver = get_driver(browser)
    driver.maximize_window()
    print(f"Opened {browser} browser.")
    return True

def navigate(url):
    driver = get_driver()
    driver.get(url)
    print(f"Navigated to {url}")
    return True

def click_by_selector(selector):
    driver = get_driver()
    elem = driver.find_element(By.CSS_SELECTOR, selector)
    elem.click()
    print(f"Clicked element {selector}")
    return True

def type_by_selector(selector, text):
    driver = get_driver()
    elem = driver.find_element(By.CSS_SELECTOR, selector)
    elem.clear()
    elem.send_keys(text)
    print(f"Typed '{text}' into {selector}")
    return True

def scroll(direction='down', amount=500):
    driver = get_driver()
    if direction == 'down':
        driver.execute_script(f"window.scrollBy(0, {amount});")
    elif direction == 'up':
        driver.execute_script(f"window.scrollBy(0, -{amount});")
    print(f"Scrolled {direction} by {amount} pixels.")
    return True

def close_browser():
    global _driver
    if _driver:
        _driver.quit()
        _driver = None
        print("Browser closed.")
        return True
    return False

if __name__ == '__main__':
    # Simple CLI for demo/testing
    if len(sys.argv) < 2:
        print("Usage: python browser_automation.py <command> [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'open_browser':
        open_browser(sys.argv[2] if len(sys.argv) > 2 else 'chrome')
    elif cmd == 'navigate':
        navigate(sys.argv[2])
    elif cmd == 'click_by_selector':
        click_by_selector(sys.argv[2])
    elif cmd == 'type_by_selector':
        type_by_selector(sys.argv[2], sys.argv[3])
    elif cmd == 'scroll':
        scroll(sys.argv[2] if len(sys.argv) > 2 else 'down')
    elif cmd == 'close_browser':
        close_browser()
    else:
        print(f"Unknown command: {cmd}")
