import re

import cv2
import os
import numpy as np
from appium import webdriver
from appium.options.ios import XCUITestOptions
from ultralytics import YOLO

from detect_compo import ip_region_proposal as detect_compo

# Initialize YOLOv8 model
model = YOLO()

# Set up Appium driver
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
    return driver.get_screenshot_as_png()


def preprocess_image(image):
    nparr = np.frombuffer(image, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def detect_objects(image):
    results = model(image)
    return results[0].boxes.data.cpu().numpy()


def detect_ui_elements(image):
    # Save the image temporarily
    temp_image_path = 'temp_screenshot.png'
    cv2.imwrite(temp_image_path, image)

    # Detect UI components and text
    output_root = 'output'
    compos = detect_compo.compo_detection(temp_image_path, output_root)
    # texts = detect_text(temp_image_path, output_root)

    # Combine components and texts
    elements = compos  # + texts

    # Clean up temporary files
    os.remove(temp_image_path)

    return elements


def parse_command(command):
    action = re.search(r'(tap|swipe|type|scroll)', command, re.IGNORECASE)
    target = re.search(r'on (.+)', command)
    return action.group(1).lower() if action else None, target.group(1) if target else None


def perform_action(action, target, objects):
    for obj in objects:
        if target.lower() in model.names[int(obj[5])].lower():
            x1, y1, x2, y2 = obj[:4]
            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            if action == 'tap':
                driver.execute_script("tap", {"x": center_x, "y": center_y})
                # TouchAction(driver).tap(x=center_x, y=center_y).perform()
            elif action == 'swipe':
                driver.execute_script("swipe", {"direction": "up"})
            elif action == 'type':
                driver.find_element_by_ios_predicate(f'label == "{target}"').send_keys("Sample text")
            elif action == 'scroll':
                driver.execute_script("scroll", {"direction": "up"})

            print(f"Performed {action} on {target}")
            return True

    print(f"Could not find {target}")
    return False


def main():
    commands = input("Enter your commands (separated by semicolons): ").split(';')

    for command in commands:
        action, target = parse_command(command.strip())
        if not action or not target:
            print(f"Invalid command: {command}")
            continue

        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            screenshot = capture_screenshot()
            image = preprocess_image(screenshot)
            objects = detect_objects(image)

            if perform_action(action, target, objects):
                break

            attempts += 1
            if attempts == max_attempts:
                print(f"Failed to perform {action} on {target} after {max_attempts} attempts")


if __name__ == "__main__":
    main()
