import json
import os
import time
import pandas as pd
from dotenv import dotenv_values
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from A11yDetector.a11y_detector import is_base64_image
from A11yDetector.helper import check_url_status
from ElementExtraction.extract_related_elements import extract_related_visual_elements, extract_info_relation_elements, \
    extract_original_screenshot, extract_and_linearize_tables, extract_sensory_elements, \
    check_orientation_and_transform, extract_input_elements, extract_link_form_screenshot, find_autoplay_audio_elements, \
    extract_contrast_related_elements, extract_text_resizing, extract_img_urls, extract_text_blocks_with_details, \
    extract_zoomed_screenshot, extract_text_reflow, extract_text_spacing_screenshots, extract_meta_refresh, \
    take_screenshots_and_compare, capture_updating_moving_element, extract_specific_role_elements, \
    extract_headings_under_sections, extract_page_title, extract_links, extract_multiple_ways, \
    extract_form_input_elements, extract_headings_with_siblings, extract_location_related_information, \
    extract_target_size, extract_lang_attr, find_related_screenshots, extract_event_handlers, \
    extract_change_on_request_element, extract_form_elements, extract_name_role_elements
from consts import JSON_FORMAT, TEMP_FILE_FOLDER

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '..', '..', 'A11yDetector', '.env')
config = dotenv_values(env_path)
client = OpenAI(api_key=config["OPENAI_API_KEY"])


def wait_for_load(driver):
    """ Wait for the page to fully load by checking the loadEventEnd timing. """
    start_time = time.time()
    while True:
        timing = driver.execute_script("""
            return window.performance.timing;
        """)
        if timing['loadEventEnd'] > 0:
            return timing['loadEventEnd'] - timing['navigationStart']
        if time.time() - start_time > 30:
            raise Exception("Timed out waiting for page load.")
        time.sleep(0.5)


def prepare_driver(url: str):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(url)
    wait_for_load(driver)
    return driver


def send_request_to_model(model_name: str, user_message):
    """ Send a request to the OpenAI model with the specified messages. """
    completion = client.chat.completions.create(model=model_name,
                                                response_format=JSON_FORMAT,
                                                messages=[{"role": "user", "content": user_message}],
                                                temperature=0.0)
    return completion


def read_wcag_criterion_and_urls_from_excel(file_path, start_index=None, end_index=None):
    """
    Read the list of values from the 'WCAG Criterion' and 'URL' columns in an Excel file.

    Parameters:
        file_path (str): The path to the Excel file.
        start_index (int, optional): The starting index for reading data. Defaults to None.
        end_index (int, optional): The ending index for reading data. Defaults to None.

    Returns:
        tuple: A tuple containing two lists - wcag_criteria and url_list.
    """
    # Load the Excel file into a DataFrame
    df = pd.read_excel(file_path)

    # Check if both 'WCAG Criterion' and 'URL' columns exist in the DataFrame
    if 'WCAG Criterion' in df.columns and 'URL' in df.columns:
        # If start_index or end_index is provided, slice the DataFrame accordingly
        if start_index is not None or end_index is not None:
            df = df.iloc[start_index:end_index+1]

        # Extract the 'WCAG Criterion' and 'URL' columns as lists
        wcag_criteria = df['WCAG Criterion'].dropna().tolist()
        url_list = df['URL'].dropna().tolist()
        return wcag_criteria, url_list
    else:
        raise ValueError("The columns 'WCAG Criterion' and/or 'URL' were not found in the Excel file.")


def save_results_to_json(results, index, output_folder):
    """Save the results to a JSON file under the Results folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    file_name = os.path.join(output_folder, f"{index}.json")
    with open(file_name, 'w') as json_file:
        json.dump(results, json_file, indent=8)


def non_text_content_violation_extraction(driver: webdriver):
    """
    WCAG 1.1.1 Non-text Content
    """
    visual_elements = extract_related_visual_elements(driver)
    user_message = ("You will be provided with visual elements from a webpage for compliance with WCAG SC 1.1.1. "
                    "Focus specifically on identifying any issues related to non-text content. The related "
                    "information for you to assess begins after the dashed line. \n"
                    "----------------------------------------\n")
    user_message + "\n".join(
        f"{key}: {value}" for key, value in visual_elements.items()
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def info_relation_violation_extraction(driver: webdriver):
    """
    WCAG 1.3.1 Info and Relationships
    """
    relation_elements = extract_info_relation_elements(driver)
    screenshot_list = extract_original_screenshot(driver)
    user_message = [{"type": "text",
                     "text": (
                         "You will be provided with related elements from a webpage to assess compliance with WCAG SC "
                         "1.3.1. Focus solely on this criterion and determine whether the elements conform to it, "
                         "describing any issues if found."
                         "The relevant information for your assessment begins after the dashed line. \n"
                         "--------------------------------- \n"
                     )}]
    for key, elements in relation_elements.items():
        user_message.append({"type": "text", "text": f"{key}: {elements}"})
    for screenshot in screenshot_list:
        user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def meaningful_sequence_violation_extraction(driver: webdriver):
    """
    WCAG 1.3.2 Meaningful Sequence
    """
    sequence_list = extract_and_linearize_tables(driver)
    user_message = (
        "You will be provided with related elements from a webpage to determine if there is any violation of WCAG "
        "SC 1.3.2. Please focus solely on this criterion. Identify whether the elements comply with this "
        "WCAG criterion and describe any issues found.\n"
        "The relevant information for your assessment begins after the dashed line. \n"
        "--------------------------------- \n"
    )
    combined_data = [{'type': 'original_table', 'content': item['original'], 'linearized': item['linearized']}
                     for item in sequence_list[0]]
    combined_data.extend([{'type': 'whitespace', 'content': ws} for ws in sequence_list[1]])
    combined_data.extend([{'type': 'rearranged', 'content': el} for el in sequence_list[2]])

    for item in combined_data:
        if item['type'] == 'original_table':
            user_message += "Original table:\n"
            user_message += f"{item['content']}\n"
            user_message += "Linearized table:\n"
            user_message += f"{item['linearized']}\n"
            user_message += "-------------\n"
        elif item['type'] == 'whitespace':
            user_message += "White space characters:\n"
            user_message += f"{item['content']}\n"
            user_message += "-------------\n"
        elif item['type'] == 'rearranged':
            user_message += "Elements that might be rearranged:\n"
            user_message += f"{item['content']}\n"
            user_message += "-------------\n"

    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def sensory_characteristic_violation_extraction(driver: webdriver):
    """
    WCAG 1.3.3 Sensory Characteristics
    """
    user_message = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 1.3.3. "
        "These elements have been identified by an upstream agent that detected sensory characteristics."
        "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific WCAG "
        "criterion,"
        "providing a description of any issues found.\n"
        "The relevant information for your assessment begins after the dashed line. \n"
        "--------------------------------- \n"
    )
    sensory_elements = extract_sensory_elements(driver)
    combined_data = [{'type': 'other_sensory', 'content': item} for item in sensory_elements.get('other_sensory', [])]
    combined_data.extend(
        [{'type': 'color_sensory', 'content': item} for item in sensory_elements.get('color_sensory', [])])
    for item in combined_data:
        if item['type'] == 'other_sensory':
            user_message += "Elements with sensory characteristics (other than color):\n"
        elif item['type'] == 'color_sensory':
            user_message += "Elements with color sensory characteristics:\n"
        user_message += f"{item['content']}\n"
        user_message += "-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def orientation_violation_extraction(driver: webdriver):
    """
    WCAG 1.3.4 Orientation
    """
    orientation_elements = check_orientation_and_transform(driver)
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with related elements from a webpage to determine if there is any violation of "
                "WCAG SC 1.3.4. Focus solely on this criterion. Your task is to determine whether the elements comply "
                "with the specific WCAG"
                "criterion, providing a description of any issues found."
                "The relevant information for your assessment begins after the dashed line. \n"
                "--------------------------------- \n"
            )
        },
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{orientation_elements['landscape']}"}},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{orientation_elements['portrait']}"}}
    ]
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def identify_input_purpose_violation_extraction(driver: webdriver):
    """
    WCAG 1.3.5 Identify Input Purpose
    """
    input_elements = extract_input_elements(driver)
    user_message = (
        "You will be provided with related elements from a webpage to determine if there is any violation of WCAG SC "
        "1.3.5. Focus solely on this criterion. Your task is to determine whether the elements comply with the specific"
        "WCAG criterion, providing a description of any issues found."
        "The relevant information for your assessment begins after the dashed line. \n"
        "--------------------------------- \n"
    )
    for key, value in input_elements.items():
        user_message += f"{key}: {value}\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def use_of_color_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.1 Use of Color
    """
    link_form_screenshots = extract_link_form_screenshot(driver)
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with related elements from a webpage to determine if there is any violation of "
             "WCAG SC 1.4.1. Focus solely on this criterion. Your task is to determine whether the elements comply "
             "with the specific WCAG"
             "criterion, providing a description of any issues found."
             "The relevant information for your assessment begins after the dashed line. \n"
             "--------------------------------- \n"
         )
         }
    ]
    combined_data = [{'type': 'link', 'content': link} for link in link_form_screenshots.get('links', [])]
    combined_data.extend([{'type': 'form', 'content': form} for form in link_form_screenshots.get('forms', [])])
    for item in combined_data:
        if item['type'] == 'link':
            user_message.append({"type": "text", "text": "Link screenshots:\n"})
        elif item['type'] == 'form':
            user_message.append({"type": "text", "text": "Form screenshots:\n"})
        user_message.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['content']}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def audio_control_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.2 Audio Control
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with audio elements from a webpage to assess compliance with WCAG SC 1.4.2. "
                "Please focus only on this criterion. Your task is to determine whether the audio elements comply "
                "with WCAG SC 1.4.2 and describe any issues identified."
                "The related information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    audio_elements = find_autoplay_audio_elements(driver)
    if 'short' in audio_elements.keys():
        for html_element, imgs in audio_elements['short'].items():
            user_message.append({
                "type": "text",
                "text": f"short-audio: {html_element} \n"
            })
    if 'long' in audio_elements.keys():
        for html_element, imgs in audio_elements['long'].items():
            user_message.append({
                "type": "text",
                "text": f"long-audio: {html_element} \n"
            })
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imgs}"}}
            )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def contrast_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.3 Contrast
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with text elements from a webpage"
                "to assess compliance with WCAG SC 1.4.3. "
                "Please focus solely on this criterion. Determine whether the elements comply with WCAG SC 1.4.3 and "
                "describe"
                "any issues identified.\n"
            )
        }
    ]
    contrast_related_elements, elements_with_background_image = extract_contrast_related_elements(driver)
    # Combine data from both parameters
    text_elements = [{'type': 'text', 'content': text} for text in contrast_related_elements]
    image_elements = [{'type': 'image', 'text': key, 'image': value} for key, value in
                      elements_with_background_image.items()]
    combined_data = text_elements + image_elements
    for item in combined_data:
        if item['type'] == 'text':
            user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})
    # Add image elements together
    user_message.append({"type": "text", "text": "\nImage elements (with background "
                                                 "images):\n----------------------\n"})
    for item in combined_data:
        if item['type'] == 'image':
            user_message.append({"type": "text", "text": f"{item['text']}\n"})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['image']}"}})
            user_message.append({"type": "text", "text": "\n-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def resize_text_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.4 Resize Text
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with related elements to assess compliance with WCAG SC "
                "1.4.4."
                "Focus exclusively on this criterion. Your task is to determine whether the elements comply with WCAG "
                "SC 1.4.4"
                "and describe any issues found.\n"
            )
        }
    ]
    extract_original_screenshot(driver)
    text_resizing_dict = extract_text_resizing(driver)
    if 'meta' in text_resizing_dict.keys():
        user_message.append({"type": "text", "text": f"Meta elements: {text_resizing_dict['meta']} \n"})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_resizing_dict['original']}"}})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_resizing_dict['zoomed']}"}})
    if len(text_resizing_dict['input_elements']) != 0:
        user_message.append({"type": "text", "text": "Input elements:"})
        for input_element in text_resizing_dict['input_elements']:
            for key, value in input_element.items():
                user_message.append({"type": "text", "text": f"{key} - {value}"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def use_of_image_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.5 Use of Image
    """
    image_text_elements = extract_img_urls(driver)
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with image URLs from a webpage. Your task is to assess whether these images "
                "comply with WCAG SC 1.4.5, focusing only on this specific criterion. \n"
            )
        }
    ]
    valid_extensions = ['png', 'jpeg', 'gif', 'webp', 'jpg']
    # Filter out image URLs that return a status code of 200
    valid_image_urls = {
        url for url in image_text_elements
        if (any(url.lower().endswith(ext) for ext in valid_extensions) or is_base64_image(url))
           and check_url_status(url) == 200
    }
    for url in valid_image_urls:
        user_message.append({"type": "image_url", "image_url": {"url": url}})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def contrast_enhanced_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.6 Contrast Enhanced
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with text elements from a webpage to assess compliance with WCAG SC 1.4.6. "
                "Focus exclusively on this criterion. Your task is to determine whether the text elements comply with "
                "WCAG SC 1.4.6 and describe any issues found."
                "The relevant information for your assessment begins after the dashed line. \n"
                "--------------------------------- \n"
            )
        }
    ]
    contrast_related_elements, elements_with_background_image = extract_contrast_related_elements(driver)
    # Combine data from both parameters
    text_elements = [{'type': 'text', 'content': text} for text in contrast_related_elements]
    image_elements = [{'type': 'image', 'text': key, 'image': value} for key, value in
                      elements_with_background_image.items()]
    combined_data = text_elements + image_elements
    for item in combined_data:
        if item['type'] == 'text':
            user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})
    # Add image elements together
    user_message.append({"type": "text", "text": "\nImage elements (with background "
                                                 "images):\n----------------------\n"})
    for item in combined_data:
        if item['type'] == 'image':
            user_message.append({"type": "text", "text": f"{item['text']}\n"})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['image']}"}})
            user_message.append({"type": "text", "text": "\n-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def visual_presentation_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.8 Visual Presentation
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with blocks of text from a webpage to determine if there is any violation of WCAG "
             "SC 1.4.8. Focus solely on this criterion. Your task is to determine whether the elements comply with "
             "the specific WCAG criterion,"
             "providing a description of any issues found.\n"
         )
         }
    ]
    extract_zoomed_screenshot(driver)
    text_blocks = extract_text_blocks_with_details(driver)
    user_message.append(
        {"type": "text", "text": "The related information about the blocks of text is below:\n"})

    for block in text_blocks:
        message_text = ""
        for key, value in block.items():
            if key != "screenshot":
                message_text += f"{key}: {value}\n"
            else:
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{block['screenshot']}"}})
        user_message.append({"type": "text", "text": message_text})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def reflow_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.10 Reflow
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with two screenshots to determine if there is any violation of WCAG SC 1.4.10. "
                "Your task is to determine whether the elements comply with WCAG SC 1.4.10 and describe any issues "
                "found.\n "
                "The related information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    extract_original_screenshot(driver)
    text_reflow_dict = extract_text_reflow(driver)
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_reflow_dict['original']}"}})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_reflow_dict['reflow']}"}})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def text_spacing_violation_extraction(driver: webdriver):
    """
    WCAG 1.4.12 Text Spacing
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with several screenshots to determine if there is any violation "
             "of WCAG SC 1.4.12. Focus solely on this criterion. Determine whether the elements comply with the "
             "specific"
             "WCAG criterion, providing a description of any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    text_spacing_elements = extract_text_spacing_screenshots(driver)
    user_message.append({"type": "text", "text": "The screenshots are below:\n"})

    for text_spacing in text_spacing_elements:
        user_message.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_spacing}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def timing_adjustable_violation_extraction(driver: webdriver):
    """
    WCAG 2.2.1 Timing Adjustable
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with meta elements and two consecutive screenshots from a webpage to determine if "
             "there is any violation of WCAG SC 2.2.1."
             "Please focus solely on this criterion. Your task is to determine whether the elements comply with "
             "WCAG SC 2.2.1 and describe any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )
         }
    ]
    meta_element_redirection = extract_meta_refresh(driver)
    screenshots = take_screenshots_and_compare(driver, duration=20)
    timing_adjustable_list = [meta_element_redirection, screenshots]
    if len(timing_adjustable_list[0]) != 0:
        user_message.append({"type": "text", "text": f"meta elements: {timing_adjustable_list[0]} \n"})
    if timing_adjustable_list[1]:
        if len(timing_adjustable_list[1]) != 0:
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{timing_adjustable_list[1][0]}"}})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{timing_adjustable_list[1][1]}"}})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def pause_stop_hide_violation_extraction(driver: webdriver):
    """
    WCAG 2.2.2 Pause, Stop, Hide
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC "
             "2.2.2."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG criterion,"
             "providing a description of any issues found.\n"
             "The relevant information for your assessment begins after the dashed line.\n"
             "--------------------------------- \n"
         )
         }
    ]
    moving_and_updating = capture_updating_moving_element(driver)
    combined_data = [{'type': 'blink', 'content': item} for item in moving_and_updating.get('blink', [])]
    combined_data.extend([{'type': 'marquee', 'content': item} for item in moving_and_updating.get('marquee', [])])
    combined_data.extend(
        [{'type': 'moving_image', 'content': item} for item in moving_and_updating.get('moving_images', [])])
    combined_data.extend(
        [{'type': 'updating_image', 'content': item} for item in moving_and_updating.get('updating_images', [])])
    for item in combined_data:
        if item['type'] == 'moving_image':
            user_message.append({"type": "text", "text": "Screenshots taken 5 seconds apart:\n"})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['content']}"}})
        elif item['type'] == 'updating_image':
            user_message.append({"type": "text", "text": "Screenshots indicating text updates:\n"})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['content']}"}})
        else:
            element_type = item['type'].replace('_', ' ').capitalize()
            user_message.append({"type": "text", "text": f"{element_type} elements:\n"})
            user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def bypass_block_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.1 Bypass Blocks
    """
    user_message = (
        "You will be provided with several elements from a webpage to determine if there is any violation of WCAG SC "
        "2.4.1. Focus solely on this criterion. Your task is to determine whether the elements comply with the "
        "specific WCAG criterion, providing a description of any issues found.\n"
        "The relevant information for your assessment begins after the dashed line. \n"
        "--------------------------------- \n"
    )
    bypass_blocks = extract_specific_role_elements(driver)
    combined_data = [{'type': key, 'content': element} for key, elements in bypass_blocks.items() for element in
                     elements]
    for item in combined_data:
        user_message += f"{item['type'].capitalize()} elements:\n"
        user_message += f"{item['content']}\n"
        user_message += "-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def page_title_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.2 Page Title
    """
    page_title_dict = extract_page_title(driver)
    user_message = (
        "You will receive the page title along with some portions of a webpage. Your task is to determine if "
        "there is any violation of WCAG SC 2.4.2. Focus solely on this criterion. Identify whether the elements "
        "comply with the specific WCAG criterion and provide a description of any issues found. \n"
        "The relevant information for your assessment begins after the dashed line. \n"
        "------------------ \n"
        f"Title: {page_title_dict['title']} \n"
        f"Portion text: {page_title_dict['portion_text']} \n"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def link_purpose_context_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.4 Link Purpose (In Context)
    """
    link_related_elements = extract_links(driver)
    user_message = (
        "You will be provided with link elements, along with their ancestors and siblings (if any), from a webpage to "
        "assess for any violations of WCAG SC 2.4.4. Determine whether the elements comply with the specific WCAG "
        "criterion and describe any issues identified.\n"
    )
    for element in link_related_elements:
        user_message += f"{element}\n-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def multiple_ways_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.5 Multiple Ways
    """
    multiple_ways_screenshots = extract_multiple_ways(driver)
    user_message = [
        {
            "type": "text",
            "text": ("You will be provided with two screenshots from a webpage to determine if there is any violation "
                     "of WCAG SC 2.4.5. Please focus solely on this criterion. Your task is to determine whether the "
                     "elements comply with WCAG SC 2.4.5 and describe any issues found.\n"
                     )
        },
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{multiple_ways_screenshots['initial']}"}},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{multiple_ways_screenshots['bottom']}"}}
    ]
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def headers_and_labels_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.6 Headers and Labels
    """
    form_input_dict = extract_form_input_elements(driver)
    heading_elements = extract_headings_with_siblings(driver)
    user_message = (
                "You will be provided with input and heading elements from a webpage to assess compliance with WCAG "
                "SC 2.4.6. Focus solely on this criterion. Your task is to determine whether the elements comply with "
                "WCAG SC 2.4.6 and describe any issues identified."
                "The relevant information for your assessment begins after the dashed line. \n"
                "--------------------------------- \n"
            )
    heading_elements = [{'type': 'heading', 'content': heading} for heading in heading_elements]
    form_labels = [{'type': 'form_label', 'content': label} for label in form_input_dict.get('forms', [])]
    input_labels = [{'type': 'input_label', 'content': label} for label in form_input_dict.get('inputs', [])]
    combined_data = heading_elements + form_labels + input_labels
    # Add heading elements
    user_message += "\nHeading elements:\n"
    user_message += "----------------------\n"
    for item in combined_data:
        if item['type'] == 'heading':
            user_message += f"{item['content']}\n-------------\n"
    # Add form labels
    user_message += "\nLabels within form elements:\n"
    user_message += "----------------------\n"
    for item in combined_data:
        if item['type'] == 'form_label':
            user_message += f"{item['content']}\n-------------\n"
    # Add input labels
    user_message += "\nLabels as siblings of input elements:\n"
    user_message += "----------------------\n"
    for item in combined_data:
        if item['type'] == 'input_label':
            user_message += f"{item['content']}\n-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def location_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.8 Location
    """
    location_related_elements = extract_location_related_information(driver)
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with related elements from a webpage to determine if there is any "
             "violation of WCAG SC 2.4.8. Focus solely on this criterion. Your task is to determine whether the "
             "elements comply with the specific WCAG criterion,"
             "providing a description of any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{location_related_elements['screenshot']}"}},
        {"type": "text", "text": f"Title information: {location_related_elements['title']}"}
    ]
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def link_purpose_link_only_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.9 Link Purpose (Link Only)
    """
    link_related_elements = extract_links(driver)
    user_message = (
        "You will be provided with link elements from a webpage to determine if there is any violation of WCAG SC "
        "2.4.9."
        "Please focus exclusively on this criterion. Determine whether the elements comply with WCAG SC 2.4.9 and "
        "describe any issues identified.\n"
        "The relevant information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    for element in link_related_elements:
        user_message += f"{element}\n-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def section_headings_violation_extraction(driver: webdriver):
    """
    WCAG 2.4.10 Section Headings
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with related elements about headings from a webpage to "
                "assess compliance with WCAG SC 2.4.10. Focus solely on this criterion and identify any violations."
            )
        }
    ]
    heading_under_section_elements = extract_headings_under_sections(driver)
    screenshot_list = extract_original_screenshot(driver)
    headings_data = [{'type': 'heading', 'content': heading} for heading in heading_under_section_elements]
    screenshots_data = [{'type': 'screenshot', 'content': screenshot} for screenshot in screenshot_list]
    combined_data = headings_data + screenshots_data
    for item in combined_data:
        if item['type'] == 'heading':
            heading = item['content']
            section_number = heading_under_section_elements.index(heading) + 1
            if heading['no_heading']:
                user_message.append({
                    "type": "text",
                    "text": f"Section {section_number} does not have a heading.\n-------------\n"
                })
            else:
                user_message.append({
                    "type": "text",
                    "text": f"Section {section_number} has a heading: {heading['headings']}\n"
                })
        elif item['type'] == 'screenshot':
            screenshot = item['content']
            user_message.append({
                "type": "text",
                "text": f"The screenshots of the webpage are provided below:\n"
            })
            user_message.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot}"}
            })
            user_message.append({
                "type": "text",
                "text": "-------------\n"
            })
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def target_size_enhanced_violation_extraction(driver: webdriver):
    """
    WCAG 2.5.5 Target Size Enhanced
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with targets from a webpage to determine "
                "if there is any violation of WCAG SC 2.5.5. Focus solely on this criterion. Determine whether the "
                "elements comply with the specific WCAG criterion,"
                "providing a description of any issues found.\n"
                "The relevant information for your assessment begins after the dashed line. \n"
                "--------------------------------- \n"
            )
        }
    ]
    target_size_elements = extract_target_size(driver)
    combined_data = [{'type': 'small_element_44', 'content': element} for element in
                     target_size_elements.get('small_elements_44', [])]
    for item in combined_data:
        element = item['content']
        user_message.append({"type": "text", "text": f"Tag: {element['tag']}\n"})
        user_message.append({"type": "text", "text": "Full screenshot:\n"})
        user_message.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['full']}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def target_size_minimum_violation_extraction(driver: webdriver):
    """
    WCAG 2.5.8 Target Size Minimum
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with targets from a webpage to determine "
                "if there is any violation of WCAG SC 2.5.8. Focus solely on this criterion. Determine whether the "
                "elements comply with the specific WCAG criterion,"
                "providing a description of any issues found.\n"
                "The relevant information for your assessment begins after the dashed line. \n"
                "--------------------------------- \n"
            )
        }
    ]
    target_size_elements = extract_target_size(driver)
    combined_data = [{'type': 'small_element', 'content': element} for element in
                     target_size_elements.get('small_elements', [])]
    for item in combined_data:
        element = item['content']
        user_message.append({"type": "text", "text": f"Tag: {element['tag']}\n"})
        user_message.append({"type": "text", "text": "Cropped screenshot:\n"})
        user_message.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['cropped']}"}})
        user_message.append({"type": "text", "text": "Full screenshot:\n"})
        user_message.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['full']}"}})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def language_violation_extraction(driver: webdriver):
    """
    WCAG 3.1.1 Language of Page; WCAG 3.1.2 Language of Parts
    """
    lang_attr_dict = extract_lang_attr(driver)
    page_title_dict = extract_page_title(driver)
    user_message = (
        "You will be provided with HTML elements that have a lang attribute from a webpage, as well as "
        "relevant portion text, to determine if there is any violation of WCAG SC 3.1.1 and SC 3.1.2. "
        "Please focus only on these criteria. Determine whether the elements comply with the specific WCAG criterion, "
        "and provide a description of any issues if found.\n"
        "The related information for you to assess starts after the dashed line. \n"
        "------------------ \n"
    )
    user_message += f"Portion text: {page_title_dict['portion_text']} \n"
    if len(lang_attr_dict["lang_only"]) > 0:
        user_message += f"html elements with lang attribute: {lang_attr_dict["lang_only"]} \n"
    if len(lang_attr_dict["lang_and_xml"]) > 0:
        user_message += f"html elements with lang and xml:lang attributes: {lang_attr_dict["lang_and_xml"]} \n"
    if len(lang_attr_dict["lang_and_xml"]) == 0 and len( lang_attr_dict["lang_only"]) == 0:
        user_message += "Could not find the lang attribute on this page. \n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def abbreviation_violation_extraction(driver: webdriver):
    """
    WCAG 3.1.4 Abbreviations
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.1.4."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    extract_original_screenshot(driver)
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    user_message.append({"type": "text", "text": "The screenshots are below:\n"})
    for screenshot in initial_screenshot_str:
        user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def on_input_violation_extraction(driver: webdriver):
    """
    WCAG 3.2.2 On Input
    """
    special_input_dict, other_input_dict = extract_event_handlers(driver)
    user_message = (
        "You will be provided with HTML elements and their associated event handler functions. Determine whether the "
        "elements comply with the specific WCAG criterion 3.2.2 On Input, providing a description of any issues "
        "found.\n"
    )
    combined_data = [
                        {"type": "special", "html": html, "function": func}
                        for html, func in special_input_dict.items()
                    ] + [
                        {"type": "other", "html": html, "function": func}
                        for html, func in other_input_dict.items()
                    ]
    special_inputs = [item for item in combined_data if item["type"] == "special"]
    other_inputs = [item for item in combined_data if item["type"] == "other"]
    if special_inputs:
        user_message += ("The following elements are radio buttons, checkboxes, and select lists with onclick "
                         "events:\n")
        for item in special_inputs:
            user_message += (
                f"Element: {item['html']}\n"
                f"Function: {item['function']}\n"
                "------------------\n"
            )

    if other_inputs:
        user_message += "The following elements are other input types with onchange events:\n"
        for item in other_inputs:
            user_message += (
                f"Element: {item['html']}\n"
                f"Function: {item['function']}\n"
                "------------------\n"
            )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def change_on_request_violation_extraction(driver: webdriver):
    """
    WCAG 3.2.5 Change on Request
    """
    user_message = (
        "You need to detect violations of WCAG SC 3.2.5 based on the provided, related elements. Determine whether the "
        "elements comply with the specific WCAG criterion, providing a description of any issues found.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    onclick_event, onblur_event = extract_change_on_request_element(driver)
    combined_data = [
                        {"type": "onclick", "html": html, "function": func}
                        for html, func in onclick_event.items()
                    ] + [
                        {"type": "onblur", "html": html, "function": func}
                        for html, func in onblur_event.items()
                    ]
    onclick_elements = [item for item in combined_data if item["type"] == "onclick"]
    onblur_elements = [item for item in combined_data if item["type"] == "onblur"]

    if onclick_elements:
        user_message += "The following elements have onclick functions:\n"
        for item in onclick_elements:
            user_message += (
                f"Element: {item['html']}\n"
                f"Function: {item['function']}\n"
                "------------------\n"
            )

    if onblur_elements:
        user_message += "The following input elements have onblur functions:\n"
        for item in onblur_elements:
            user_message += (
                f"Element: {item['html']}\n"
                f"Function: {item['function']}\n"
                "------------------\n"
            )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def error_identification_violation_extraction(driver: webdriver):
    """
    WCAG 3.3.1 Error Identification
    """
    extract_original_screenshot(driver)
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.3.1."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    user_message.append({"type": "text", "text": "The screenshots are below:\n"})

    for screenshot in initial_screenshot_str:
        user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def labels_instructions_violation_extraction(driver: webdriver):
    """
    WCAG 3.3.2 Labels or Instructions
    """
    user_message = (
        "You will be provided with form elements from a webpage. Your task is to assess compliance with WCAG SC 3.3.2, "
        "focusing solely on this criterion. \n"
    )
    form_elements = extract_form_elements(driver)
    for form_element in form_elements:
        user_message += f"{form_element}\n-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def error_suggestion_violation_extraction(driver: webdriver):
    """
    WCAG 3.3.3 Error Suggestion
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.3.3."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    extract_original_screenshot(driver)
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    user_message.append({"type": "text", "text": "The screenshots are below:\n"})
    for screenshot in initial_screenshot_str:
        user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
        user_message.append({"type": "text", "text": "-------------\n"})
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def name_role_value_violation_extraction(driver: webdriver):
    """
    WCAG 4.1.2 Name, Role, Value
    """
    name_role = extract_name_role_elements(driver)
    form_inputs = extract_form_input_elements(driver)
    user_message = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 4.1.2. "
        "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific WCAG "
        "criterion,"
        "providing a description of any issues found.\n"
    )
    combined_data = [{'type': 'button', 'content': item} for item in name_role.get('button', [])]
    combined_data.extend(
        [{'type': 'aria-hidden', 'content': item} for item in name_role.get('aria-hidden', [])])
    combined_data.extend([{'type': 'form', 'content': item} for item in form_inputs.get('forms', [])])
    combined_data.extend([{'type': 'input', 'content': item} for item in form_inputs.get('inputs', [])])
    combined_data.extend([{'type': 'menuitem', 'content': item} for item in name_role.get('menuitem', [])])
    combined_data.extend([{'type': 'iframe', 'content': item} for item in name_role.get('iframe', [])])
    combined_data.extend(
        [{'type': 'script-controlled', 'content': item} for item in name_role.get('script-controlled', [])])
    combined_data.extend([{'type': 'link', 'content': item} for item in name_role.get('link', [])])
    for item in combined_data:
        user_message += f"{item['type'].capitalize()}:\n"
        user_message += f"{item['content']}\n"
        user_message += "-------------\n"
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def map_wcag_criterion_to_function_with_driver(criterion, driver):
    if 'SC 1.1.1 Non-text Content (Level A)' in criterion:
        result = non_text_content_violation_extraction(driver)
    elif 'SC 1.3.1: Info and Relationships (Level A)' in criterion:
        result = info_relation_violation_extraction(driver)
    elif 'SC 1.3.2: Meaningful Sequence (Level A)' in criterion:
        result = meaningful_sequence_violation_extraction(driver)
    elif 'SC 1.3.3: Sensory Characteristics (Level A)' in criterion:
        result = sensory_characteristic_violation_extraction(driver)
    elif 'SC 1.3.4: Orientation (Level AA)' in criterion:
        result = orientation_violation_extraction(driver)
    elif 'SC 1.3.5: Identify Input Purpose (Level AA)' in criterion:
        result = identify_input_purpose_violation_extraction(driver)
    elif 'SC 1.4.1: Use of Color (Level A)' in criterion:
        result = use_of_color_violation_extraction(driver)
    elif 'SC 1.4.2: Audio Control (Level A)' in criterion:
        result = audio_control_violation_extraction(driver)
    elif 'SC 1.4.3: Contrast (Minimum) (Level AA)' in criterion:
        result = contrast_violation_extraction(driver)
    elif 'SC 1.4.4: Resize Text (Level AA)' in criterion:
        result = resize_text_violation_extraction(driver)
    elif 'SC 1.4.5: Images of Text (Level AA)' in criterion:
        result = use_of_image_violation_extraction(driver)
    elif 'SC 1.4.6: Contrast (Enhanced) (Level AAA)' in criterion:
        result = contrast_enhanced_violation_extraction(driver)
    elif 'SC 1.4.8: Visual Presentation (Level AAA)' in criterion:
        result = visual_presentation_violation_extraction(driver)
    elif 'SC 1.4.10: Reflow (Level AA)' in criterion:
        result = reflow_violation_extraction(driver)
    elif 'SC 1.4.12: Text Spacing (Level AA)' in criterion:
        result = text_spacing_violation_extraction(driver)
    elif 'SC 2.2.1: Timing Adjustable (Level A)' in criterion:
        result = timing_adjustable_violation_extraction(driver)
    elif 'SC 2.2.2: Pause, Stop, Hide (Level A)' in criterion:
        result = pause_stop_hide_violation_extraction(driver)
    elif 'SC 2.4.1: Bypass Blocks (Level A)' in criterion:
        result = bypass_block_violation_extraction(driver)
    elif 'SC 2.4.2: Page Titled (Level A)' in criterion:
        result = page_title_violation_extraction(driver)
    elif 'SC 2.4.4: Link Purpose (In Context) (Level A)' in criterion:
        result = link_purpose_context_violation_extraction(driver)
    elif 'SC 2.4.5: Multiple Ways (Level AA)' in criterion:
        result = multiple_ways_violation_extraction(driver)
    elif 'SC 2.4.6: Headings and Labels (Level AA)' in criterion:
        result = headers_and_labels_violation_extraction(driver)
    elif 'SC 2.4.8: Location (Level AAA)' in criterion:
        result = location_violation_extraction(driver)
    elif 'SC 2.4.9: Link Purpose (Link Only) (Level AAA)' in criterion:
        result = link_purpose_link_only_violation_extraction(driver)
    elif "SC 2.4.10: Section Headings (Level AAA)" in criterion:
        result = section_headings_violation_extraction(driver)
    elif 'SC 2.5.5: Target Size (Enhanced) (Level AAA)' in criterion:
        result = target_size_enhanced_violation_extraction(driver)
    elif 'SC 2.5.8: Target Size (Minimum) (Level AA)' in criterion:
        result = target_size_minimum_violation_extraction(driver)
    elif 'SC 3.1.1: Language of Page (Level A)' in criterion:
        result = language_violation_extraction(driver)
    elif 'SC 3.1.2: Language of Parts (Level AA)' in criterion:
        result = language_violation_extraction(driver)
    elif 'SC 3.1.4: Abbreviations (Level AAA)' in criterion:
        result = abbreviation_violation_extraction(driver)
    elif 'SC 3.2.2: On Input (Level A)' in criterion:
        result = on_input_violation_extraction(driver)
    elif 'SC 3.2.5: Change on Request (Level AAA)' in criterion:
        result = change_on_request_violation_extraction(driver)
    elif 'SC 3.3.1: Error Identification (Level A)' in criterion:
        result = error_identification_violation_extraction(driver)
    elif 'SC 3.3.2: Labels or Instructions (Level A)' in criterion:
        result = labels_instructions_violation_extraction(driver)
    elif 'SC 3.3.3: Error Suggestion (Level AA)' in criterion:
        result = error_suggestion_violation_extraction(driver)
    elif 'SC 4.1.2: Name, Role, Value (Level A)' in criterion:
        result = name_role_value_violation_extraction(driver)
    else:
        result = None
    return result
