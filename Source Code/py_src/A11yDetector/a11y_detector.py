import asyncio
import base64
import binascii
import inspect
import json
import os
import re
import textwrap
from openai import OpenAI
from dotenv import dotenv_values
from consts import JSON_FORMAT
from A11yDetector.helper import chunk_data, aggregate_responses, check_url_status

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
config = dotenv_values(env_path)
client = OpenAI(api_key=config["OPENAI_API_KEY"])
sys_message = ("You are an Accessibility Expert (WCAG Specialist) responsible for detecting WCAG 2.2 violations on "
               "websites.Your expertise is crucial in making the web more accessible for everyone. Please analyze the "
               "provided, related HTML and CSS elements for compliance with the"
               "specified WCAG success criterion. Be confident in your expertise. Do not omit any issue. After "
               "analyzing all elements,"
               "do not provide individual element-by-element analysis. "
               "Instead, summarize the overall result. "
               "Your output should be structured as a JSON object with the following format: \n"
               '''{
                    "overall_violation": "Yes or No",
                    "violated_elements_and_reasons": 
                    [
                        {
                            "element": "outerHTML of the element",
                            "reason": "Explanation of why it violates the criterion",
                            "recommendation": "Recommendation to fix the violation for this specific element"
                        }
                    ]
            }'''
               "If there are no violations, the response should be: \n"
               '''{
                    "overall_violation": "No",
                    "violated_elements_and_reasons": []
                   }'''
               "Please provide the outerHTML of each element without including any of its children elements. This means"
               "you should return only the opening tag of the element along with its attributes and the closing tag, "
               "but exclude any nested elements or content inside."
               )


def send_request_to_model(model_name: str, system_message: str, user_message):
    """ Send a request to the OpenAI model with the specified messages. """
    completion = client.chat.completions.create(model=model_name,
                                                response_format=JSON_FORMAT,
                                                messages=[{"role": "system", "content": system_message},
                                                          {"role": "user", "content": user_message}],
                                                temperature=0.0, )
    return completion


def detect_title_violation(page_title_dict: dict):
    """
    Determine if a webpage's title violates WCAG Success Criterion 2.4.2.
    """
    user_message = (
        "You will receive the page title along with some portions of a webpage. Your task is to determine if "
        "there is any violation of WCAG SC 2.4.2. Focus solely on this criterion. Identify whether the elements "
        "comply with the specific WCAG criterion and provide a description of any issues found. Please adhere to the "
        "following test rules provided by WCAG: \n"
        "1. The page title should not be null. \n"
        "2. The page title should be descriptive based on the portions of the webpage. \n"
        "The information for your assessment begins after the dashed line. \n"
        "------------------ \n"
        f"Title: {page_title_dict['title']} \n"
        f"Portion text: {page_title_dict['portion_text']} \n"
    )
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    return detection_result


def detect_lang_violation(page_title_dict: dict, elements_with_lang: dict):
    """
    Detect violations of WCAG Success Criteria 3.1.1 and 3.1.2 regarding the use of the lang attribute.
    """
    user_message = (
        "You will be provided with HTML elements that have a lang attribute from a webpage, as well as "
        "relevant portion text, to determine if there is any violation of WCAG SC 3.1.1 and SC 3.1.2. "
        "Please focus only on these criteria. Determine whether the elements comply with the specific WCAG criterion, "
        "and provide a description of any issues if found. Follow the six test rules below: \n"
        "1. The HTML page should have a lang attribute. If you see the message 'Could not find the lang attribute on "
        "this page', it's a violation. \n"
        "2. The lang attribute must have a valid language tag. For example, if the value of the lang attribute is "
        "'#1', it is not valid. \n"
        "3. The lang and xml:lang attributes, if both present, should have matching values. You can ignore this case "
        "if xml:lang is not present. \n"
        "4. The language subtag in the lang attribute should match the default language. \n"
        "5. The language specified by the lang and xml:lang attributes for any element must accurately reflect the "
        "language of the content within that element. Determine the language of the text in the HTML snippet without "
        "considering the lang and xml:lang attributes, then compare your identification with the declared language. \n"
        "6. For portions of content in a different language from the default, use the lang attribute to specify the "
        "language. Ensure that the text direction is appropriate for the specified language. \n"
        "The related information for you to assess starts after the dashed line. \n"
        "------------------ \n"
    )
    user_message += f"Portion text: {page_title_dict['portion_text']} \n"
    if len(elements_with_lang["lang_only"]) > 0:
        user_message += f"html elements with lang attribute: {elements_with_lang["lang_only"]} \n"
    if len(elements_with_lang["lang_and_xml"]) > 0:
        user_message += f"html elements with lang and xml:lang attributes: {elements_with_lang["lang_and_xml"]} \n"
    if len(elements_with_lang["lang_and_xml"]) == 0 and len(elements_with_lang["lang_only"]) == 0:
        user_message += "Could not find the lang attribute on this page. \n"
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    return detection_result


def detect_non_text_content_violation(visual_elements_dict: dict):
    """ Detect if there are violations related to non-text content WCAG SC 1.1.1. """
    user_message_template = (
        "Please analyze the provided visual elements from a webpage for compliance with WCAG SC 1.1.1. "
        "Focus specifically on identifying any issues related to non-text content. Your primary task is to detect "
        "whether images, videos, and other non-text elements have appropriate text alternatives.\n"
        "**WCAG SC 1.1.1 Test Rules:**\n"
        "1. Image buttons must have a non-empty accessible name.\n"
        "2. Images (including elements with the role 'img'), videos, and audio elements must have non-empty "
        "accessible names, unless they are purely decorative. Ignore purely decorative images (e.g., those with alt='',"
        "alt=\"\", role='presentation', aria-hidden='true').\n"
        "3. The accessible names for images (including elements with role 'img'), videos, and audio elements must be"
        "meaningful.\n"
        "4. Non-text content rendered by object elements must have non-empty accessible names.\n"
        "5. SVG elements with explicit roles must have non-empty accessible names.\n"
        "**Common Failures for SC 1.1.1:**\n"
        "- **F30**: Using text alternatives that are not true alternatives (e.g., filenames or placeholder text).\n"
        "- **F65**: Omitting the alt attribute or text alternative on img elements, area elements, and input elements "
        "of type 'image', except when the image is purely decorative.\n"
        "**Additional Considerations:**\n"
        "- Ensure that text alternatives are not only present but also descriptive and relevant.\n"
        "The information you need to assess starts after the dashed line below. Pay attention to all the elements "
        "below. \n"
        "----------------------------------\n"
    )
    # Chunk the visual elements data
    chunks = chunk_data(visual_elements_dict, threshold_tokens=20000, max_chunk_tokens=5000)

    # Initialize a list to collect responses
    all_responses = []

    for chunk in chunks:
        # Construct the user message for the current chunk
        chunk_message = user_message_template + "\n".join(
            f"{key}: {value}" for key, value in chunk.items()
        )

        # Send request to the model (assuming send_request_to_model is defined)
        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, chunk_message)
        response_json = completion.choices[0].message.content
        all_responses.append(response_json)

    # Aggregate all responses
    aggregated_response = aggregate_responses(all_responses)

    # Print the aggregated response
    final_response = json.dumps(aggregated_response, indent=2)
    return final_response


def is_base64_image(data):
    image_patterns = [
        r'data:image/png;base64,',
        r'data:image/jpeg;base64,',
        r'data:image/gif;base64,',
        r'data:image/webp;base64,',
        r'data:image/svg+xml;base64,'
    ]
    return any(re.match(pattern, data) for pattern in image_patterns)


def detect_non_text_alt_text_not_descriptive(visual_elements_dict: dict):
    user_message_base = {
        "type": "text",
        "text": (
            "You will be provided with various visual elements and their URLs from a webpage to assess "
            "compliance with WCAG SC 1.1.1. Please focus solely on this criterion. Your task is to determine "
            "whether these elements meet the specific WCAG requirements and to describe any issues identified. "
            "\n"
            "The following test rules should be followed:\n"
            "1. The accessible name of the image should be descriptive.\n"
            "2. Images not included in the accessibility tree should be marked as decorative.\n"
            "Common failures of SC 1.1.1 include:\n"
            "- **F3**: Failure due to using CSS to include images conveying important information. An image conveys "
            "important information if it provides essential context or content, such as a graph showing data trends "
            "or an icon indicating an error message. If the image does not"
            "convey important information, it is not a violation. If the image"
            "does not convey important information, it is not a violation.\n"
            "- **F13**: Failure due to text alternatives not including information conveyed by color differences "
            "in the image.\n"
            "- **F20**: Failure due to not updating text alternatives when changes occur in non-text content.\n"
            "- **F30**: Failure due to using non-descriptive text alternatives, such as filenames or placeholder "
            "text.\n"
            "- **F38**: Failure due to not marking up decorative images so assistive technology can ignore them.\n"
            "- **F39**: Failure due to providing non-null text alternatives (e.g., 'alt=\"spacer\"') for images "
            "that should be ignored by assistive technology.\n"
            "- **F67**: Failure due to providing long descriptions for non-text content that do not serve the "
            "same purpose or present the same information.\n"
            "For each visual element, you will be given the HTML tag and image URL. Use the image URL to determine "
            "if there are any violations based on the test rules and common failures.\n"
            "The related information for your assessment starts after the dashed line.\n"
            "------------------\n"
        )
    }

    valid_extensions = ['png', 'jpeg', 'gif', 'webp', 'jpg']
    elements_with_status_200 = {
        key: value for key, value in visual_elements_dict['img_urls'].items()
        if (any(value.lower().endswith(ext) for ext in valid_extensions) or is_base64_image(value))
           and check_url_status(value) == 200
    }

    chunked_elements = chunk_data(elements_with_status_200, threshold_tokens=20000, max_chunk_tokens=5000)
    responses = []

    for chunk in chunked_elements:
        try:
            user_message = [user_message_base.copy()]  # Start with the base message
            for key, value in chunk.items():
                user_message.append({"type": "text", "text": f"HTML tag: {key}\n"})
                user_message.append({"type": "image_url", "image_url": {"url": value}})
                user_message.append({"type": "text", "text": "------------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_non_text_content_aggregated_violation(visual_elements_dict: dict):
    """
    Detect aggregated violations of WCAG criterion 1.1.1 related to non-text content on a webpage.
    """
    detection_result = detect_non_text_content_violation(visual_elements_dict)
    detection_result_2 = detect_non_text_alt_text_not_descriptive(visual_elements_dict)
    aggregated_response = aggregate_responses([detection_result, detection_result_2])
    final_response = json.dumps(aggregated_response, indent=2)
    return final_response


def detect_misuse_images_of_text(image_urls: set):
    """
        Detect misuse of images of text based on WCAG SC 1.4.5 criteria.
    """
    user_message_base = {
        "type": "text",
        "text": (
            "You will be provided with image URLs from a webpage. Your task is to assess whether these images "
            "comply with WCAG SC 1.4.5, focusing only on this specific criterion. Determine if the images contain "
            "visible text and describe any issues if found.\n"
            "According to WCAG SC 1.4.5, images should not contain visible text unless one of the following "
            "conditions is met:\n"
            "1. The image is purely decorative.\n"
            "2. The text is not a significant part of the image.\n"
            "3. The presentation of the text is essential.\n"
            "Use your judgment to determine whether each image meets these exceptions.\n"
            "The relevant information for your assessment begins after the dashed line.\n"
            "------------------\n"
        )
    }

    valid_extensions = ['png', 'jpeg', 'gif', 'webp', 'jpg']
    # Filter out image URLs that return a status code of 200
    valid_image_urls = {
        url for url in image_urls
        if (any(url.lower().endswith(ext) for ext in valid_extensions) or is_base64_image(url))
           and check_url_status(url) == 200
    }
    # Chunk the valid image URLs
    chunked_image_urls = chunk_data(list(valid_image_urls))

    responses = []

    for chunk in chunked_image_urls:
        try:
            user_message = [user_message_base.copy()]  # Start with the base message
            for url in chunk:
                user_message.append({"type": "image_url", "image_url": {"url": url}})
            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def wrap_text_with_textwrap(text, max_line_length):
    return '\n'.join(textwrap.wrap(text, width=max_line_length))


def detect_input_without_purpose(input_elements: dict):
    """
    Detect the presence of input elements without a discernible purpose based on WCAG SC 1.3.5.
    """
    user_message = (
        "You will be provided with input elements from a webpage to assess compliance with WCAG SC 1.3.5. "
        "Each input element is presented as a key-value pair, where the key represents the label and the value "
        "is the corresponding input tag. Please focus only on this criterion. Determine whether the input elements "
        "comply with the WCAG SC 1.3.5 criterion and describe any issues identified.\n"
        "Below are common failures associated with this criterion, but violations are not limited to these examples. "
        "Use your expertise and judgment to identify any additional violations:\n"
        "1. Failure of Success Criterion 1.3.5 due to incorrect autocomplete attribute values.\n"
        "2. Failure of Success Criterion 1.3.5 when the purpose of each input field that collects information about "
        "the user cannot be programmatically determined when the field serves a common purpose.\n"
        "The related information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    for key, value in input_elements.items():
        user_message += f"{key}: {value}\n"
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_missing_label_instruction(form_elements: list):
    """
    Detect input elements that lack appropriate labels or instructions according to WCAG SC 3.3.2.
    """
    user_message = (
        "You will be provided with form elements from a webpage. Your task is to assess compliance with WCAG SC 3.3.2, "
        "focusing solely on this criterion. Determine whether the form elements have appropriate labels and "
        "instructions,"
        "and describe any issues found.\n"
        "Test rules for this criterion include:\n"
        "1. **fieldset_label_valid**: Groups with nested inputs must have a unique accessible name.\n"
        "2. **input_label_after**: Checkboxes and radio buttons must have a label after the input control.\n"
        "3. **input_label_before**: Text inputs and <select> elements must have a label before the input control.\n"
        "4. **input_placeholder_label_visible**: The HTML5 'placeholder' attribute must not replace a visible label. "
        "HTML5 placeholders should not be the only visible label, and any additional visible label referenced by "
        "'aria-labelledby' must be valid.\n"
        "5. **input_label_visible**: An input element must have an associated visible label. Check whether the label is"
        "visible through CSS attributes.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    for form_element in form_elements:
        user_message += f"{form_element}\n-------------\n"
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_label_in_name_violation(element_with_label: set):
    """
     Detect elements that violate the 'label in name' requirement based on WCAG SC 2.5.3.
    """
    user_message_base = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 2.5.3. "
        "Each element is separated by the string '-------------'. Please focus solely on this criterion. Your task is "
        "to determine whether the elements comply with WCAG SC 2.5.3 and to describe any issues found.\n"
        "Test rules for this criterion include:\n"
        "1. The visible label (including the value attribute and text inside a tag) must be part of the accessible "
        "name."
        "For example, <button aria-label='Next Page in the list'>Next Page</button> is a **passing example** because "
        "the"
        "visible label 'Next Page' is part of the accessible name 'Next Page in the list'.\n"
        "Common failures include:\n"
        "1. **F96**: Failure due to the accessible name not containing the visible label text.\n"
        "2. **F111**: Failure due to a control having a visible label text (including value attribute and text) but no "
        "accessible name. If there is no accessible name, do not infer one from the element!\n"
        "The relevant information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    # Chunk the elements with labels if they exceed a certain size
    chunked_elements = chunk_data(list(element_with_label))

    responses = []

    for chunk in chunked_elements:
        user_message = user_message_base  # Start with the base message
        for element in chunk:
            user_message += f"{element}\n-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_text_resizing_violation(resizing_elements: dict):
    """
    Detect violations related to text resizing in accordance with WCAG SC 1.4.4.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with webpage elements and two screenshots to assess compliance with WCAG SC "
                "1.4.4."
                "The first screenshot shows the original webpage, and the second shows the webpage after zooming in "
                "to 200%."
                "Focus exclusively on this criterion. Your task is to determine whether the elements comply with WCAG "
                "SC 1.4.4"
                "and describe any issues found.\n"
                "Test rules for this criterion include:\n"
                "1. The content attribute on a meta element with a name attribute value of 'viewport' must not "
                "restrict zoom. Specifically,"
                "the 'user-scalable' property should not be set to 'no,' and the 'maximum-scale' property should be "
                "at least 2.\n"
                "2. When text is resized up to 200%, it should not cause text, images, or controls to be clipped, "
                "truncated, or obscured."
                "Extract text from each screenshot and compare them to ensure resizability without causing these "
                "issues.\n"
                "3. Text-based form controls should resize appropriately when visually rendered text is resized up to "
                "200%. Using fixed"
                "units such as pt and px for text size is a violation.\n"
                "The related information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    if 'meta' in resizing_elements.keys():
        user_message.append({"type": "text", "text": f"Meta elements: {resizing_elements['meta']} \n"})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{resizing_elements['original']}"}})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{resizing_elements['zoomed']}"}})
    if len(resizing_elements['input_elements']) != 0:
        user_message.append({"type": "text", "text": "Input elements:"})
        for input_element in resizing_elements['input_elements']:
            for key, value in input_element.items():
                user_message.append({"type": "text", "text": f"{key} - {value}"})
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_reflow_violation(reflow_elements: dict):
    """
    Detect violations related to content reflow in accordance with WCAG SC 1.4.10.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with two screenshots to determine if there is any violation of WCAG SC 1.4.10. "
                "The first screenshot shows the original webpage, and the second shows the webpage after zooming in "
                "to 400% with a window size of 1280x1024 pixels. Focus exclusively on this criterion. Your task is to "
                "determine whether the elements comply with WCAG SC 1.4.10 and describe any issues found.\n"
                "Common failures for this criterion include:\n"
                "1. Content disappearing and not being available after reflow.\n"
                "2. Content requiring scrolling in two dimensions to view.\n"
                "The related information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{reflow_elements['original']}"}})
    user_message.append(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{reflow_elements['reflow']}"}})
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_no_audio_control(audio_dict: dict):
    """
    Detect violations related to the absence of audio controls in accordance with WCAG SC 1.4.2.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with audio elements from a webpage to assess compliance with WCAG SC 1.4.2. "
                "Please focus only on this criterion. Your task is to determine whether the audio elements comply "
                "with WCAG SC 1.4.2 and describe any issues identified. Below are the test rules for this "
                "criterion:\n"
                "1. If audio plays automatically and there is no mechanism to stop or pause it, the audio should not "
                "play for more than 3 seconds. Audio elements labeled as 'short-audio' indicate they do not play for "
                "more"
                "than 3 seconds.\n"
                "2. If audio plays automatically for more than 3 seconds, there must be a mechanism to stop or pause "
                "the audio."
                "Audio elements labeled as 'long-audio' indicate they play for more than 3 seconds. For each "
                "'long-audio' element,"
                "you will be provided with the corresponding HTML tag and a screenshot. Use the screenshot to "
                "determine whether"
                "there is a control to stop or pause the audio.\n"
                "The related information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    if 'short' in audio_dict.keys():
        for html_element, imgs in audio_dict['short'].items():
            user_message.append({
                "type": "text",
                "text": f"short-audio: {html_element} \n"
            })
    if 'long' in audio_dict.keys():
        for html_element, imgs in audio_dict['long'].items():
            user_message.append({
                "type": "text",
                "text": f"long-audio: {html_element} \n"
            })
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imgs}"}}
            )
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_timing_adjustable_violation(timing_adjustable_list: list):
    """
    Detect violations related to time limits and the ability to adjust them in accordance with WCAG SC 2.2.1.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with meta elements and two consecutive screenshots (the first is before "
                "redirection"
                "and the second is after redirection) from a webpage to determine if there is any violation of WCAG "
                "SC 2.2.1."
                "If no meta elements or screenshots are provided, it indicates that the website conforms to "
                "this criterion."
                "Please focus solely on this criterion. Your task is to determine whether the elements comply with "
                "WCAG SC 2.2.1"
                "and describe any issues found.\n"
                "Common failures for this criterion include:\n"
                "1. **F40**: Failure due to using meta redirect with a time limit.\n"
                "2. **F41**: Failure due to using meta refresh to reload the page.\n"
                "3. **F58**: Failure due to using server-side techniques to automatically redirect pages after a "
                "time-out.\n"
                "Test rules for this criterion include:\n"
                "1. If a web page uses a meta element to redirect to another page, and the numerical value for the "
                "seconds until refresh in the content attribute is less than 1 or greater than 72000, it is *not* a "
                "violation.\n"
                "2. Otherwise, there should be a mechanism to turn off, adjust, or extend time limits. Use the two "
                "provided screenshots"
                "to determine this.\n"
                "3. If the page is redirected or refreshed automatically without using a meta element, use the two "
                "provided screenshots"
                "to determine if there is a mechanism to turn off, adjust, or extend time limits. If not, "
                "it is a violation.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    if len(timing_adjustable_list[0]) != 0:
        user_message.append({"type": "text", "text": f"meta elements: {timing_adjustable_list[0]} \n"})
    if timing_adjustable_list[1]:
        if len(timing_adjustable_list[1]) != 0:
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{timing_adjustable_list[1][0]}"}})
            user_message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{timing_adjustable_list[1][1]}"}})
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_orientation_violation(orientation_dict: dict):
    """
    Detect violations related to content orientation as per WCAG SC 1.3.4.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with two screenshots from a webpage to assess compliance with WCAG SC 1.3.4. "
                "The first screenshot is in landscape mode, and the second is in portrait mode. Focus solely on this "
                "criterion. Your task is to determine whether the elements comply with WCAG SC 1.3.4 and describe any "
                "issues found.\n"
                "Test rules for this criterion include:\n"
                "1. Examine both screenshots to determine if the content is restricted to one view. If the content "
                "does not display correctly"
                "or is restricted in either landscape or portrait mode, it is a violation.\n"
                "**Non-Compliant Example**: A webpage that displays a header and text content correctly in landscape "
                "mode, but in portrait mode,"
                "the text is rotated 90 degrees, making it unreadable without rotating the device.\n"
                "**Compliant Example**: A webpage that adjusts its layout based on the device orientation, "
                "ensuring all text, images, and interactive elements"
                "are accessible and properly aligned in both portrait and landscape modes.\n"
                "2. Determine if there is a message prompting users to reorient their device. If such a message "
                "exists, it is a violation.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        },
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{orientation_dict['landscape']}"}},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{orientation_dict['portrait']}"}}
    ]
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_multiple_ways_violation(multiple_way_dict: dict):
    """
    Detect violations of WCAG SC 2.4.5, which requires providing multiple ways to access content.
    """
    user_message = [
        {
            "type": "text",
            "text": (
                "You will be provided with two screenshots from a webpage to determine if there is any violation of "
                "WCAG SC 2.4.5. The first screenshot is taken when opening the browser, and the second screenshot is "
                "taken after scrolling to the very bottom of the webpage. Please focus solely on this criterion. Your "
                "task is to"
                "determine whether the elements comply with WCAG SC 2.4.5 and describe any issues found.\n"
                "Test rule for this criterion:\n"
                "1. Review the two screenshots and determine whether the page provides at least two methods for "
                "reaching the same content."
                "Common techniques include:\n"
                "- **G125**: Providing links to navigate to related web pages.\n"
                "- **G64**: Providing a Table of Contents.\n"
                "- **G63**: Providing a site map.\n"
                "- **G161**: Providing a search function to help users find content.\n"
                "- **G126**: Providing a list of links to all other web pages.\n"
                "- **G185**: Linking to all of the pages on the site from the home page.\n"
                "The page should use two or more of these techniques to offer multiple ways to access content. If the "
                "page uses alternative methods"
                "not listed above but still provides multiple ways to reach content, it may still be compliant. Use "
                "your judgment and expertise to"
                "assess these cases.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        },
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{multiple_way_dict['initial']}"}},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{multiple_way_dict['bottom']}"}}]
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_link_purpose_violation_a(link_purpose_list: list):
    """
    Detect violations related to the purpose of links as per WCAG SC 2.4.4
    """
    user_message_base = (
        "It's important to understand that if a link's purpose can be determined by the surrounding context, "
        "it is not a violation."
        "You will be provided with link elements, along with their ancestors and siblings (if any), from a webpage to "
        "assess for any violations"
        "of WCAG SC 2.4.4. Unlike SC 2.4.9, this criterion allows relying on contextual information to determine if a "
        "link is descriptive."
        "A link should clearly indicate its purpose without requiring the user to click on it, and it should not be "
        "too general, such as 'a link'."
        "Each link element will be presented on a new line, starting with '-------------'. Please focus exclusively "
        "on this criterion."
        "Determine whether the elements comply with the specific WCAG criterion and describe any issues identified.\n"
        "Test rules for this criterion include:\n"
        "1. The link must have a non-empty accessible name.\n"
        "2. The link in **context** should be descriptive. **Context** refers to the information provided by the "
        "link's ancestors and siblings."
        "If these elements provide enough descriptive information, then the link is compliant and not considered a "
        "violation.\n"
        "3. Links with identical accessible names in the same context must serve an equivalent purpose.\n"
        "The relevant information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    # Chunk the data
    chunked_link_purpose_list = chunk_data(link_purpose_list)

    responses = []

    for chunk in chunked_link_purpose_list:
        user_message = user_message_base
        for element in chunk:
            user_message += f"{element}\n-------------\n"
        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_link_purpose_violation_aaa(link_purpose_list: list):
    """
    Detect violations of WCAG SC 2.4.9 related to the purpose of links.
    """
    user_message_base = (
        "You will be provided with link elements from a webpage to determine if there is any violation of WCAG SC "
        "2.4.9."
        "Unlike SC 2.4.4, this criterion requires that you evaluate the link's descriptiveness based solely on the "
        "link itself,"
        "without considering its surrounding context. A link should clearly indicate its purpose without requiring "
        "the user to click on it,"
        "and it should not be too general, such as 'a link'. Each link element will be presented on a new line, "
        "starting with"
        "'-------------'."
        "Please focus exclusively on this criterion. Determine whether the elements comply with WCAG SC 2.4.9 and "
        "describe any issues identified.\n"
        "Test rules for this criterion include:\n"
        "1. The link must have a non-empty accessible name.\n"
        "2. The link must be descriptive, clearly conveying its purpose.\n"
        "3. Links with identical accessible names must serve an equivalent purpose.\n"
        "The relevant information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    # Chunk the data
    chunked_link_purpose_list = chunk_data(link_purpose_list)

    responses = []

    for chunk in chunked_link_purpose_list:
        user_message = user_message_base
        for element in chunk:
            user_message += f"{element}\n-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_color_contrast_violation_aa(color_contrast_list: list, color_contrast_dict: dict):
    """
    Detect violations related to color contrast as per WCAG SC 1.4.3.
    """
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with text elements and their corresponding color values in rgb or rgba format "
                "from a webpage"
                "to assess compliance with WCAG SC 1.4.3. If a text element has an image background, you will also "
                "receive"
                "a screenshot of the text over the background image. Each text element will be separated by "
                "'-------------'."
                "Please focus solely on this criterion. Determine whether the elements comply with WCAG SC 1.4.3 and "
                "describe"
                "any issues identified.\n"
                "Test rules for this criterion include:\n"
                "1. Text and its background must have a contrast ratio of at least 4.5:1.\n"
                "2. Large text (defined as at least 18 point for regular text or 14 point for bold text) and its "
                "background must have a contrast ratio of at least 3:1."
                "You will be provided with font-size information.\n"
                "3. When background images are used, they must provide sufficient contrast with the foreground text "
                "to ensure readability."
                "Examine the provided screenshot to determine if the text is readable.\n"
                "A common failure for this criterion includes:\n"
                "- **F24**: Failure due to specifying foreground colors without specifying background colors or vice "
                "versa.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "----------------------\n"
            )
        }
    ]

    # Combine data from both parameters
    text_elements = [{'type': 'text', 'content': text} for text in color_contrast_list]
    image_elements = [{'type': 'image', 'text': key, 'image': value} for key, value in color_contrast_dict.items()]

    combined_data = text_elements + image_elements

    # Chunk the combined data
    chunked_data = chunk_data(combined_data)

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()

            # Add text elements together
            user_message.append({"type": "text", "text": "\nText elements:\n----------------------\n"})
            for item in chunk:
                if item['type'] == 'text':
                    user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})

            # Add image elements together
            user_message.append({"type": "text", "text": "\nImage elements (with background "
                                                         "images):\n----------------------\n"})
            for item in chunk:
                if item['type'] == 'image':
                    user_message.append({"type": "text", "text": f"{item['text']}\n"})
                    user_message.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['image']}"}})
                    user_message.append({"type": "text", "text": "\n-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_color_contrast_violation_aaa(color_contrast_list: list, color_contrast_dict: dict):
    """
    Detect violations related to color contrast as per WCAG SC 1.4.6.
    """
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with text elements and their corresponding color values in rgb or rgba format "
                "from a webpage"
                "to assess compliance with WCAG SC 1.4.6. If a text element uses an image as a background, "
                "you will also receive"
                "a screenshot showing the text over the background image. Each text element will be separated by "
                "'-------------'."
                "Please **only focus on this criterion**. Your task is to determine whether the elements comply with "
                "WCAG SC 1.4.6"
                "and describe any issues identified.\n"
                "Test rules for this criterion include:\n"
                "1. Text and its background must have a contrast ratio of at least 7:1.\n"
                "2. Large text (defined as at least 18 point for regular text or 14 point for bold text) and its "
                "background must have a contrast ratio of at least 4.5:1."
                "You will be provided with font-size information.\n"
                "3. When background images are used, they must provide sufficient contrast with the foreground text "
                "to ensure readability."
                "Examine the provided screenshot to determine if the text is readable.\n"
                "A common failure for this criterion includes:\n"
                "- **F24**: Failure due to specifying foreground colors without specifying background colors or vice "
                "versa.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "----------------------\n"
            )
        }
    ]

    # Combine data from both parameters
    text_elements = [{'type': 'text', 'content': text} for text in color_contrast_list]
    image_elements = [{'type': 'image', 'text': key, 'image': value} for key, value in color_contrast_dict.items()]

    combined_data = text_elements + image_elements

    # Chunk the combined data
    chunked_data = chunk_data(combined_data)

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()  # Copy the base message structure

            # Add text elements together
            user_message.append({"type": "text", "text": "\nText elements:\n----------------------\n"})
            for item in chunk:
                if item['type'] == 'text':
                    user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})

            # Add image elements together
            user_message.append({"type": "text", "text": "\nImage elements (with background "
                                                         "images):\n----------------------\n"})
            for item in chunk:
                if item['type'] == 'image':
                    user_message.append({"type": "text", "text": f"{item['text']}\n"})
                    user_message.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['image']}"}})
                    user_message.append({"type": "text", "text": "\n-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_heading_label_description_violation(input_dict: dict, heading_list: list):
    """
    Detect heading and label description violations as per WCAG SC 2.4.6.
    """
    user_message_base = (
        "You will receive heading elements and labels of inputs from a webpage. Your task is to determine compliance "
        "with WCAG SC 2.4.6. Each heading element includes two consecutive siblings, if present. Use these siblings to "
        "assess if the heading is descriptive. Labels for input elements are either within form elements or directly "
        "sibling to the inputs. Labels should clearly describe the purpose of their corresponding inputs if they are "
        "present. If there is no label or heading, it is not a violation. Focus solely"
        "on this criterion. Identify any issues and describe them. The relevant information begins after the dashed "
        "line.\n"
        "------------------\n"
    )
    # Combine data from both parameters
    heading_elements = [{'type': 'heading', 'content': heading} for heading in heading_list]
    form_labels = [{'type': 'form_label', 'content': label} for label in input_dict.get('forms', [])]
    input_labels = [{'type': 'input_label', 'content': label} for label in input_dict.get('inputs', [])]

    combined_data = heading_elements + form_labels + input_labels

    # Chunk the combined data
    chunked_data = chunk_data(combined_data)

    responses = []

    for chunk in chunked_data:
        user_message = user_message_base

        # Add heading elements
        user_message += "\nHeading elements:\n"
        user_message += "----------------------\n"
        for item in chunk:
            if item['type'] == 'heading':
                user_message += f"{item['content']}\n-------------\n"

        # Add form labels
        user_message += "\nLabels within form elements:\n"
        user_message += "----------------------\n"
        for item in chunk:
            if item['type'] == 'form_label':
                user_message += f"{item['content']}\n-------------\n"

        # Add input labels
        user_message += "\nLabels as siblings of input elements:\n"
        user_message += "----------------------\n"
        for item in chunk:
            if item['type'] == 'input_label':
                user_message += f"{item['content']}\n-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_section_heading_violation(section_heading_list: list, screenshot_list: list):
    """
    Detect violations related to section headings according to WCAG SC 2.4.10.
    """
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with a list of screenshots and information about headings from a webpage to "
                "assess"
                "compliance with WCAG SC 2.4.10. A section heading should clearly describe the purpose of the section, "
                "helping users understand its content. In this context, a 'section' refers to a distinct part of the "
                "content"
                "that is logically grouped together, such as a group of paragraphs, a form, a list, or any other "
                "cohesive"
                "unit of information. You should look at the screenshots to determine the sections.  Focus solely on "
                "this criterion and identify any violations. Specifically,"
                "determine"
                "whether each section has a descriptive heading. The test rules for this criterion are:\n"
                "1. Each section should have a heading.\n"
                "2. The heading should be descriptive.\n"
                "The relevant information for your assessment begins after the dashed line.\n"
                "------------------\n"
            )
        }
    ]

    responses = []

    # Prepare combined data with categorized elements
    headings_data = [{'type': 'heading', 'content': heading} for heading in section_heading_list]
    screenshots_data = [{'type': 'screenshot', 'content': screenshot} for screenshot in screenshot_list]

    combined_data = headings_data + screenshots_data

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    for _, chunk in enumerate(chunked_data):
        try:
            user_message = user_message_base.copy()
            for item in chunk:
                if item['type'] == 'heading':
                    heading = item['content']
                    section_number = section_heading_list.index(heading) + 1
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
            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_info_relation_violation(info_dict: dict):
    """
    Detect violations related to information and relationships according to WCAG SC 1.3.1.
    """
    user_message_base = (
        "You will be provided with elements from a webpage to assess compliance with WCAG SC 1.3.1. Focus solely on "
        "this"
        "criterion and determine whether the elements conform to it, describing any issues if found. Below are the "
        "common"
        "failures related to this criterion:\n"
        "Tables:\n"
        "1. Not correctly marking up table headers (using <th> for headers).\n"
        "2. Using <th>, <caption>, or non-empty summary attributes in layout tables.\n"
        "3. Headers attribute refers to cells in the same table.\n"
        "4. Missing scope attributes in header cells.\n"
        "5. Inconsistent numbers of columns in rows.\n"
        "6. Table with only <th> elements.\n"
        "7. Missing or inappropriate captions.\n"
        "8. Tables used solely for layout purposes.\n"
        "9. Empty table headers or cells.\n"
        "10. Nested tables.\n"
        "PRE elements:\n"
        "1. Failure of Success Criterion 1.3.1 due to using the <pre> element to markup tabular information.\n"
        "ARIA Roles:\n"
        "1. ARIA required context role. An element with an explicit semantic role exists inside its required context.\n"
        "2. ARIA required owned elements. An element with an explicit semantic role has at least one of its required "
        "owned elements.\n"
        "3. The ARIA role should have a valid value.\n"
        "onClick Events:\n"
        "1. Failure of Success Criteria 1.3.1 when emulating links. Only the <a> and <area> elements are intended to "
        "mark"
        "up links. Check the onClick event to determine if the element is used to emulate links.\n"
        "Whitespace in Plain Text:\n"
        "1. Failure of Success Criterion 1.3.1 due to using white space characters to create multiple columns in plain "
        "text content.\n"
        "2. Failure of Success Criterion 1.3.1 due to using white space characters to format tables in plain text "
        "content.\n"
        "Article Elements:\n"
        "1. Article element used to mark-up an element that's not an article/blog post, etc.\n"
        "Headings:\n"
        "1. Headings not structured in a hierarchical manner.\n"
        "2. Headings have empty text.\n"
        "Lists and Definitions:\n"
        "1. Incorrect markup of List and Definition elements.\n"
        "CSS Inserted Content:\n"
        "1. The inserted content by CSS is not decorative; instead, it conveys important information.\n"
        "Hidden Elements:\n"
        "1. The hidden element is not intended to be hidden. It's important for people with disabilities to understand "
        "the page.\n"
        "Radio Buttons and Checkboxes:\n"
        "1. If a group of radio buttons or checkboxes is not enclosed in a <fieldset>, it's a violation. Use the value "
        "attribute and the associated label to determine if the radio buttons or checkboxes should be grouped. If they "
        "should be grouped but there is no <fieldset>, it's a violation.\n"
        "Fieldset and Legend:\n"
        "1. Fieldset does not have a legend.\n"
        "2. The legend is empty.\n"
        "Paragraphs:\n"
        "1. Paragraphs should not have empty text.\n"
        "Images:\n"
        "1. Images should not be used to create space.\n"
        "The relevant information for your assessment begins after the dashed line.\n"
        "------------------\n"
    )
    # Combine data from all sections in info_dict
    combined_data = []
    for key, elements in info_dict.items():
        combined_data.extend([{key: element} for element in elements])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base

            # Add each element from the chunk
            for item in chunk:
                key = list(item.keys())[0]
                user_message += f"{key.capitalize()}:\n"
                user_message += f"{item[key]}\n-------------\n"

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_info_relation_part_b_violation(info_dict: dict, screenshot_list: list):
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with screenshots from a webpage, as well as heading, list, and link elements, "
                "to determine if there is any violation of WCAG SC 1.3.1. Pay attention to all screenshots provided. "
                "Focus solely on this criterion and determine whether the elements comply with the specific WCAG "
                "criterion,"
                "providing a description of any issues found.\n"
                "Below are the test rules for this criterion:\n"
                "1. **Organize Content:** Content should be organized into well-defined groups or chunks using "
                "headings, lists,"
                "and other visual mechanisms. Use the screenshots to assess if the elements on the page are "
                "appropriately grouped."
                "If not, identify the elements that are improperly organized.\n"
                "2. **Use of Actual Headings:** Actual headings should be used instead of text formatting. Compare "
                "the visual headings"
                "in the screenshots with the actual HTML headings. Discrepancies are violations.\n"
                "3. **Use of Actual Lists:** Actual lists should be used instead of text formatting. Compare the "
                "visual lists in the"
                "screenshots with the actual HTML lists. Discrepancies are violations.\n"
                "4. **Identifiable Links:** Links should be distinguishable from surrounding text. Verify that the "
                "links in the screenshots"
                "match the actual HTML links. Discrepancies are violations.\n"
                "The relevant information for your assessment starts after the dashed line.\n"
                "------------------\n"
            )
        },
        {"type": "text", "text": "Screenshots are provided below:\n"}
    ]
    # Combine data from all sections in info_dict and screenshots
    combined_data = [{"type": "screenshot", "content": screenshot} for screenshot in screenshot_list]
    combined_data.extend([{"type": "heading", "content": heading} for heading in info_dict.get("headings", [])])
    combined_data.extend([{"type": "list", "content": list_element} for list_element in info_dict.get("lists", [])])
    combined_data.extend([{"type": "link", "content": link} for link in info_dict.get("links", [])])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append({"type": "text", "text": "Screenshots and elements are provided "
                                                         "below:\n"})

            for item in chunk:
                if item["type"] == "screenshot":
                    user_message.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['content']}"}}
                    )
                else:
                    element_type = item["type"].capitalize()
                    user_message.append({"type": "text", "text": f"{element_type}s:\n"})
                    user_message.append({"type": "text", "text": f"{item['content']}\n-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def aggregate_info_relation_violation_responses(info_dict: dict, screenshot_list: list):
    response_1 = detect_info_relation_violation(info_dict)
    response_2 = detect_info_relation_part_b_violation(info_dict, screenshot_list)
    aggregated_response = aggregate_responses([response_1, response_2])
    final_response = json.dumps(aggregated_response, indent=2)
    return final_response


def detect_meaningful_sequence_violation(meaningful_sequence_list: list, white_space_list: list,
                                         element_rearranged_list: list):
    """
    Detect violations related to meaningful sequence according to WCAG SC 1.3.2.
    """
    user_message_base = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 1.3.2. "
        "Please focus solely on this criterion. Identify whether the elements comply with this WCAG criterion and "
        "describe any issues found.\n"
        "Below are common failures associated with this criterion:\n"
        "1. Using an HTML layout table that does not make sense when linearized. You will receive the original and "
        "linearized versions of the table to evaluate if the table's meaning is preserved when linearized.\n"
        "2. Using white space characters to control spacing within a word.\n"
        "3. Incorrect reading order in source code. You will receive elements that might be rearranged to assess if "
        "the content follows the correct reading order.\n"
        "The related information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    # Combine all elements into one list
    combined_data = [{'type': 'original_table', 'content': item['original'], 'linearized': item['linearized']}
                     for item in meaningful_sequence_list]
    combined_data.extend([{'type': 'whitespace', 'content': ws} for ws in white_space_list])
    combined_data.extend([{'type': 'rearranged', 'content': el} for el in element_rearranged_list])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        user_message = user_message_base

        for item in chunk:
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

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response
    return {}



def detect_name_role_value_violation(name_role_value_dict: dict, form_dict: dict):
    """
    Detect if there are name, role, and value violations according to WCAG SC 4.1.2.
    """
    user_message_base = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 4.1.2. "
        "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific WCAG "
        "criterion,"
        "providing a description of any issues found.\n"
        "Below are the test rules for this criterion:\n"
        "1. **Buttons**: Ensure buttons have non-empty, descriptive accessible names.\n"
        "2. **Aria-hidden**: Elements with 'aria-hidden' should not receive sequential focus navigation.\n"
        "3. **Form and Input Elements**:"
        "- Form fields should have non-empty, descriptive accessible names."
        "- Provide names for each part of a multi-part form field (e.g., US telephone number)."
        "- Each form field should have only one label."
        "- Field hints should be associated with specific form fields.\n"
        "4. **Menuitem**: Menu items should have non-empty, descriptive accessible names.\n"
        "5. **Iframes**:"
        "- Iframes should have non-empty, descriptive accessible names."
        "- Iframes with identical accessible names should have equivalent purposes.\n"
        "6. **Script-Controlled Elements**: When using scripts to make div or span elements into user interface "
        "controls, a role should be provided. Assess whether these elements function as controls and if appropriate "
        "roles are provided.\n"
        "7. **Links**: Links should have valid hypertext references.\n"
        "The related information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    # Combine all elements into one list
    combined_data = [{'type': 'button', 'content': item} for item in name_role_value_dict.get('button', [])]
    combined_data.extend(
        [{'type': 'aria-hidden', 'content': item} for item in name_role_value_dict.get('aria-hidden', [])])
    combined_data.extend([{'type': 'form', 'content': item} for item in form_dict.get('forms', [])])
    combined_data.extend([{'type': 'input', 'content': item} for item in form_dict.get('inputs', [])])
    combined_data.extend([{'type': 'menuitem', 'content': item} for item in name_role_value_dict.get('menuitem', [])])
    combined_data.extend([{'type': 'iframe', 'content': item} for item in name_role_value_dict.get('iframe', [])])
    combined_data.extend(
        [{'type': 'script-controlled', 'content': item} for item in name_role_value_dict.get('script-controlled', [])])
    combined_data.extend([{'type': 'link', 'content': item} for item in name_role_value_dict.get('link', [])])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        user_message = user_message_base

        for item in chunk:
            user_message += f"{item['type'].capitalize()}:\n"
            user_message += f"{item['content']}\n"
            user_message += "-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_moving_updating_element_violation(moving_updating_dict: dict):
    """
    Detect if there are moving or updating element violations according to WCAG SC 2.2.2.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC "
             "2.2.2."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG criterion,"
             "providing a description of any issues found.\n"
             "Below are the common failures for this criterion:\n"
             "1. Using the <blink> element.\n"
             "2. Using the <marquee> element.\n"
             "3. Including scrolling content without a mechanism to pause and restart it, when movement is not "
             "essential to the activity. You will be provided with two screenshots taken 5 seconds apart to assess "
             "this.\n"
             "4. For text content that changes automatically, there must be a mechanism to pause, stop, or hide the "
             "updates. The provided screenshots indicate detected text updates. Rely on these screenshots to "
             "determine if such a mechanism exists.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    # Combine all elements into one list
    combined_data = [{'type': 'blink', 'content': item} for item in moving_updating_dict.get('blink', [])]
    combined_data.extend([{'type': 'marquee', 'content': item} for item in moving_updating_dict.get('marquee', [])])
    combined_data.extend(
        [{'type': 'moving_image', 'content': item} for item in moving_updating_dict.get('moving_images', [])])
    combined_data.extend(
        [{'type': 'updating_image', 'content': item} for item in moving_updating_dict.get('updating_images', [])])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()

            for item in chunk:
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

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response
    return {}


def detect_bypass_blocks_violation(bypass_block_dict: dict):
    """
    Detect if there are bypass blocks violations according to WCAG SC 2.4.1.
    """
    user_message_base = (
        "You will be provided with several elements from a webpage to determine if there is any violation of WCAG SC "
        "2.4.1. Focus solely on this criterion. Your task is to determine whether the elements comply with the "
        "specific WCAG"
        "criterion, providing a description of any issues found. Each element corresponds to one or several test "
        "rules. Below are the test"
        "rules:\n"
        "**Elements with Application Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "2. Each element must have an accessible name describing its purpose.\n"
        "**Elements with Article Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "**Elements with Banner Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "2. There must be only one element with a banner role on the page.\n"
        "**Elements with Complementary Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "2. Each element must have an accessible name.\n"
        "**Elements with Contentinfo Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "2. A page, document, or application should have only one element with a contentinfo role.\n"
        "**Elements with Document Role**:\n"
        "1. All elements must have unique labels.\n"
        "**Elements with Form Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "**Elements with Main Role**:\n"
        "1. All elements must have unique labels.\n"
        "**Elements with Navigation Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "**Elements with Region Role**:\n"
        "1. Each element must have a unique label.\n"
        "2. Each element must have an accessible name describing its purpose.\n"
        "**Elements with Search Role**:\n"
        "1. Each element must have a unique label describing its purpose.\n"
        "**Hyperlinks**:\n"
        "1. Determine whether the hyperlink is used to bypass content.\n"
        "2. If so, ensure the description of the hyperlink clearly communicates where it links to. A violation occurs "
        "if the skip link description is too general.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    # Combine all elements into one list
    combined_data = [{'type': key, 'content': element} for key, elements in bypass_block_dict.items() for element in
                     elements]

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        user_message = user_message_base

        for item in chunk:
            user_message += f"{item['type'].capitalize()} elements:\n"
            user_message += f"{item['content']}\n"
            user_message += "-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_location_violation(location_dict: dict):
    """
    Detect if there are location violations according to WCAG SC 2.4.8.
    """
    user_message = [
        {"type": "text",
         "text": (
             "You will be provided with a screenshot and title information from a webpage to determine if there is any "
             "violation of WCAG SC 2.4.8. Focus solely on this criterion. Your task is to determine whether the "
             "elements comply with the specific WCAG criterion,"
             "providing a description of any issues found.\n"
             "Below are the test rules:\n"
             "1. Use the screenshot to identify mechanisms that help users understand their location within a set of "
             "web pages. These mechanisms include, but are not limited to, breadcrumb trails, navigation bars, "
             "site maps, or other visual indicators that provide context about the user's current page within the "
             "overall site structure.\n"
             "2. Use the title information to determine if the title of the web page describes its relationship to the "
             "collection to which it belongs.\n"
             "A violation occurs if both rules fail.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{location_dict['screenshot']}"}},
        {"type": "text", "text": f"Title information: {location_dict['title']}"}]
    completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
    detection_result = completion.choices[0].message.content
    final_response = json.dumps(detection_result, indent=2)
    return final_response


def detect_sensory_characteristics_violation(sensory_dict: dict):
    """
    Detect if there are sensory characteristics violations according to WCAG SC 1.3.3.
    """
    user_message_base = (
        "You will be provided with elements from a webpage to determine if there is any violation of WCAG SC 1.3.3. "
        "These elements have been identified by an upstream agent that detected sensory characteristics. The elements "
        "are formatted as the parent of the sensory characteristic elements, followed by the parent's immediate "
        "sibling, if one exists."
        "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific WCAG "
        "criterion,"
        "providing a description of any issues found.\n"
        "Below is the test rule for this criterion:\n"
        "1. When content is identified through a visual reference, there must also be non-visual references identifying"
        "the same content. If this is not the case, it is a violation.\n"
        "Additionally, consider the common failure:\n"
        "1. Identifying content solely by its shape or location is a failure of Success Criterion 1.3.3.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    # Combine all elements into one list
    combined_data = [{'type': 'other_sensory', 'content': item} for item in sensory_dict.get('other_sensory', [])]
    combined_data.extend([{'type': 'color_sensory', 'content': item} for item in sensory_dict.get('color_sensory', [])])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        user_message = user_message_base

        for item in chunk:
            if item['type'] == 'other_sensory':
                user_message += "Elements with sensory characteristics (other than color):\n"
            elif item['type'] == 'color_sensory':
                user_message += "Elements with color sensory characteristics:\n"
            user_message += f"{item['content']}\n"
            user_message += "-------------\n"

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_use_of_color_violation(color_dict: dict):
    """
    Detect violations related to the use of color according to WCAG SC 1.4.1.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots of link and form elements from a webpage to determine if there is "
             "any"
             "violation of WCAG SC 1.4.1. Focus solely on this criterion. Use the screenshots to identify the "
             "elements present before making the assessment."
             "Do not describe elements that are not visible in the screenshots.\n"
             "Below are the test rules for this criterion:\n"
             "1. Ensure that each link identifiable by color (hue) is also visually distinguishable by other means ("
             "e.g., underlined, bold, italicized, sufficient difference in lightness).\n"
             "2. For all required fields or error fields identified using color differences, ensure there is an "
             "additional non-color method to indicate the required field or error (e.g., asterisk, label, "
             "or text description).\n"
             "A violation occurs if any of the rules are not met.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    # Combine all elements into one list
    combined_data = [{'type': 'link', 'content': link} for link in color_dict.get('links', [])]
    combined_data.extend([{'type': 'form', 'content': form} for form in color_dict.get('forms', [])])

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()

            for item in chunk:
                if item['type'] == 'link':
                    user_message.append({"type": "text", "text": "Link screenshots:\n"})
                elif item['type'] == 'form':
                    user_message.append({"type": "text", "text": "Form screenshots:\n"})
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['content']}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_target_size_minimum_violation(target_size_dict: dict):
    """
    Detect violations related to the minimum target size according to WCAG SC 2.5.8.
    """
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with targets that are smaller than 24x24 CSS pixels from a webpage to determine "
                "if there is any violation of WCAG SC 2.5.8. For each target, you will also receive screenshots with a "
                "24 CSS pixel diameter circle centered on the bounding box of the target. The circle is drawn in red. "
                "Focus solely on this criterion. Determine whether the elements comply with the specific WCAG "
                "criterion,"
                "providing a description of any issues found.\n"
                "Below are the exceptions to this criterion:\n"
                "1. **Spacing**: Undersized targets are positioned so that if a 24 CSS pixel diameter circle is "
                "centered on the bounding box, the circles do not intersect another target or another undersized "
                "target's circle. Use the cropped image to assess this.\n"
                "2. **Equivalent**: The function can be achieved through a different control on the same page that "
                "meets this criterion. Assess this using the full screenshot.\n"
                "3. **Inline**: The target is within a sentence or its size is otherwise constrained by the "
                "line-height of non-target text. Assess this using the full screenshot.\n"
                "4. **Essential**: The specific presentation of the target is essential or legally required for the "
                "information being conveyed. Assess this using the full screenshot.\n"
                "If none of the exceptions apply, it is a violation.\n"
                "The relevant information for your assessment starts after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    # Combine all elements into one list
    combined_data = [{'type': 'small_element', 'content': element} for element in
                     target_size_dict.get('small_elements', [])]

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()

            for item in chunk:
                element = item['content']
                user_message.append({"type": "text", "text": f"Tag: {element['tag']}\n"})
                user_message.append({"type": "text", "text": "Cropped screenshot:\n"})
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['cropped']}"}})
                user_message.append({"type": "text", "text": "Full screenshot:\n"})
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['full']}"}})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_target_size_enhanced_violation(target_size_dict: dict):
    """
    Detect violations related to the enhanced minimum target size according to WCAG SC 2.5.5.
    """
    user_message_base = [
        {
            "type": "text",
            "text": (
                "You will be provided with targets that are smaller than 44x44 CSS pixels from a webpage to determine "
                "if there is any violation of WCAG SC 2.5.5. Focus solely on this criterion. Determine whether the "
                "elements comply with the specific WCAG criterion,"
                "providing a description of any issues found.\n"
                "Below are the exceptions to this criterion:\n"
                "1. **Equivalent**: The function can be achieved through a different control on the same page that "
                "meets this criterion. Assess this using the full screenshot.\n"
                "2. **Inline**: The target is within a sentence or its size is otherwise constrained by the "
                "line-height of non-target text. Assess this using the full screenshot.\n"
                "3. **Essential**: The specific presentation of the target is essential or legally required for the "
                "information being conveyed. Assess this using the full screenshot.\n"
                "If none of the exceptions apply, it is a violation.\n"
                "The relevant information for your assessment starts after the dashed line.\n"
                "------------------\n"
            )
        }
    ]
    # Combine all elements into one list
    combined_data = [{'type': 'small_element_44', 'content': element} for element in
                     target_size_dict.get('small_elements_44', [])]

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    responses = []

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()

            for item in chunk:
                element = item['content']
                user_message.append({"type": "text", "text": f"Tag: {element['tag']}\n"})
                user_message.append({"type": "text", "text": "Full screenshot:\n"})
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{element['full']}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def is_valid_base64(data):
    try:
        # Check if the data can be decoded
        base64.b64decode(data, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def detect_visual_presentation_violation(visual_list: list):
    """
    Detect violations related to visual presentation according to WCAG SC 1.4.8.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with blocks of text from a webpage to determine if there is any violation of WCAG "
             "SC 1.4.8. Focus solely on this criterion. Your task is to determine whether the elements comply with "
             "the specific WCAG criterion,"
             "providing a description of any issues found.\n"
             "Below are the test rules for this criterion:\n"
             "1. Foreground and background colors can be selected by the user.\n"
             "2. Width is no more than 80 characters or glyphs (40 if CJK).\n"
             "3. Text is not justified (aligned to both the left and right margins).\n"
             "4. Line spacing (leading) is at least space-and-a-half within paragraphs, and paragraph spacing is at "
             "least 1.5 times larger than the line spacing.\n"
             "5. Text can be resized without assistive technology up to 200% without requiring horizontal scrolling "
             "on a full-screen window. Use the full screenshot to check for horizontal scrolling.\n\n"
             "If any of the rules fail, check if there is a mechanism on screen to achieve compliance. If not, "
             "it is a violation.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(visual_list))

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append(
                {"type": "text", "text": "The related information about the blocks of text is below:\n"})

            for block in chunk:
                message_text = ""
                for key, value in block.items():
                    if key != "screenshot":
                        message_text += f"{key}: {value}\n"
                    else:
                        user_message.append(
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{block['screenshot']}"}})
                user_message.append({"type": "text", "text": message_text})
                user_message.append({"type": "text", "text": "-------------\n"})
            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response


def detect_text_spacing_violation(text_spacing_list: list):
    """
    Detect violations related to text spacing adjustments according to WCAG SC 1.4.12.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with one or several screenshots from a webpage where line height, paragraph spacing,"
             "letter spacing, and word spacing have been adjusted. Your task is to determine if there is any violation "
             "of WCAG SC 1.4.12. Focus solely on this criterion. Determine whether the elements comply with the "
             "specific"
             "WCAG criterion, providing a description of any issues found.\n"
             "Common failure for this criterion:\n"
             "1. Clipped or overlapped content when text spacing is adjusted.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(text_spacing_list))

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append({"type": "text", "text": "The screenshots are below:\n"})

            for text_spacing in chunk:
                user_message.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{text_spacing}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_error_identified_violation(error_identified_screenshot: list):
    """
    Detect violations related to error identification according to WCAG SC 3.3.1.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.3.1."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "Test rule for this criterion:\n"
             "1. If an input error is automatically detected, the item in error must be identified, and the error "
             "must be described to the user in text. If the error is identified and described without a suggestion "
             "for fixing it, it is not considered a violation.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(error_identified_screenshot))

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append({"type": "text", "text": "The screenshots are below:\n"})

            for screenshot in chunk:
                user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_error_suggestion_violation(error_suggestion_screenshot: list):
    """
    Detect violations related to providing error correction suggestions according to WCAG SC 3.3.3.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.3.3."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "Test rule for this criterion:\n"
             "1. If an input error is detected and suggestions for correction are known, then the suggestions must be "
             "provided to the user, unless doing so would jeopardize the security or purpose of the content.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(error_suggestion_screenshot))

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append({"type": "text", "text": "The screenshots are below:\n"})

            for screenshot in chunk:
                user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_abbreviations_violation(abbreviations_list: list):
    """
    Detect violations related to the use of abbreviations according to WCAG SC 3.1.4.
    """
    user_message_base = [
        {"type": "text",
         "text": (
             "You will be provided with screenshots from a webpage to determine if there is any violation of WCAG SC "
             "3.1.4."
             "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific "
             "WCAG"
             "criterion, providing a description of any issues found.\n"
             "Test rule for this criterion:\n"
             "1. If an abbreviation is used in the text, the full form of the abbreviation must be provided. If not, "
             "it is a violation.\n"
             "The relevant information for your assessment starts after the dashed line.\n"
             "------------------\n"
         )}
    ]
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(abbreviations_list))

    for chunk in chunked_data:
        try:
            user_message = user_message_base.copy()
            user_message.append({"type": "text", "text": "The screenshots are below:\n"})

            for screenshot in chunk:
                user_message.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}})
                user_message.append({"type": "text", "text": "-------------\n"})

            completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
            responses.append(completion.choices[0].message.content)
        except Exception as e:
            method_name = inspect.currentframe().f_code.co_name
            print(f"Error in {method_name}: {e}")
            continue

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_non_text_contrast_violation(focusable_elements: list):
    """
    Detect non-text contrast violations for focusable elements according to WCAG SC 1.4.11.
    """
    user_message_base = (
        "You will be provided with focusable elements from a webpage to determine if there is any violation of WCAG SC "
        "1.4.11 (Non-text Contrast). Each element is described by its HTML structure and CSS properties. "
        "Focus solely on this criterion. Your task is to determine whether the elements comply with the specific WCAG "
        "criterion,"
        "providing a description of any issues found.\n"
        "Common failures for this criterion include, but are not limited to:\n"
        "1. Insufficient contrast ratio between the focus indicator (e.g., border or outline) and the adjacent "
        "background. The minimum contrast ratio required is 3:1.\n"
        "2. Focus indicators being styled in a way that they become non-visible.\n"
        "Use your expertise and judgment to identify any additional potential violations. The relevant information "
        "for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    responses = []

    # Chunk the data
    chunked_data = list(chunk_data(focusable_elements))

    for chunk in chunked_data:
        user_message = user_message_base
        for element_info in chunk:
            user_message += (
                f"Element HTML: {element_info['element']}\n"
                f"Border Color: {element_info['border_color']}\n"
                f"Outline Color: {element_info['outline_color']}\n"
                f"Background Color: {element_info['background_color']}\n"
                "------------------\n"
            )

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_on_input_violation(special_input_dict, other_input_dict):
    """
    Detect violations related to on-input changes causing context shifts according to WCAG SC 3.2.2.
    """
    user_message_base = (
        "You need to detect violations of WCAG SC 3.2.2. This criterion requires that changing the setting of any user "
        "interface component does not automatically cause a change of context unless the user has been advised of the "
        "behavior beforehand. A change of context includes launching a new window or changing focus. "
        "You will be provided with HTML elements and their associated event handler functions. Determine whether the "
        "elements comply with the specific WCAG criterion, providing a description of any issues found.\n"
        "Test rules for this criterion:\n"
        "1. Changing the value of a field in a form should not submit the form automatically without warning users.\n"
        "2. Changing the selection of a radio button, checkbox, or select list should not launch a new window without "
        "prior warning.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    responses = []

    # Combine data for chunking
    combined_data = [
                        {"type": "special", "html": html, "function": func}
                        for html, func in special_input_dict.items()
                    ] + [
                        {"type": "other", "html": html, "function": func}
                        for html, func in other_input_dict.items()
                    ]

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    for chunk in chunked_data:
        user_message = user_message_base

        special_inputs = [item for item in chunk if item["type"] == "special"]
        other_inputs = [item for item in chunk if item["type"] == "other"]

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

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}


def detect_change_on_request_violation(onclick_dict: dict, onblur_dict: dict):
    """
    Detect violations of WCAG SC 3.2.5 by analyzing elements with onclick and onblur functions.
    This function combines the extracted event handlers and checks for potential violations.
    """
    user_message_base = (
        "You need to detect violations of WCAG SC 3.2.5. This criterion requires that changing the setting of any user "
        "interface component does not automatically cause a change of context unless the user has been advised of the "
        "behavior beforehand. A change of context includes launching a new window or changing focus. "
        "You will be provided with HTML elements and their associated event handler functions. Determine whether the "
        "elements comply with the specific WCAG criterion, providing a description of any issues found.\n"
        "Test rules for this criterion:\n"
        "1. For each element that can be activated, check if it will open a new window. Elements that open new "
        "windows should have associated text indicating this behavior. If not, it is a violation.\n"
        "2. Removing focus from a form element (such as by moving to the next element) should not cause a change of "
        "context.\n"
        "The relevant information for your assessment starts after the dashed line.\n"
        "------------------\n"
    )
    responses = []

    # Combine data for chunking
    combined_data = [
                        {"type": "onclick", "html": html, "function": func}
                        for html, func in onclick_dict.items()
                    ] + [
                        {"type": "onblur", "html": html, "function": func}
                        for html, func in onblur_dict.items()
                    ]

    # Chunk the combined data
    chunked_data = list(chunk_data(combined_data))

    for chunk in chunked_data:
        user_message = user_message_base

        onclick_elements = [item for item in chunk if item["type"] == "onclick"]
        onblur_elements = [item for item in chunk if item["type"] == "onblur"]

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

        completion = send_request_to_model("gpt-4o-2024-08-06", sys_message, user_message)
        responses.append(completion.choices[0].message.content)

    if responses:
        aggregated_response = aggregate_responses(responses)
        final_response = json.dumps(aggregated_response, indent=2)
        return final_response

    return {}
