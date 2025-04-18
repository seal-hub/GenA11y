import json
import os
import time
import pandas as pd
from dotenv import dotenv_values
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from consts import JSON_FORMAT

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '..', '..', 'A11yDetector', '.env')
config = dotenv_values(env_path)
client = OpenAI(api_key=config["OPENAI_API_KEY"])

sys_message = ("You are an Accessibility Expert (WCAG Specialist) responsible for detecting WCAG violations on "
               "websites. Your expertise is crucial in making the web more accessible for everyone. Please analyze the "
               "provided page source of the website for compliance with the "
               "specified WCAG success criterion. Be confident in your expertise. Do not omit any issue. After "
               "analyzing all elements, "
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
               "but exclude any nested elements or content inside. "
               )


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
                                                messages=[{"role": "system", "content": sys_message},
                                                          {"role": "user", "content": user_message}],
                                                temperature=0.0, )
    return completion


def read_wcag_criterion_and_urls_from_excel(file_path, start_index=None, end_index=None):
    """
    Read the list of values from the 'WCAG Criterion' and 'URL' columns in an Excel file.
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


def non_text_content_violation_prompting(page_source):
    """
    WCAG 1.1.1 Non-text Content
    """
    user_message_template = (
        "Please analyze the provided page source of the website for compliance with WCAG SC 1.1.1. "
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
        "6. Images not included in the accessibility tree should be marked as decorative.\n"
        "**Common Failures for SC 1.1.1:**\n"
        "- **F13**: Failure due to text alternatives not including information conveyed by color "
        "differences"
        "in the image.\n"
        "- **F20**: Failure due to not updating text alternatives when changes occur in non-text content.\n"
        "- **F30**: Using text alternatives that are not true alternatives (e.g., filenames or placeholder text).\n"
        "- **F38**: Failure due to not marking up decorative images so assistive technology can ignore them.\n"
        "- **F39**: Failure due to providing non-null text alternatives (e.g., 'alt=\"spacer\"') for images "
        "that should be ignored by assistive technology.\n"
        "- **F65**: Omitting the alt attribute or text alternative on img elements, area elements, and input elements "
        "of type 'image', except when the image is purely decorative.\n"
        "- **F67**: Failure due to providing long descriptions for non-text content that do not serve the "
        "same purpose or present the same information.\n"
        "The information you need to assess starts after the dashed line below.\n"
        "----------------------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_template)
    return response.choices[0].message.content


def info_relations_violation_prompting(page_source):
    """
    WCAG 1.3.1 Info and Relationships
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.3.1. Focus solely on "
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
        "In addition to the common failures, below are the test rules for SC 1.3.1:\n"
        "1. Content should be organized into well-defined groups or chunks using "
        "headings, lists, paragraphs, and other visual mechanisms. \n"
        "2. Use of actual headings and lists instead of text formatting to convey structure.\n"
        "3. Links should be distinguishable from surrounding text. \n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def meaningful_sequence_violation_prompting(page_source):
    """
    WCAG 1.3.2 Meaningful Sequence
    """
    user_message_base = (
        "You will be provided with page source to determine if there is any violation of WCAG SC 1.3.2. "
        "Please focus solely on this criterion. Identify whether the elements comply with this WCAG criterion and "
        "describe any issues found.\n"
        "Below are common failures associated with this criterion:\n"
        "1. Using an HTML layout table that does not make sense when linearized.\n"
        "2. Using white space characters to control spacing within a word.\n"
        "3. Incorrect reading order in source code.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def sensory_characteristic_violation_prompting(page_source):
    """
    WCAG 1.3.3 Sensory Characteristics
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.3.3. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below is the test rule for this criterion:\n"
        "1. When content is identified through a visual reference, there must also be non-visual references identifying"
        "the same content. If this is not the case, it is a violation.\n"
        "Additionally, consider the common failure:\n"
        "1. Identifying content solely by its shape or location is a failure of Success Criterion 1.3.3.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def orientation_violation_prompting(page_source):
    """
    WCAG 1.3.4 Orientation
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.3.4. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below is the test rule for this criterion:\n"
        "1. The content must not be restricted to one view. If the content "
        "does not display correctly"
        "or is restricted in either landscape or portrait mode, it is a violation.\n"
        "2. Determine if there is a message prompting users to reorient their device. If such a message "
        "exists, it is a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def identify_input_purpose_violation_prompting(page_source):
    """
    WCAG 1.3.5 Identify Input Purpose
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.3.5. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are common failures associated with this criterion, but violations are not limited to these examples. "
        "Use your expertise and judgment to identify any additional violations:\n"
        "1. Failure of Success Criterion 1.3.5 due to incorrect autocomplete attribute values.\n"
        "2. Failure of Success Criterion 1.3.5 when the purpose of each input field that collects information about "
        "the user cannot be programmatically determined when the field serves a common purpose.\n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def use_of_color_violation_prompting(page_source):
    """
    WCAG 1.4.1 Use of Color
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.1. Focus solely on this "
        "criterion and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. Ensure that each link identifiable by color (hue) is also visually distinguishable by other means ("
        "e.g., underlined, bold, italicized, sufficient difference in lightness).\n"
        "2. For all required fields or error fields identified using color differences, ensure there is an "
        "additional non-color method to indicate the required field or error (e.g., asterisk, label, "
        "or text description).\n"
        "A violation occurs if any of the rules are not met.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def audio_control_violation_prompting(page_source):
    """
    WCAG 1.4.2 Audio Control
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.2. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. If audio plays automatically and there is no mechanism to stop or pause it, the audio should not "
        "play for more than 3 seconds. \n"
        "2. If audio plays automatically for more than 3 seconds, there must be a mechanism to stop or pause "
        "the audio."
        "A violation occurs if any of the rules are not met.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def contrast_violation_prompting(page_source):
    """
    WCAG 1.4.3 Contrast (Minimum)
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.3. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. Text and its background must have a contrast ratio of at least 4.5:1.\n"
        "2. Large text (defined as at least 18 point for regular text or 14 point for bold text) and its "
        "background must have a contrast ratio of at least 3:1."
        "3. When background images are used, they must provide sufficient contrast with the foreground text "
        "to ensure readability."
        "A violation occurs if any of the rules are not met.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def resize_text_violation_prompting(page_source):
    """
    WCAG 1.4.4 Resize Text
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.4. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. The content attribute on a meta element with a name attribute value of 'viewport' must not "
        "restrict zoom. Specifically,"
        "the 'user-scalable' property should not be set to 'no,' and the 'maximum-scale' property should be "
        "at least 2.\n"
        "2. When text is resized up to 200%, it should not cause text, images, or controls to be clipped, "
        "truncated, or obscured."
        "3. Text-based form controls should resize appropriately when visually rendered text is resized up to "
        "200%. Using fixed units such as pt and px for text size is a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def image_of_text_violation_prompting(page_source):
    """
    WCAG 1.4.5 Images of Text
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.5. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "According to WCAG SC 1.4.5, images should not contain visible text unless one of the following "
        "conditions is met:\n"
        "1. The image is purely decorative.\n"
        "2. The text is not a significant part of the image.\n"
        "3. The presentation of the text is essential.\n"
        "Use your judgment to determine whether each image meets these exceptions.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def contrast_enhanced_violation_prompting(page_source):
    """
    WCAG 1.4.6 Contrast (Enhanced)
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.6. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Test rules for this criterion include:\n"
        "1. Text and its background must have a contrast ratio of at least 7:1.\n"
        "2. Large text (defined as at least 18 point for regular text or 14 point for bold text) and its "
        "background must have a contrast ratio of at least 4.5:1."
        "3. When background images are used, they must provide sufficient contrast with the foreground text "
        "to ensure readability."
        "A common failure for this criterion includes:\n"
        "- **F24**: Failure due to specifying foreground colors without specifying background colors or vice "
        "versa.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def visual_presentation_violation_prompting(page_source):
    """
    WCAG 1.4.8 Visual Presentation
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.8. Focus solely on this criterion "
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. Foreground and background colors can be selected by the user.\n"
        "2. Width is no more than 80 characters or glyphs (40 if CJK).\n"
        "3. Text is not justified (aligned to both the left and right margins).\n"
        "4. Line spacing (leading) is at least space-and-a-half within paragraphs, and paragraph spacing is at "
        "least 1.5 times larger than the line spacing.\n"
        "5. Text can be resized without assistive technology up to 200% without requiring horizontal scrolling "
        "on a full-screen window. Use the full screenshot to check for horizontal scrolling.\n\n"
        "If any of the rules fail, check if there is a mechanism to achieve compliance. If not, "
        "it is a violation.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def reflow_violation_prompting(page_source):
    """
    WCAG 1.4.10 Reflow
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.10. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Common failures for this criterion include:\n"
        "1. Content disappearing and not being available after reflow.\n"
        "2. Content requiring scrolling in two dimensions to view.\n"
        "The related information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def text_spacing_violation_prompting(page_source):
    """
    WCAG 1.4.12 Text Spacing
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 1.4.12. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Common failure for this criterion:\n"
        "1. Clipped or overlapped content when line height, paragraph spacing,"
        "letter spacing, and word spacing have been adjusted.\n"
        "The related information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def timing_adjustable_violation_prompting(page_source):
    """
    WCAG 2.2.1 Timing Adjustable
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.2.1. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Common failures for this criterion include:\n"
        "1. **F40**: Failure due to using meta redirect with a time limit.\n"
        "2. **F41**: Failure due to using meta refresh to reload the page.\n"
        "3. **F58**: Failure due to using server-side techniques to automatically redirect pages after a "
        "time-out.\n"
        "Test rules for this criterion include:\n"
        "1. If a web page uses a meta element to redirect to another page, and the numerical value for the "
        "seconds until refresh in the content attribute is less than 1 or greater than 72000, it is *not* a "
        "violation.\n"
        "2. Otherwise, there should be a mechanism to turn off, adjust, or extend time limits. \n"
        "The related information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def pause_stop_hide_violation_prompting(page_source):
    """
    WCAG 2.2.2 Pause, Stop, Hide
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.2.2. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the common failures for this criterion:\n"
        "1. Using the <blink> element.\n"
        "2. Using the <marquee> element.\n"
        "3. Including scrolling content without a mechanism to pause and restart it, when movement is not "
        "essential to the activity.\n"
        "4. For text content that changes automatically, there must be a mechanism to pause, stop, or hide the "
        "updates.\n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def bypass_blocks_violation_prompting(page_source):
    """
    WCAG 2.4.1 Bypass Blocks
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.4.1. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules:\n"
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
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def page_titled_violation_prompting(page_source):
    """
    WCAG 2.4.2 Page Titled
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.4.2. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Below are the test rules for this criterion:\n"
        "1. The page title should not be null. \n"
        "2. The page title should be descriptive based on the portions of the webpage. \n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def link_purpose_context_violation_prompting(page_source):
    """
    WCAG 2.4.4 Link Purpose (In Context)
    """
    user_message_base = (
        "You will be provided with the page source to assess for any violations of WCAG SC 2.4.4. Unlike SC 2.4.9, "
        "this criterion allows relying on contextual information to determine if a"
        "link is descriptive. A link should clearly indicate its purpose without requiring the user to click on it, "
        "and it should not be"
        "too general, such as 'a link'."
        "Please focus exclusively on this criterion."
        "Determine whether the elements comply with the specific WCAG criterion and describe any issues identified.\n"
        "Test rules for this criterion include:\n"
        "1. The link must have a non-empty accessible name.\n"
        "2. The link in **context** should be descriptive. **Context** refers to the information provided by the "
        "link's ancestors and siblings."
        "If these elements provide enough descriptive information, then the link is compliant and not considered a "
        "violation.\n"
        "3. Links with identical accessible names in the same context must serve an equivalent purpose.\n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def multiple_ways_violation_prompting(page_source):
    """
    WCAG 2.4.5 Multiple Ways
    """
    user_message_base = ("You will be provided with the page source to determine if there is any "
                         "violation of WCAG SC 2.4.5. Please focus solely on this criterion. \n"
                         "Test rule for this criterion:\n"
                         "1. Determine whether the page provides at least two methods for "
                         "reaching the same content."
                         "Common techniques include:\n"
                         "- **G125**: Providing links to navigate to related web pages.\n"
                         "- **G64**: Providing a Table of Contents.\n"
                         "- **G63**: Providing a site map.\n"
                         "- **G161**: Providing a search function to help users find content.\n"
                         "- **G126**: Providing a list of links to all other web pages.\n"
                         "- **G185**: Linking to all of the pages on the site from the home page.\n"
                         "The page should use two or more of these techniques to offer multiple ways to access "
                         "content. If the page uses alternative methods"
                         "not listed above but still provides multiple ways to reach content, it may still be "
                         "compliant. Use your judgment and expertise to assess these cases.\n"
                         "The information for your assessment begins after the dashed line.\n"
                         "------------------\n"
                         f"Page Source: {page_source}"
                         )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def headers_labels_violation_prompting(page_source):
    """
    WCAG 2.4.6 Headings and Labels
    """
    user_message_base = (
        "You will receive the page source. Your task is to determine compliance "
        "with WCAG SC 2.4.6. Headings should be descriptive. Labels should clearly describe the purpose of their "
        "corresponding inputs. Focus solely on this criterion. Identify any issues and describe them. The relevant "
        "information begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def location_violation_prompting(page_source):
    """
    WCAG 2.4.8 Location
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.4.8. Focus solely on this "
        "criterion. Your task is to determine whether the elements comply with the specific WCAG criterion, "
        "providing a description of any issues found.\n"
        "Below are the test rules:\n"
        "1. There should be mechanisms that help users understand their location within a set of "
        "web pages. These mechanisms include, but are not limited to, breadcrumb trails, navigation bars, "
        "site maps, or other visual indicators that provide context about the user's current page within the "
        "overall site structure.\n"
        "2. Use the title information to determine if the title of the web page describes its relationship to the "
        "collection to which it belongs.\n"
        "A violation occurs if both rules fail.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def link_purpose_link_only_violation_prompting(page_source):
    """
    WCAG 2.4.9 Link Purpose (Link Only)
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.4.9."
        "Unlike SC 2.4.4, this criterion requires that you evaluate the link's descriptiveness based solely on the "
        "link itself,"
        "without considering its surrounding context. A link should clearly indicate its purpose without requiring "
        "the user to click on it,"
        "and it should not be too general, such as 'a link'."
        "Please focus exclusively on this criterion. Determine whether the elements comply with WCAG SC 2.4.9 and "
        "describe any issues identified.\n"
        "Test rules for this criterion include:\n"
        "1. The link must have a non-empty accessible name.\n"
        "2. The link must be descriptive, clearly conveying its purpose.\n"
        "3. Links with identical accessible names must serve an equivalent purpose.\n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def section_headings_violation_prompting(page_source):
    """
    WCAG 2.4.10 Section Headings
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.4.10. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "A section heading should clearly describe the purpose of the section, "
        "helping users understand its content. In this context, a 'section' refers to a distinct part of the "
        "content that is logically grouped together, such as a group of paragraphs, a form, a list, or any other "
        "cohesive unit of information. Specifically,"
        "determine"
        "whether each section has a descriptive heading. The test rules for this criterion are:\n"
        "1. Each section should have a heading.\n"
        "2. The heading should be descriptive.\n"
        "The information for your assessment begins after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def target_size_enhanced_violation_prompting(page_source):
    """
    WCAG 2.5.5 Target Size (Enhanced)
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 2.5.5. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Below is the test rules for this criterion:\n"
        "1. The target size for pointer inputs must be at least 44 by 44 CSS pixels.\n"
        "Below are the exceptions to this criterion:\n"
        "1. **Equivalent**: The function can be achieved through a different control on the same page that "
        "meets this criterion.\n"
        "2. **Inline**: The target is within a sentence or its size is otherwise constrained by the "
        "line-height of non-target text.\n"
        "3. **Essential**: The specific presentation of the target is essential or legally required for the "
        "information being conveyed. \n"
        "If none of the exceptions apply, it is a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def target_size_minimum_violation_prompting(page_source):
    """
    WCAG 2.5.8 Target Size (Minimum)
    """
    user_message_base = (
        "You will be provided with the page source to determine "
        "if there is any violation of WCAG SC 2.5.8. Determine whether the elements comply with the specific WCAG "
        "criterion, providing a description of any issues found.\n"
        "Each target size should be greater than 24x24 CSS pixels. Except:\n"
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
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def language_violation_prompting(page_source):
    """
    WCAG 3.1.1 Language of Page; WCAG 3.1.2 Language of Parts
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.1.1 and SC 3.1.2. Focus solely on "
        "these criteria"
        "and determine whether the elements conform to them, describing any issues if found."
        "Follow the six test rules below: \n"
        "1. The HTML page should have a lang attribute.\n"
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
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def abbreviation_violation_prompting(page_source):
    """
    WCAG 3.1.4 Abbreviation
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.1.4. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Test rule for this criterion:\n"
        "1. If an abbreviation is used in the text, the full form of the abbreviation must be provided. If not, "
        "it is a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def on_input_violation_prompting(page_source):
    """
    WCAG 3.2.2 On Input
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.2.2. This criterion requires that "
        "changing the setting of any user"
        "interface component does not automatically cause a change of context unless the user has been advised of the "
        "behavior beforehand. A change of context includes launching a new window or changing focus. Focus solely on "
        "this criterion and determine whether the elements conform to it, describing any issues if found."
        "Test rules for this criterion:\n"
        "1. Changing the value of a field in a form should not submit the form automatically without warning users.\n"
        "2. Changing the selection of a radio button, checkbox, or select list should not launch a new window without "
        "prior warning.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def change_on_request_violation_prompting(page_source):
    """
    WCAG 3.2.5 Change on Request
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.2.5. This criterion requires that "
        "changing the setting of any user"
        "interface component does not automatically cause a change of context unless the user has been advised of the "
        "behavior beforehand. A change of context includes launching a new window or changing focus. "
        "Determine whether the "
        "elements comply with the specific WCAG criterion, providing a description of any issues found.\n"
        "Test rules for this criterion:\n"
        "1. For each element that can be activated, check if it will open a new window. Elements that open new "
        "windows should have associated text indicating this behavior. If not, it is a violation.\n"
        "2. Removing focus from a form element (such as by moving to the next element) should not cause a change of "
        "context.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def error_identification_violation_prompting(page_source):
    """
    WCAG 3.3.1 Error Identification
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.3.1. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Test rule for this criterion:\n"
        "1. If an input error is automatically detected, the item in error must be identified, and the error "
        "must be described to the user in text. If the error is identified and described without a suggestion "
        "for fixing it, it is not considered a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def label_instructions_violation_prompting(page_source):
    """
    WCAG 3.3.2 Labels or Instructions
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.3.2. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Test rule for this criterion:\n"
        "1. For user interface components that require user input, such as form fields, radio buttons, and checkboxes, "
        "each component must have a label or instructions associated with it. If a label or instruction is not "
        "provided, it is a violation.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def error_suggestion_violation_prompting(page_source):
    """
    WCAG 3.3.3 Error Suggestion
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 3.3.3. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
        "Test rule for this criterion:\n"
        "1. If an input error is detected and suggestions for correction are known, then the suggestions must be "
        "provided to the user, unless doing so would jeopardize the security or purpose of the content.\n"
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def name_role_value_violation_prompting(page_source):
    """
    WCAG 4.1.2 Name, Role, Value
    """
    user_message_base = (
        "You will be provided with page source to assess compliance with WCAG SC 4.1.2. Focus solely on this criterion"
        "and determine whether the elements conform to it, describing any issues if found."
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
        "The information for your assessment starts after the dashed line.\n"
        "------------------\n"
        f"Page Source: {page_source}"
    )
    response = send_request_to_model("gpt-4o-2024-08-06", user_message_base)
    return response.choices[0].message.content


def save_results_to_json(results, index, output_folder):
    """Save the results to a JSON file under the Results folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    file_name = os.path.join(output_folder, f"{index}.json")
    with open(file_name, 'w') as json_file:
        json.dump(results, json_file, indent=8)


def map_wcag_criterion_to_prompting_function(criterion, page_source):
    if 'SC 1.1.1 Non-text Content (Level A)' in criterion:
        result = non_text_content_violation_prompting(page_source)
    elif 'SC 1.3.1: Info and Relationships (Level A)' in criterion:
        result = info_relations_violation_prompting(page_source)
    elif 'SC 1.3.2: Meaningful Sequence (Level A)' in criterion:
        result = meaningful_sequence_violation_prompting(page_source)
    elif 'SC 1.3.3: Sensory Characteristics (Level A)' in criterion:
        result = sensory_characteristic_violation_prompting(page_source)
    elif 'SC 1.3.4: Orientation (Level AA)' in criterion:
        result = orientation_violation_prompting(page_source)
    elif 'SC 1.3.5: Identify Input Purpose (Level AA)' in criterion:
        result = identify_input_purpose_violation_prompting(page_source)
    elif 'SC 1.4.1: Use of Color (Level A)' in criterion:
        result = use_of_color_violation_prompting(page_source)
    elif 'SC 1.4.2: Audio Control (Level A)' in criterion:
        result = audio_control_violation_prompting(page_source)
    elif 'SC 1.4.3: Contrast (Minimum) (Level AA)' in criterion:
        result = contrast_violation_prompting(page_source)
    elif 'SC 1.4.4: Resize Text (Level AA)' in criterion:
        result = resize_text_violation_prompting(page_source)
    elif 'SC 1.4.5: Images of Text (Level AA)' in criterion:
        result = image_of_text_violation_prompting(page_source)
    elif 'SC 1.4.6: Contrast (Enhanced) (Level AAA)' in criterion:
        result = contrast_enhanced_violation_prompting(page_source)
    elif 'SC 1.4.8: Visual Presentation (Level AAA)' in criterion:
        result = visual_presentation_violation_prompting(page_source)
    elif 'SC 1.4.10: Reflow (Level AA)' in criterion:
        result = reflow_violation_prompting(page_source)
    elif 'SC 1.4.12: Text Spacing (Level AA)' in criterion:
        result = text_spacing_violation_prompting(page_source)
    elif 'SC 2.2.1: Timing Adjustable (Level A)' in criterion:
        result = timing_adjustable_violation_prompting(page_source)
    elif 'SC 2.2.2: Pause, Stop, Hide (Level A)' in criterion:
        result = pause_stop_hide_violation_prompting(page_source)
    elif 'SC 2.4.1: Bypass Blocks (Level A)' in criterion:
        result = bypass_blocks_violation_prompting(page_source)
    elif 'SC 2.4.2: Page Titled (Level A)' in criterion:
        result = page_titled_violation_prompting(page_source)
    elif 'SC 2.4.4: Link Purpose (In Context) (Level A)' in criterion:
        result = link_purpose_context_violation_prompting(page_source)
    elif 'SC 2.4.5: Multiple Ways (Level AA)' in criterion:
        result = multiple_ways_violation_prompting(page_source)
    elif 'SC 2.4.6: Headings and Labels (Level AA)' in criterion:
        result = headers_labels_violation_prompting(page_source)
    elif 'SC 2.4.8: Location (Level AAA)' in criterion:
        result = location_violation_prompting(page_source)
    elif 'SC 2.4.9: Link Purpose (Link Only) (Level AAA)' in criterion:
        result = link_purpose_link_only_violation_prompting(page_source)
    elif 'SC 2.4.10: Section Headings (Level AAA)' in criterion:
        result = section_headings_violation_prompting(page_source)
    elif 'SC 2.5.5: Target Size (Enhanced) (Level AAA)' in criterion:
        result = target_size_enhanced_violation_prompting(page_source)
    elif 'SC 2.5.8: Target Size (Minimum) (Level AA)' in criterion:
        result = target_size_minimum_violation_prompting(page_source)
    elif 'SC 3.1.1: Language of Page (Level A)' in criterion:
        result = language_violation_prompting(page_source)
    elif 'SC 3.1.2: Language of Parts (Level AA)' in criterion:
        result = language_violation_prompting(page_source)
    elif 'SC 3.1.4: Abbreviations (Level AAA)' in criterion:
        result = abbreviation_violation_prompting(page_source)
    elif 'SC 3.2.2: On Input (Level A)' in criterion:
        result = on_input_violation_prompting(page_source)
    elif 'SC 3.2.5:Change on Request (Level AAA)' in criterion:
        result = change_on_request_violation_prompting(page_source)
    elif 'SC 3.3.1: Error Identification (Level A)' in criterion:
        result = error_identification_violation_prompting(page_source)
    elif 'SC 3.3.2: Labels or Instructions (Level A)' in criterion:
        result = label_instructions_violation_prompting(page_source)
    elif 'SC 3.3.3: Error Suggestion (Level AA)' in criterion:
        result = error_suggestion_violation_prompting(page_source)
    elif 'SC 4.1.2: Name, Role, Value (Level A)' in criterion:
        result = name_role_value_violation_prompting(page_source)
    else:
        result = None
    return result
