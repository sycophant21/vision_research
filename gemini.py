import json
import os
import re  # For regular expressions
import subprocess
import time

from PIL import Image
from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from google.generativeai import GenerativeModel, configure
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

# --- Configuration ---
GEMINI_API_KEY = ""  # Replace with your actual Gemini API key
RUNNER_APP_PATH = "/Users/pkamra/Library/Developer/Xcode/DerivedData/Runner-cznhzcttjkmrrggdodjdqsvdstuf/Build/Products/Debug-iphonesimulator/Runner.app"  # Replace with the actual path to your Runner.app
BUNDLE_IDENTIFIER = "com.speedy.speedyDeliveryPartner"  # Replace with your app's bundle identifier
SIMULATOR_DEVICE_NAME = "iPhone 16"  # Adjust as needed
SIMULATOR_OS_VERSION = "18.2"  # Adjust as needed
APPIUM_PORT = 4723  # Default Appium port

# --- Initialize Gemini ---
configure(api_key=GEMINI_API_KEY)
generation_config = {
    "temperature": 0.3,
    "top_p": 1.0,
    "top_k": 32,
    "max_output_tokens": 2048,
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]


model = GenerativeModel(model_name="gemini-2.0-flash", generation_config=generation_config,
                        safety_settings=safety_settings)



# --- Helper Functions ---
def start_ios_simulator(device_name=SIMULATOR_DEVICE_NAME, os_version=SIMULATOR_OS_VERSION):
    """Starts the iOS simulator."""
    try:
        subprocess.run(["xcrun", "simctl", "bootstatus", device_name, "-d"], check=True, capture_output=True)
        print(f"Simulator '{device_name}' is already running or successfully booted.")
    except subprocess.CalledProcessError:
        print(f"Booting simulator '{device_name}' with iOS {os_version}...")
        subprocess.run(["xcrun", "simctl", "create", device_name, "com.apple.CoreSimulator.SimDeviceType.iPhone-15",
                        f"com.apple.CoreSimulator.SimRuntime.iOS-{os_version.replace('.', '-')}"])
        subprocess.run(["xcrun", "simctl", "boot", device_name], check=True)
        time.sleep(30)  # Give the simulator some time to boot
        print(f"Simulator '{device_name}' booted.")
    except FileNotFoundError:
        print("Error: Xcode command-line tools not found. Please install them.")
        exit(1)


def setup_appium_driver(device_name, os_version, app_path, bundle_identifier):
    """Sets up the Appium driver."""
    options = XCUITestOptions()
    options.set_capability("platformName", "iOS")
    options.set_capability("deviceName", SIMULATOR_DEVICE_NAME)
    options.set_capability("platformVersion", SIMULATOR_OS_VERSION)
    options.set_capability("app", RUNNER_APP_PATH)
    options.set_capability("automationName", "XCUITest")
    options.set_capability("noReset", True)
    options.set_capability("updatedWDABundleId", BUNDLE_IDENTIFIER)
    options.set_capability("useNewWDA", True)
    options.set_capability("wdaStartupRetries", 14)
    options.set_capability("iosInstallPause", 8000)
    options.set_capability("wdaStartupRetryInterval", 20000)

    driver = webdriver.Remote(f"http://127.0.0.1:{APPIUM_PORT}", options=options)
    driver.implicitly_wait(10)  # Add implicit wait for elements to load
    return driver


def get_screenshot_base64(driver):
    """Gets the screenshot as a base64 encoded string using Appium."""
    try:
        return driver.get_screenshot_as_base64()
    except Exception as e:
        print(f"Error taking screenshot with Appium: {e}")
        return None


def get_screenshot(driver):
    """Gets the screenshot as a png file using Appium."""
    try:
        return driver.save_screenshot("ios_screenshot.png")

    except Exception as e:
        print(f"Error taking screenshot with Appium: {e}")
        return None


def get_screen_dimension(driver):
    try:
        return driver.get_window_size()
    except Exception as e:
        print(f"Error getting screen dimensions with Appium: {e}")
        return None


def perform_action(driver, action_type, element=None, text=None, coordinates=None, duration=None):
    """Performs an action using Appium."""
    try:
        if action_type == "tap":
            if coordinates:
                actions = ActionBuilder(driver)
                finger = PointerInput(interaction.POINTER_TOUCH, "finger")
                finger.create_pointer_move(x=coordinates["x"], y=coordinates["y"])
                finger.create_pointer_down()
                # actions.pointer_action.move_to_location(coordinates["x"], coordinates["y"])
                # actions.pointer_action.click()
                # actions.perform()
            elif element:
                el = find_element(driver, element)
                if el:
                    el.click()
                else:
                    print(f"Element '{element}' not found for tap action.")
                    return False
        elif action_type == "long_press" and coordinates and duration is not None:
            x, y = coordinates
            actions = ActionBuilder(driver)
            finger = PointerInput(interaction.POINTER_TOUCH, "finger")
            actions.pointer_action.move_to_location(finger, x, y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(duration=int(duration * 1000))
            actions.pointer_action.pointer_up()
            actions.perform()

        elif action_type == "swipe" and coordinates:
            start_x, start_y = coordinates[0]
            end_x, end_y = coordinates[1]
            finger = PointerInput(interaction.POINTER_TOUCH, name="finger")
            actions = ActionBuilder(driver)
            actions.pointer_action.move_to_location(start_x, start_y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(duration=100)
            actions.pointer_action.move_to_location(end_x, end_y)
            actions.pointer_action.pointer_up()
            actions.perform()
        elif action_type == "send_keys" and element and text:
            el = find_element(driver, element)
            if el:
                el.send_keys(text)
            else:
                print(f"Element '{element}' not found for send_keys action.")
                return False
        else:
            print(f"Unsupported action: {action_type}")
            return False
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Error performing action '{action_type}': {e}")
        return False


def find_element(driver, element_text):
    """Finds an element by its accessibility ID, name, or other suitable locator.
    This is a simplified example; in a real-world scenario, you might need more
    sophisticated element location strategies."""
    try:
        # Try finding by accessibility ID first (most reliable)
        el = driver.find_element(by=AppiumBy.ACCESSIBILITY_ID, value=element_text)
        return el
    except Exception:
        try:
            # If not found, try finding by name
            el = driver.find_element(by=AppiumBy.NAME, value=element_text)
            return el
        except:
            try:
                el = driver.find_element(by=AppiumBy.XPATH,
                                         value=f"//*[contains(@label, '{element_text}') or contains(@name, '{element_text}')]")
                return el
            except:
                return None  # Element not found


def parse_user_input(user_input):
    """Parses the user input into a structured format."""
    # Use regex to extract action, target, and qualifiers
    patterns = [
        (r"(tap|click)\s+on\s+(.+)", "tap"),
        (r"(long-press)\s+on\s+(.+)\s+for\s+(\d+\.?\d*)\s+seconds", "long_press"),
        (r"(swipe)\s+from\s+(.+)\s+to\s+(.+)", "swipe"),
        (r"(enter|type)\s+'(.+)'\s+in\s+the\s+(.+)", "send_keys"),
        (r"(enter|type)\s+(.+)\s+in\s+the\s+(.+)", "send_keys"),  # without quotes
    ]
    for pattern, action in patterns:
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            if action == "tap":
                return {"action": "tap", "element": match.group(2).strip()}
            elif action == "long_press":
                return {"action": "long_press", "element": match.group(2).strip(), "duration": float(match.group(3))}
            elif action == "swipe":
                start_coords = tuple(map(int, match.group(2).split(',')))
                end_coords = tuple(map(int, match.group(3).split(',')))
                return {"action": "swipe", "coordinates": (start_coords, end_coords)}
            elif action == "send_keys":
                return {"action": "send_keys", "text": match.group(2).strip().strip("'\""),
                        "element": match.group(3).strip()}
    # Default case: if no pattern matches, return the original input for Gemini to handle
    return {"action": "unknown", "text": user_input}


def analyze_steps(user_steps, current_screen_base64, screen_dim, language="en"):
    """Analyzes user-provided steps using Gemini to determine their status."""
    prompt = f"""You are an AI assistant that analyzes user steps for an iOS mobile application based on a screenshot.

The user will provide a list of steps in their preferred language. Your task is to:
1. Convert these steps into actionable steps that can be performed on an iOS simulator.  Use element labels, or text descriptions to identify UI elements and use the image provided and screen dimensions to infer the coordinates.
2. For each actionable step, determine if it has likely already been done on the provided screen, if it can or should be done on the current screen, or if it likely can't be done on the current screen and might be possible on a subsequent screen.
3.  If the step can be done, provide a JSON object with the action and the element to interact with.  
    - Provide the coordinates as a tuple (x, y) and if coordinates can not be inferred then return a suitable error.
    - Example: {{"action": "tap", "coordinates": "100,200"}}.
4. If the step has already been done, return status as "already_done".
5. If the step will be done on the next screen, return status as "will_be_done_next".
6. you understand json and only json, do not generate anything that is not json.
7. if the action can not be inferred or can not be performed then a reason parameter has to be present.

User Steps:
{user_steps}

Screen Dimension:
{screen_dim}

Provide your analysis in a JSON format like this:
[
  {{
    "original_step": "step 1",
    "action": "tap",
    "coordinates": "100,200"
    "status": "can_be_done"
  }}
]
"""

    try:
        response = model.generate_content(contents=[Image.open("ios_screenshot.png"), prompt])
        # print(current_screen_base64 is None)
        # response = client.messages.create(
        #     max_tokens=1024,
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": [
        #                 {
        #                     "type": "image",
        #                     "source": {
        #                         "type": "base64",
        #                         "media_type": "image/png",  # or image/png, etc.
        #                         "data": current_screen_base64
        #                     }
        #                 },
        #                 {
        #                     "type": "text",
        #                     "text": prompt
        #                 }
        #             ]
        #         }
        #     ],
        #     model="claude-3-5-sonnet-latest",
        # )
        # response = openai.ChatCompletion.create(
        #     model="deepseek/deepseek-chat-v3-0324:free",
        #     messages=[
        #         {"role": "user", "content": [
        #             {"type": "text", "text": prompt},
        #             {"type": "image_url", "image_url": f"data:image/png;base64,{current_screen_base64}"}
        #         ]}
        #     ]
        # )
        analysis_json_str = response.text#["choices"][0]["message"]["content"]
        analysis_json_str = re.sub(r'```json\n', '', analysis_json_str)
        analysis_json_str = re.sub(r'```', '', analysis_json_str)
        analysis_json_str = analysis_json_str.strip()
        try:
            analysis = json.loads(analysis_json_str)
            return analysis
        except json.JSONDecodeError:
            print(f"Error decoding Gemini response as JSON: {analysis_json_str}")
            return None
    except Exception as e:
        print(f"Error communicating with Gemini: {e}")
        return None


# --- Main Pipeline ---
if __name__ == "__main__":
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        print("Error: Please provide your Gemini API key in the configuration section.")
        exit(1)
    if not os.path.exists(RUNNER_APP_PATH):
        print(f"Error: Runner.app not found at '{RUNNER_APP_PATH}'. Please update the path.")
        exit(1)

    device_name = SIMULATOR_DEVICE_NAME
    start_ios_simulator(device_name, SIMULATOR_OS_VERSION)

    driver = setup_appium_driver(device_name, SIMULATOR_OS_VERSION, RUNNER_APP_PATH, BUNDLE_IDENTIFIER)

    try:
        while True:
            user_steps_input = input("Enter the steps you want to perform (or 'exit' to quit): ")
            if user_steps_input.lower() == 'exit':
                break

            current_screenshot_base64 = get_screenshot_base64(driver)
            current_screenshot = get_screenshot(driver)
            if not current_screenshot_base64:
                print("Could not take screenshot. Exiting.")
                break

            analysis_results = analyze_steps(user_steps_input, current_screenshot_base64, get_screen_dimension(driver))

            if analysis_results:
                print("\nAnalysis of Steps:")
                for item in analysis_results:
                    print(f"  Original Step: {item.get('original_step')}")
                    print(f"  Action: {item.get('action')}")
                    print(f"  Element: {item.get('element')}")
                    print(f"  Status: {item.get('status')}")
                    print(f"  Reason: {item.get('reason')} ")
                    print(f"  Coordinates: {item.get('coordinates')} ")

                    action = item.get('action')
                    if item.get('status') == 'can_be_done':
                        if action == 'tap':
                            if item.get('element') != 'None':
                                perform_action(driver, 'tap', element=item.get('element'))
                            elif item.get('coordinates'):
                                coordinates = item.get('coordinates').strip("()")
                                coordinates = coordinates.split(",")
                                perform_action(driver, 'tap', coordinates={"x": coordinates[0], "y": coordinates[1]})
                            else:
                                print("  Action 'tap' requires either 'element' or 'coordinates'.")
                        elif action == 'send_keys':
                            perform_action(driver, 'send_keys', element=item.get('element'), text=item.get('text'))
                        elif action == 'swipe':
                            perform_action(driver, 'swipe', coordinates=item.get('coordinates'))
                        elif action == 'long_press':
                            perform_action(driver, 'long_press', coordinates=item.get('coordinates'),
                                           duration=item.get('duration'))
                        elif action == 'unknown':
                            parsed_input = parse_user_input(item.get('text'))
                            if parsed_input['action'] != "unknown":
                                print(f"  Parsed step: {parsed_input}")
                                if parsed_input['action'] == 'tap':
                                    perform_action(driver, 'tap', element=parsed_input.get('element'))
                                elif parsed_input['action'] == 'send_keys':
                                    perform_action(driver, 'send_keys', element=parsed_input.get('element'),
                                                   text=parsed_input.get('text'))
                                elif parsed_input['action'] == 'swipe':
                                    perform_action(driver, 'swipe', coordinates=parsed_input.get('coordinates'))
                                elif parsed_input['action'] == 'long_press':
                                    perform_action(driver, 'long_press', coordinates=parsed_input.get('coordinates'),
                                                   duration=parsed_input.get('duration'))
                            else:
                                print(f"  Action '{item.get('text')}' is unknown and cannot be performed.")

            else:
                print("Could not analyze the steps.")
    finally:
        if driver:
            driver.quit()
        # Stop Appium Server (if started within the script) - Better to manage it separately
        # subprocess.run(["killall", "node"])
