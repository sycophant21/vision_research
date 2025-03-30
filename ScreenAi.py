import subprocess
import time

import torch
from PIL import Image
from appium import webdriver
from appium.options.ios import XCUITestOptions
from screenai.main import ScreenAI
from torchvision import transforms

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


def start_appium():
    try:
        subprocess.run(["pgrep", "-f", "appium"], check=True)
        print("Appium server is already running.")
    except subprocess.CalledProcessError:
        print("Starting Appium server...")
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

    print("Launching iOS app...")
    driver = webdriver.Remote("http://localhost:4723", options=options)
    time.sleep(3)


def capture_screenshot():
    screenshot_path = "ios_screenshot.png"
    driver.save_screenshot(screenshot_path)
    print(f"Screenshot captured: {screenshot_path}")
    return screenshot_path


def preprocess_text(text):
    # Instead of using the external BERT tokenizer directly
    # Let's create a simple tokenization that fits within ScreenAI's vocabulary range

    # Assuming ScreenAI expects token indices < 10000 based on your num_tokens parameter
    simple_vocab = {word: idx for idx, word in enumerate(set(text.lower().split()))}

    # Simple tokenization
    tokens = [simple_vocab.get(word, 0) for word in text.lower().split()]

    # Convert to tensor and ensure all indices are within range
    token_tensor = torch.tensor([token for token in tokens if token < 10000])

    # Pad or truncate to max_seq_len
    if len(token_tensor) < 512:
        padded_tensor = torch.nn.functional.pad(token_tensor, (0, 512 - len(token_tensor)))
    else:
        padded_tensor = token_tensor[:512]

    # Add batch dimension
    return padded_tensor.unsqueeze(0)


def preprocess_image(image_path):
    image = Image.open(image_path).convert('RGB')
    transform_tensor = transforms.Compose([
        transforms.Resize((224, 224)),  # Resize image
        transforms.ToTensor()  # Convert to tensor and normalize to [0, 1]
    ])

    # Add batch dimension with unsqueeze(0)
    return transform_tensor(image).unsqueeze(0)  # This adds the batch dimension


def detect_ui_elements(image_path):
    screen_ai = ScreenAI(
        num_tokens=10000,  # Adjust this value based on your vocabulary size
        max_seq_len=512,  # Adjust this value based on your maximum sequence length
        patch_size=16,
    )
    image = preprocess_image(image_path)
    print(image.shape)
    question = "What are the main UI elements on this screen?"
    text_input = preprocess_text(question)
    ui_elements = screen_ai(text_input, image)

    # with open("detected_ui.json", "w") as f:
    #     json.dump(ui_elements, f, indent=4)

    print(f"Detected {len(ui_elements)} UI elements.")
    return ui_elements


def tensor_to_text(tensor, vocab):

    if tensor.ndim == 2:  # If batch dimension exists, take first example
        tensor = tensor.squeeze(0)

    # Create reverse vocabulary (index -> word)
    index_to_word = {idx: word for word, idx in vocab.items()}

    # Convert indices back to words, ignoring padding (0 index)
    words = [index_to_word.get(idx, "[UNK]") for idx in tensor.tolist() if idx != 0]

    return " ".join(words)


def find_element_by_label(label, ui_elements):
    for element in ui_elements:
        if label.lower() in element.get("label", "").lower():
            return element
    return None


def perform_action(element, action="tap"):
    if not element:
        print("No matching UI element found.")
        return

    x = (element["bbox"][0] + element["bbox"][2]) // 2
    y = (element["bbox"][1] + element["bbox"][3]) // 2

    if action == "tap":
        driver.tap([(x, y)])
        print(f"Tapped on '{element.get('label', 'Unknown')}' at ({x}, {y})")
    elif action == "swipe":
        driver.swipe(x, y, x + 200, y, 500)
        print(f"Swiped from ({x}, {y}) to ({x + 200}, {y})")
    elif action == "long_press":
        driver.long_press(x, y)
        print(f"Long pressed on '{element.get('label', 'Unknown')}' at ({x}, {y})")


def run_automation(command):
    start_appium()
    start_ios_app()
    screenshot_path = capture_screenshot()
    ui_elements = detect_ui_elements(screenshot_path)

    if "swipe" in command.lower():
        action = "swipe"
    elif "long press" in command.lower():
        action = "long_press"
    else:
        action = "tap"

    target_label = " ".join(command.split()[1:])  # Extract full label
    #element = find_element_by_label(target_label, ui_elements)

    #perform_action(element, action)
    driver.quit()
    print("Test automation completed.")


if __name__ == "__main__":
    command = input("Enter your command (e.g., 'tap Login button', 'swipe carousel'): ")
    run_automation(command)
