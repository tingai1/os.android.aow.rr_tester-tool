import pyautogui
import sys

def take_screenshot(filename):
    screenshot = pyautogui.screenshot()
    screenshot.save(filename)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python screenshot.py <filename>")
        sys.exit(1)
    filename = sys.argv[1]
    take_screenshot(filename)
