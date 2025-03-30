import subprocess
import time

import cv2
import torch
from appium import webdriver
from appium.options.ios import XCUITestOptions
from ultralytics import YOLO

# Load YOLOv8 model (replace with a UI-trained model if available)
model = YOLO("yolov8n.pt")


def start_appium():
    try:
        subprocess.run(["pgrep", "-f", "appium"], check=True)
    except subprocess.CalledProcessError:
        subprocess.Popen(["appium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)


def start_ios_app():
    global driver
    options = XCUITestOptions()
    options.set_capability("platformName", "iOS")
    options.set_capability("deviceName", "iPhone 16")
    options.set_capability("platformVersion", "18.2")
    options.set_capability("app",
                           "/Users/pkamra/Library/Developer/Xcode/DerivedData/Runner-cznhzcttjkmrrggdodjdqsvdstuf/Build/Products/Debug-iphonesimulator/Runner.app")
    options.set_capability("automationName", "XCUITest")

    options.set_capability("noReset", True)
    options.set_capability("updatedWDABundleId", "com.speedy.speedyDeliveryPartner")
    options.set_capability("useNewWDA", True)
    options.set_capability("wdaStartupRetries", 14)
    options.set_capability("iosInstallPause", 8000)
    options.set_capability("wdaStartupRetryInterval", 20000)

    driver = webdriver.Remote("http://localhost:4723", options=options)


def capture_screenshot():
    screenshot_path = "ios_screenshot.png"
    driver.save_screenshot(screenshot_path)
    return screenshot_path


def detect_ui_elements(image_path):
    image = cv2.imread(image_path)
    results = model(image, imgsz=(1184, 2560), visualize=False)
    ui_elements = []

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = box.conf[0].item()
            class_id = int(box.cls[0])
            label = f"Element {class_id}"  # Replace with actual class mapping if available
            ui_elements.append({
                "bbox": [x1, y1, x2, y2],
                "label": label,
                "confidence": confidence
            })
    return ui_elements


def find_element_by_label(label, ui_elements):
    for element in ui_elements:
        if label.lower() in element["label"].lower():
            return element
    return None


def perform_action(element, action="tap"):
    if not element:
        return
    x = (element["bbox"][0] + element["bbox"][2]) // 2
    y = (element["bbox"][1] + element["bbox"][3]) // 2
    if action == "tap":
        driver.tap([(x, y)])
    elif action == "swipe":
        driver.swipe(x, y, x + 200, y, 500)
    elif action == "long_press":
        driver.long_press(x, y)


def run_automation(command):
    start_appium()
    start_ios_app()
    screenshot_path = capture_screenshot()
    ui_elements = detect_ui_elements(screenshot_path)
    action = "swipe" if "swipe" in command.lower() else "long_press" if "long press" in command.lower() else "tap"
    target_label = " ".join(command.split()[1:])
    element = find_element_by_label(target_label, ui_elements)
    perform_action(element, action)
    driver.quit()


if __name__ == "__main__":
    command = input("Enter command (e.g., 'tap Login button', 'swipe carousel'): ")
    run_automation(command)
