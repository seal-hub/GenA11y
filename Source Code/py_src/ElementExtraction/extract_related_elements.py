import ast
import html
import base64
import hashlib
import io
import os
import re
import time
from io import BytesIO
from urllib.parse import urlparse
import cv2
import imagehash
import numpy as np
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from consts import TEMP_FILE_FOLDER
from A11yDetector.llm_helper import detect_sensory_instructions


def wait_for_load(driver, timeout=30):
    """ Wait for the page to fully load, including dynamic content. """
    start_time = time.time()

    def is_page_loaded():
        return driver.execute_script("""
            return document.readyState === 'complete' && 
                   (typeof jQuery === 'undefined' || jQuery.active === 0) &&
                   (typeof angular === 'undefined' || !angular.element(document).injector() || !angular.element(document).injector().get('$http').pendingRequests.length) &&
                   (typeof Ext === 'undefined' || !Ext.Ajax.isLoading()) &&
                   (!window.performance.timing || window.performance.timing.loadEventEnd > 0);
        """)

    while True:
        if is_page_loaded():
            return time.time() - start_time
        if time.time() - start_time > timeout:
            raise Exception("Timed out waiting for page load.")
        time.sleep(0.5)


async def extract_elements_long_delay(url: str) -> dict:
    # delete all files in the temp folder
    delete_all_files_in_folder(TEMP_FILE_FOLDER)

    # Set up the WebDriver options
    options = Options()
    options.add_argument('--headless')

    # Set up the WebDriver
    driver = webdriver.Chrome(options=options)

    # Navigate to the page
    driver.get(url)

    wait_for_load(driver)

    meta_element_redirection = extract_meta_refresh(driver)
    screenshots = take_screenshots_and_compare(driver, duration=20)

    # Combine the results into a dictionary
    results = {
        'SC 2.2.1': [meta_element_redirection, screenshots]
    }
    driver.quit()
    return results


def extract_related_elements(url) -> dict:
    """ Main function to extract both the page title and visual elements. """

    # delete all files in the temp folder
    delete_all_files_in_folder(TEMP_FILE_FOLDER)

    # Set up the WebDriver options
    options = Options()
    options.add_argument('--headless')

    # Set up the WebDriver
    driver = webdriver.Chrome(options=options)

    # Navigate to the page
    driver.get(url)

    wait_for_load(driver)

    # Extract the page title and related plain text
    page_title_dict = extract_page_title(driver)

    # Extract visual elements
    visual_elements_dict = extract_related_visual_elements(driver)

    # Extract lang attribute
    lang_attr_dict = extract_lang_attr(driver)

    # Extract input elements
    input_elements_dict = extract_input_elements(driver)

    # Extract image URLs
    img_urls = extract_img_urls(driver)

    # Extract form elements
    form_elements = extract_form_elements(driver)

    # Extract elements with text and ARIA labels
    elements_with_text_and_aria = extract_label_in_name(driver)

    # Extract text resizing elements
    text_resizing_dict = extract_text_resizing(driver)

    # Extract reflow elements
    text_reflow_dict = extract_text_reflow(driver)

    # Extract autoplay audio elements
    audio_elements = find_autoplay_audio_elements(driver)

    # Check the orientation and take screenshots
    orientation_dict = check_orientation_and_transform(driver)

    # Extract multiple ways screenshots
    multiple_ways_screenshots = extract_multiple_ways(driver)

    # Extract links
    link_related_elements = extract_links(driver)

    # Extract contrast related elements
    contrast_related_elements, elements_with_background_image = extract_contrast_related_elements(driver)

    # Extract form and heading elements
    form_input_dict = extract_form_input_elements(driver)
    heading_elements = extract_headings_with_siblings(driver)

    # Extract headings under sections
    heading_under_section_elements = extract_headings_under_sections(driver)

    # Extract information and relation
    information_and_relation = extract_info_relation_elements(driver)

    # Extract linearized tables
    linearized_tables, white_space_list, element_rearranged_list = extract_and_linearize_tables(driver)

    # Extract icons and controls
    icons_and_controls = extract_all_controls(driver)

    # Extract names and roles
    names_and_roles = extract_name_role_elements(driver)

    # Extract location related element
    location_related_elements = extract_location_related_information(driver)

    # Extract moving and updating content
    moving_and_updating = capture_updating_moving_element(driver)

    # Extract bypassing element
    bypass_blocks = extract_specific_role_elements(driver)

    # Extract sensory elements
    sensory_elements = extract_sensory_elements(driver)

    # Extract link and form screenshots
    link_form_screenshots = extract_link_form_screenshot(driver)

    # Extract target size elements
    target_size_elements = extract_target_size(driver)

    # Extract blocks of text
    text_blocks = extract_text_blocks_with_details(driver)

    # Extract text spacing screenshots
    text_spacing_screenshots = extract_text_spacing_screenshots(driver)

    # Extract initial screenshots
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)

    # Clean up by closing the browser
    driver.quit()

    # Combine results
    results = {
        "SC 1.1.1": visual_elements_dict,
        "SC 1.3.1": information_and_relation,
        "SC 1.3.2": [linearized_tables, white_space_list, element_rearranged_list],
        "SC 1.3.3": sensory_elements,
        'SC 1.3.4': orientation_dict,
        "SC 1.3.5": input_elements_dict,
        "SC 1.3.6": icons_and_controls,
        "SC 1.4.1": link_form_screenshots,
        "SC 1.4.2": audio_elements,
        "SC 1.4.3": [contrast_related_elements, elements_with_background_image],
        "SC 1.4.4": text_resizing_dict,
        "SC 1.4.5": img_urls,
        "SC 1.4.8": text_blocks,
        "SC 1.4.10": text_reflow_dict,
        "SC 1.4.12": text_spacing_screenshots,
        "SC 2.2.2": moving_and_updating,
        "SC 2.4.1": bypass_blocks,
        "SC 2.4.2": page_title_dict,
        "SC 2.4.4": link_related_elements,
        "SC 2.4.5": multiple_ways_screenshots,
        "SC 2.4.6": [form_input_dict, heading_elements],
        "SC 2.4.8": location_related_elements,
        "SC 2.4.10": heading_under_section_elements,
        "SC 2.5.3": elements_with_text_and_aria,
        "SC 2.5.8": target_size_elements,
        "SC 3.1.1": lang_attr_dict,
        "SC 3.1.4": initial_screenshot_str,
        "SC 3.3.1": initial_screenshot_str,
        "SC 3.3.2": form_elements,
        "SC 3.3.3": initial_screenshot_str,
        "SC 4.1.2": names_and_roles
    }

    return results


def extract_page_title(driver: webdriver.Chrome) -> dict:
    """ Extract the page title as well as the related plain text from the HTML content."""

    # Extract the page source and process it
    title = driver.title
    if title is None:
        title = "<title></title>"
    plain_text = driver.find_element(By.TAG_NAME, 'body').text
    # Remove newline characters and make it one line
    plain_text = plain_text.replace('\n', ' ')
    length = len(plain_text)
    portion_length = int(length * 0.5)
    page_title_dict = {
        "title": title,
        "portion_text": plain_text[:portion_length]
    }
    return page_title_dict


def extract_url_from_style(style):
    if 'background-image:' in style:
        start = style.find('url(') + len('url(')
        end = style.find(')', start)
        url = style[start:end].strip('\'"')
        return url
    return None


def convert_to_absolute(base, relative):
    if not base.endswith('/'):
        base += '/'

    # If the relative URL starts with a '/', remove the leading '/' to treat it as a relative path
    if relative.startswith('/'):
        relative = relative.lstrip('/')

    # Append the relative URL to the base URL
    return base + relative


def extract_related_visual_elements(driver: webdriver.Chrome) -> dict:
    """Extract various visual elements from the HTML content."""

    # Helper function to clean up the HTML
    def clean_html(html_string):
        cleaned_html = html.unescape(html_string).replace('\\"', '"')
        # Remove extra whitespace
        return ' '.join(cleaned_html.split())

        # Helper function to convert relative URLs to absolute URLs

    def get_base_url(subfolder):
        if subfolder == "capitalone":
            return "https://www.capitalone.com/"
        elif subfolder == "openai":
            return "https://openai.com/"
        elif subfolder == "zoro.to":
            return "https://zoroxtv.to/"
        else:
            return f"https://www.{subfolder}/"  # Assuming the default base URL should end with .com

    def extract_last_part_of_base(base):
        parts = base.rstrip('/').split('/')
        return parts[-1]

    # Get the base URL from the current URL of the driver
    current_url = driver.current_url
    parsed_url = urlparse(current_url)

    # Check if the path ends with a slash; if not, assume it's a file and remove the file part
    if not current_url.endswith('/'):
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}/"
    else:
        base_url = current_url

    # Extract elements
    applet_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                       driver.find_elements(By.TAG_NAME, 'applet')]
    img_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in driver.find_elements(By.TAG_NAME, 'img')]
    svg_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in driver.find_elements(By.TAG_NAME, 'svg')]
    canvas_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                       driver.find_elements(By.TAG_NAME, 'canvas')]
    img_within_a_elements = [clean_html(img.find_element(By.XPATH, './..').get_attribute('outerHTML')) for img in
                             driver.find_elements(By.XPATH, '//a//img')]
    area_within_map_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                                driver.find_elements(By.XPATH, '//map//area')]
    graphics_role_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                              driver.find_elements(By.XPATH, '//*[@role="graphics"]')]
    img_role_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                         driver.find_elements(By.XPATH, '//*[@role="img"]')]
    input_image_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                            driver.find_elements(By.XPATH, '//input[@type="image"]')]
    map_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in driver.find_elements(By.TAG_NAME, 'map')]
    object_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                       driver.find_elements(By.TAG_NAME, 'object')]
    audio_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                      driver.find_elements(By.TAG_NAME, 'audio')]
    video_elements = [clean_html(elem.get_attribute('outerHTML')) for elem in
                      driver.find_elements(By.TAG_NAME, 'video')]
    background_image_elements = driver.execute_script('''
        return Array.from(document.querySelectorAll('*'))
            .filter(el => {
                let bgImage = window.getComputedStyle(el).backgroundImage;
                return bgImage !== 'none' && bgImage !== '';
            })
            .map(el => {
                let bgImage = window.getComputedStyle(el).backgroundImage;
                // Decode HTML entities in the backgroundImage style
                bgImage = bgImage.replace(/&quot;/g, '"');
                // Remove the url("...") wrapper from the decoded string
                bgImage = bgImage.replace(/url\\(["']?(.*?)["']?\\)/i, '$1');
                let clone = el.cloneNode(true); // Clone the element
                clone.style.backgroundImage = 'url("' + bgImage + '")'; // Re-apply the backgroundImage style
                while (clone.firstChild) {
                    clone.removeChild(clone.firstChild); // Remove all children from the clone
                }
                return clone.outerHTML; // Returns the outerHTML of the cleaned clone
            });
    ''')
    background_image_elements = [html.replace('&quot;', '') for html in background_image_elements]

    # Extract associated aria-label or aria-labelledby attributes for img role elements
    img_role_aria_labels = [
        (clean_html(elem.get_attribute('outerHTML')))
        for elem in driver.find_elements(By.XPATH, '//*[@role="img"]')
    ]

    img_str_elements = [str(img) for img in img_elements]

    # Return the extracted elements as a dictionary
    all_elements = {
        "applet_elements": set(applet_elements),
        "img_elements": set(img_str_elements),
        "svg_elements": set(svg_elements),
        "canvas_elements": set(canvas_elements),
        "img_within_a_elements": set(img_within_a_elements),
        "area_within_map_elements": set(area_within_map_elements),
        "graphics_role_elements": set(graphics_role_elements),
        "img_role_elements": set(img_role_elements),
        "img_role_aria_labels": set(img_role_aria_labels),
        "input_image_elements": set(input_image_elements),
        "map_elements": set(map_elements),
        "object_elements": set(object_elements),
        "audio_elements": set(audio_elements),
        "video_elements": set(video_elements),
        "background_image_elements": set(background_image_elements)
    }

    augmented_elements = {}
    for key, elements in all_elements.items():
        for element in elements:
            if 'src="' in element:
                start = element.find('src="') + len('src="')
                end = element.find('"', start)
                src = element[start:end]
                if not src.startswith(('http://', 'https://')):
                    src = convert_to_absolute(base_url, src)
                outer_html = element[:start - 5] + ' src="' + src + '"' + element[end + 1:]
                augmented_elements[outer_html] = src
            elif 'style="' in element:
                start = element.find('style="') + len('style="')
                end = element.find('"', start)
                style = element[start:end]
                background_image_url = extract_url_from_style(style)
                if background_image_url:
                    if not background_image_url.startswith(('http://', 'https://')):
                        background_image_url = convert_to_absolute(base_url, background_image_url)
                    outer_html = element[:start - 5] + ' style="' + style + '"' + element[end + 1:]
                    augmented_elements[outer_html] = background_image_url
    all_elements['img_urls'] = augmented_elements
    return all_elements


def extract_lang_attr(driver: webdriver.Chrome) -> dict:
    """ Extract the lang attribute from the HTML content. """
    lang_only_elements = []
    lang_and_xml_lang_elements = []

    # Extract the lang attribute of the <html> tag without its children
    html_tag = driver.find_element(By.TAG_NAME, 'html')
    html_tag_lang = html_tag.get_attribute('lang')
    html_tag_xml_lang = html_tag.get_attribute('xml:lang')
    if html_tag_lang and html_tag_xml_lang:
        lang_and_xml_lang_elements.append(f'<html lang="{html_tag_lang}" xml:lang="{html_tag_xml_lang}"></html>')
    elif html_tag_lang:
        lang_only_elements.append(f'<html lang="{html_tag_lang}"></html>')

    # Find all elements with the lang attribute
    elements_with_lang = driver.find_elements(By.XPATH, '//*[@lang and not(self::html)]')

    # Process elements to separate those with only lang and those with both lang and xml:lang
    for element in elements_with_lang:
        outer_html = element.get_attribute('outerHTML')
        if element.get_attribute('xml:lang'):
            lang_and_xml_lang_elements.append(outer_html)
        else:
            lang_only_elements.append(outer_html)

    # Combine the results into two strings separated by newlines
    lang_only_output = "; ".join(lang_only_elements)
    lang_and_xml_lang_output = "; ".join(lang_and_xml_lang_elements)

    return {"lang_only": lang_only_output,
            "lang_and_xml": lang_and_xml_lang_output}


def extract_img_urls(driver: webdriver.Chrome) -> set:
    current_url = driver.current_url
    parsed_url = urlparse(current_url)

    if not current_url.endswith('/'):
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}/"
    else:
        base_url = current_url

    # Collect image sources from <img> and <input type="image">
    image_sources = {img.get_attribute('src') for img in driver.find_elements(By.TAG_NAME, 'img')}
    image_sources.update(
        {input_img.get_attribute('src') for input_img in driver.find_elements(By.CSS_SELECTOR, 'input[type="image"]')})

    # Execute JavaScript to collect background images from computed styles
    background_image_urls = driver.execute_script('''
        return Array.from(document.querySelectorAll('*'))
            .map(el => window.getComputedStyle(el).backgroundImage)
            .filter(bgImg => bgImg !== 'none' && bgImg.startsWith('url'))
            .map(bgImg => bgImg.slice(5, -2).replace(/["']/g, ""));
    ''')
    image_sources.update(background_image_urls)

    absolute_image_sources = {
        convert_to_absolute(base_url, src) if src and not src.startswith(('http://', 'https://')) else src
        for src in image_sources if src}

    return absolute_image_sources


def extract_input_elements(driver: webdriver.Chrome) -> dict:
    """ Extract input elements from the HTML content. """

    # Find all label elements that have a 'for' attribute
    labels = driver.find_elements(By.XPATH, "//label[@for]")

    # Initialize a dictionary to hold label-input pairs
    label_input_pairs = {}

    # Loop through each label and find the corresponding input by its id
    for label in labels:
        try:
            input_id = label.get_attribute('for')
            input_element = driver.find_element(By.ID, input_id)
            label_text = label.text
            input_html = input_element.get_attribute('outerHTML')

            # Store the label text and the entire HTML of the input in the dictionary
            label_input_pairs[label_text] = input_html
        except:
            continue
    return label_input_pairs


def get_label_html_with_inline_styles(label):
    """
    Retrieves a label's HTML with relevant CSS properties applied as inline styles.
    """
    css_properties = ['display', 'visibility', 'opacity', 'position', 'left', 'top', 'right', 'bottom', 'z-index']
    style_str = "; ".join(f"{prop}: {label.value_of_css_property(prop)}" for prop in css_properties)

    # Include the 'for' attribute if it exists
    for_attribute = label.get_attribute('for')
    if for_attribute:
        for_attribute_str = f' for="{for_attribute}"'
    else:
        for_attribute_str = ''

    return f'<label style="{style_str}"{for_attribute_str}>{label.get_attribute("innerHTML")}</label>'


def extract_form_elements(driver: webdriver.Chrome) -> list:
    # Define the selectors for potential root containers
    container_selectors = [
        "form",
        "div[role='form']",
        "div[role='radiogroup']",
        "div[role='group']",
        "fieldset",
        "section:has(input, textarea, select)",
        "article:has(input, textarea, select)"
    ]

    all_containers = []
    all_containers_html = []

    # Iterate over selectors to find all containers
    for selector in container_selectors:
        containers = driver.find_elements(By.CSS_SELECTOR, selector)
        for container in containers:
            # Modify the labels within each container
            labels = container.find_elements(By.TAG_NAME, 'label')
            container_html = container.get_attribute('outerHTML')
            for label in labels:
                if label.get_attribute('for'):  # Check if label has 'for' attribute
                    # Update label with inline styles for visibility
                    new_label_html = get_label_html_with_inline_styles(label)
                    # Replace old label HTML with new HTML in the container's HTML
                    old_label_html = label.get_attribute('outerHTML')
                    container_html = container_html.replace(old_label_html, new_label_html)

            # Add container HTML to all_containers list
            all_containers.append(container)
            all_containers_html.append(container_html)

    # Filter out nested containers by checking containment in outerHTML
    root_containers_html = []
    for i, html in enumerate(all_containers_html):
        is_root = True
        for j, other_html in enumerate(all_containers_html):
            if i != j and other_html.find(html) != -1:
                is_root = False
                break
        if is_root:
            root_containers_html.append(html)

    return root_containers_html


def extract_label_in_name(driver: webdriver.Chrome) -> set:
    # Specific HTML elements and ARIA roles with tag mapping
    html_elements = {
        'button': ['button', 'input[type="button"]', 'input[type="submit"]', 'input[type="reset"]'],
        'checkbox': ['input[type="checkbox"]'],
        'radio': ['input[type="radio"]'],
        'link': ['a[href]'],
        'option': ['option'],
        'searchbox': ['input[type="search"]']
    }

    aria_roles = [
        'button', 'checkbox', 'gridcell', 'link', 'menuitem',
        'menuitemcheckbox', 'menuitemradio', 'option', 'radio',
        'searchbox', 'switch', 'tab', 'treeitem'
    ]

    def process_elements(elements, unique_elements_html):
        for element in elements:
            if meets_criteria(element):
                # Check if aria-labelledby needs to be converted to aria-label
                aria_labelledby = element.get_attribute('aria-labelledby')
                if aria_labelledby:
                    # Replace aria-labelledby with aria-label
                    labelled_element = driver.find_element(By.ID, aria_labelledby)
                    if labelled_element:
                        text_content = labelled_element.text.strip()
                        driver.execute_script("arguments[0].setAttribute('aria-label', arguments[1])", element,
                                              text_content)
                        driver.execute_script("arguments[0].removeAttribute('aria-labelledby')", element)

                # Add to set if not already included based on its outerHTML
                unique_elements_html.add(element.get_attribute('outerHTML'))

    # Set to store unique outerHTML
    unique_elements_html = set()

    # Extract elements by HTML tag
    for element_type, selectors in html_elements.items():
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                process_elements(elements, unique_elements_html)
            except Exception as e:
                pass

    # Extract elements by ARIA role
    for role in aria_roles:
        try:
            elements = driver.find_elements(By.XPATH, f"//*[@role='{role}']")
            process_elements(elements, unique_elements_html)
        except Exception as e:
            pass

    return unique_elements_html


def meets_criteria(element):
    """Check if the element has visible text and either an aria-label or aria-labelledby attribute."""
    text = element.text.strip()
    value = element.get_attribute('value')

    return bool(text) or bool(value)


def is_vertical_scrolling_needed(driver):
    # Get the total height of the document
    scroll_height = driver.execute_script("return document.documentElement.scrollHeight")
    # Get the height of the visible part of the document
    client_height = driver.execute_script("return document.documentElement.clientHeight")

    # Check if any element on the page is fixed and its height
    fixed_elements_height = driver.execute_script("""
        let fixedElements = Array.from(document.querySelectorAll('*')).filter(
            el => getComputedStyle(el).position === 'fixed'
        );
        let fixedHeight = fixedElements.reduce((acc, el) => acc + el.offsetHeight, 0);
        return fixedHeight;
    """)

    # If there are fixed elements, subtract their height from the client height
    effective_client_height = client_height - fixed_elements_height

    return scroll_height > effective_client_height


# Function to take screenshots while scrolling to the bottom
def take_screenshots_while_scrolling(driver, prefix):
    screenshots = []
    total_height = driver.execute_script("return document.documentElement.scrollHeight")
    view_height = driver.execute_script("return window.innerHeight")
    scroll_position = 0

    if "after" or 'before' in prefix:
        if 'after' in prefix:
            threshold_length = 10
        else:
            threshold_length = 5
        while scroll_position < total_height or len(screenshots) < threshold_length:
            screenshot_name = os.path.join(TEMP_FILE_FOLDER, f"{prefix}_{len(screenshots)}.png")
            driver.save_screenshot(screenshot_name)
            screenshots.append(screenshot_name)

            scroll_position += view_height
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            time.sleep(2)  # Wait for scrolling to complete

            current_scroll_position = driver.execute_script("return window.pageYOffset")
            if current_scroll_position + view_height >= total_height:
                # Take a final screenshot at the very bottom
                screenshot_name = os.path.join(TEMP_FILE_FOLDER, f"{prefix}_{len(screenshots)}.png")
                driver.save_screenshot(screenshot_name)
                screenshots.append(screenshot_name)
                break

            # Break the loop if the limit of 30 screenshots is reached
            if len(screenshots) >= 10:
                break
    else:
        while scroll_position < total_height:
            screenshot_name = os.path.join(TEMP_FILE_FOLDER, f"{prefix}_{len(screenshots)}.png")
            driver.save_screenshot(screenshot_name)
            screenshots.append(screenshot_name)

            scroll_position += view_height
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            time.sleep(2)  # Wait for scrolling to complete

            current_scroll_position = driver.execute_script("return window.pageYOffset")
            if current_scroll_position + view_height >= total_height:
                # Take a final screenshot at the very bottom
                screenshot_name = os.path.join(TEMP_FILE_FOLDER, f"{prefix}_{len(screenshots)}.png")
                driver.save_screenshot(screenshot_name)
                screenshots.append(screenshot_name)
                break

    return screenshots


# Function to stitch screenshots together vertically
def stitch_screenshots(screenshots, output_filename):
    # Open all the images
    images = [Image.open(screenshot) for screenshot in screenshots]

    # Assuming all images have the same size
    width, height = images[0].size

    # Calculate the total height of the stitched image
    total_height = height * len(images)

    # Create a new blank image with the calculated dimensions
    stitched_image = Image.new('RGB', (width, total_height))

    # Initialize the vertical offset
    y_offset = 0

    # Paste each image into the new blank image at the appropriate position
    for image in images:
        stitched_image.paste(image, (0, y_offset))
        y_offset += height

    # Save the stitched image to the specified output file
    stitched_image.save(output_filename)


def extract_original_screenshot(driver: webdriver.Chrome) -> list:
    screenshot_list = []
    # Check if vertical scrolling is needed before zooming
    before_scroll_needed = is_vertical_scrolling_needed(driver)
    if before_scroll_needed:
        before_screenshots = take_screenshots_while_scrolling(driver, 'before')
        stitch_screenshots(before_screenshots, os.path.join(TEMP_FILE_FOLDER, 'screenshot_original.png'))
    else:
        driver.save_screenshot(os.path.join(TEMP_FILE_FOLDER, 'screenshot_original.png'))
    files_with_before = []

    # Walk through all files and directories within the specified directory
    for root, dirs, files in os.walk(TEMP_FILE_FOLDER):
        for file in files:
            if "before" in file:
                files_with_before.append(os.path.join(root, file))
    for file in files_with_before:
        screenshot_list.append(encode_image(file))
    return screenshot_list


def extract_zoomed_screenshot(driver: webdriver.Chrome) -> list:
    screenshot_list = []
    set_browser_scale(200, driver)
    time.sleep(1)  # Wait for the zoom effect to apply
    files_with_after = []

    after_scroll_needed = is_vertical_scrolling_needed(driver)
    if after_scroll_needed:
        after_screenshots = take_screenshots_while_scrolling(driver, 'after')
        stitch_screenshots(after_screenshots, os.path.join(TEMP_FILE_FOLDER, 'screenshot_zoomed.png'))
    else:
        driver.save_screenshot(os.path.join(TEMP_FILE_FOLDER, 'screenshot_zoomed.png'))
    for root, dirs, files in os.walk(TEMP_FILE_FOLDER):
        for file in files:
            if "after" in file:
                files_with_after.append(os.path.join(root, file))
    for file in files_with_after:
        screenshot_list.append(encode_image(file))
    return screenshot_list


def extract_text_resizing(driver: webdriver.Chrome) -> dict:
    """ Extract the text resizing elements from the HTML content. """
    # Find all meta elements with a name attribute of "viewport"
    meta_elements = driver.find_elements(By.XPATH, '//meta[@name="viewport"]')
    text_resizing_dict = {}
    # Store the original size
    original_size = driver.get_window_size()

    # Iterate through found elements to check the content attribute
    for meta in meta_elements:
        content_value = meta.get_attribute('content')
        if 'user-scalable' in content_value or 'maximum-scale' in content_value:
            meta.get_attribute('outerHTML')  # Return the element's HTML if it matches the criteria
            text_resizing_dict['meta'] = meta.get_attribute('outerHTML')
            break
    driver.set_window_size(2560, 1440)

    input_elements = driver.find_elements(By.TAG_NAME, 'input')
    input_lists = []

    for input_element in input_elements:
        # Check inline style
        style_attribute = input_element.get_attribute("style")
        if 'font-size' in style_attribute:
            inline_font_size = style_attribute.split('font-size:')[1].split(';')[0].strip()
        else:
            inline_font_size = None

        # Check stylesheets if inline style is not found
        original_font_size = None
        if not inline_font_size:
            stylesheets = driver.execute_script("""
                let sheets = document.styleSheets;
                let rules = [];
                for (let i = 0; i < sheets.length; i++) {
                    try {
                        if (sheets[i].cssRules) {
                            for (let j = 0; j < sheets[i].cssRules.length; j++) {
                                rules.push(sheets[i].cssRules[j].cssText);
                            }
                        }
                    } catch (e) {
                        // Ignore errors from cross-origin stylesheets
                    }
                }
                return rules;
            """)

            element_class = input_element.get_attribute("class").split()
            element_id = input_element.get_attribute("id")
            element_name = input_element.get_attribute("name")

            for rule in stylesheets:
                if element_id and f"#{element_id}" in rule:
                    if 'font-size' in rule:
                        original_font_size = rule.split('font-size:')[1].split(';')[0].strip()
                        break
                for cls in element_class:
                    if f".{cls}" in rule:
                        if 'font-size' in rule:
                            original_font_size = rule.split('font-size:')[1].split(';')[0].strip()
                            break
                if element_name and f"[name='{element_name}']" in rule:
                    if 'font-size' in rule:
                        original_font_size = rule.split('font-size:')[1].split(';')[0].strip()
                        break
        else:
            original_font_size = inline_font_size

        input_lists.append({input_element.get_attribute('outerHTML'): original_font_size})
    # extract_original_screenshot(driver)
    extract_zoomed_screenshot(driver)
    text_resizing_dict['original'] = encode_image(TEMP_FILE_FOLDER + '/screenshot_original.png')
    text_resizing_dict['zoomed'] = encode_image(TEMP_FILE_FOLDER + '/screenshot_zoomed.png')
    text_resizing_dict['input_elements'] = input_lists
    # Execute JavaScript to reset text size back to original
    driver.set_window_size(original_size['width'], original_size['height'])
    return text_resizing_dict


def extract_text_reflow(driver) -> dict:
    text_reflow_dict = {}
    # Store the original size
    original_size = driver.get_window_size()
    # Set window size to 1280x1024 CSS pixels
    driver.set_window_size(1280, 1024)

    # Zoom to 400%
    set_browser_scale(400, driver)

    # Check if vertical scrolling is needed after zooming
    after_scroll_needed = is_vertical_scrolling_needed(driver)
    if after_scroll_needed:
        after_screenshots = take_screenshots_while_scrolling(driver, 'after_zoom')
        stitch_screenshots(after_screenshots, os.path.join(TEMP_FILE_FOLDER, 'screenshot_reflow.png'))
    else:
        driver.save_screenshot(os.path.join(TEMP_FILE_FOLDER, 'screenshot_reflow.png'))
    text_reflow_dict['original'] = encode_image(TEMP_FILE_FOLDER + '/screenshot_original.png')
    text_reflow_dict['reflow'] = encode_image(TEMP_FILE_FOLDER + '/screenshot_reflow.png')
    driver.set_window_size(original_size['width'], original_size['height'])
    set_browser_scale(100, driver)
    return text_reflow_dict


def set_browser_scale(level: int, driver: webdriver.Chrome):
    # JavaScript to scale the entire document body
    driver.execute_script(f"document.body.style.zoom='{level}%'")


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Function to find and handle various scenarios of autoplay audio elements
def find_autoplay_audio_elements(driver: webdriver.Chrome) -> dict:
    # Find all audio elements
    audio_elements = driver.find_elements(By.XPATH, "//audio | //video")

    audio_dict = {"short": {}, "long": {}}

    # Iterate over each audio element to check for autoplay scenarios
    for index, audio in enumerate(audio_elements):
        # Check for autoplay attribute
        if audio.get_attribute("autoplay") and not audio.get_attribute("muted"):
            handle_autoplay_audio(driver, audio, index, audio_dict)
        else:
            # Check for other potential autoplay scenarios
            if is_autoplay_by_js(driver, audio) and not audio.get_attribute("muted"):
                handle_autoplay_audio(driver, audio, index, audio_dict)

    return audio_dict


# Function to handle autoplay audio element
def handle_autoplay_audio(driver, audio_element, index, audio_dict):
    # Scroll to the audio element
    driver.execute_script("arguments[0].scrollIntoView(true);", audio_element)
    time.sleep(1)  # Optional: Wait for scrolling to stabilize

    # Take screenshot
    screenshot_path = TEMP_FILE_FOLDER + f"/autoplay_audio_{index + 1}.png"
    driver.save_screenshot(screenshot_path)
    html_tag = extract_tag_with_attributes_only(audio_element)
    html_tag = html_tag.replace('\n', '').replace('\t', '')
    image_encoded = encode_image(screenshot_path)

    # Check the duration of the audio file and categorize accordingly
    duration = check_audio_file_duration(driver, audio_element)
    played_less_than_3_seconds = has_played_for_more_than(driver, audio_element, 3)
    if duration <= 3 or not played_less_than_3_seconds:
        audio_dict["short"][html_tag] = image_encoded
    elif duration > 3 or played_less_than_3_seconds:
        audio_dict["long"][html_tag] = image_encoded


# Function to check if audio element is autoplay by JavaScript events
def is_autoplay_by_js(driver, audio_element):
    # Check for common JavaScript events that might trigger autoplay
    try:
        # Check if onload event triggers audio playback
        onload_event = driver.execute_script("return arguments[0].onload;", audio_element)
        if onload_event:
            return True

        # Check for setTimeout or setInterval that might start audio playback
        set_timeout_event = driver.execute_script("return arguments[0].setTimeout;", audio_element)
        if set_timeout_event:
            return True

        set_interval_event = driver.execute_script("return arguments[0].setInterval;", audio_element)
        if set_interval_event:
            return True

        return False
    except Exception as e:
        print(f"Error checking JavaScript autoplay: {e}")
        return False


def check_audio_file_duration(driver, audio_element):
    # Check the duration of the audio file
    audio_duration = driver.execute_script("return arguments[0].duration;", audio_element)
    return audio_duration


def is_audio_paused(driver, audio_element):
    """
    Check whether an audio element is paused or not.
    """
    return driver.execute_script("return arguments[0].paused;", audio_element)


def has_played_for_more_than(driver, media_element, seconds):
    """
    Check whether a media element (audio or video) has played for more than a specified number of seconds.
    """
    initial_time = driver.execute_script("return arguments[0].currentTime;", media_element)
    start_time = time.time()

    while time.time() - start_time < seconds:
        time.sleep(0.5)  # Check every 0.5 seconds
        current_time = driver.execute_script("return arguments[0].currentTime;", media_element)

        if current_time - initial_time >= seconds:
            return True

    return False


def extract_meta_refresh(driver: webdriver.Chrome) -> list:
    """ Extract the meta refresh elements from the HTML content. """

    # Locate the meta elements by their http-equiv attribute
    meta_refresh_elements = driver.find_elements(By.XPATH, '//meta[@http-equiv="refresh"]')
    meta_refresh_list = []

    for meta in meta_refresh_elements:
        outer_html = meta.get_attribute('outerHTML')
        if outer_html:
            meta_refresh_list.append(outer_html)
    if len(meta_refresh_list) == 0:
        # Use JavaScript to get the meta elements
        meta_refresh_list = driver.execute_script(
            "return Array.from(document.getElementsByTagName('meta')).filter(meta => meta.httpEquiv === "
            "'refresh').map(meta => meta.outerHTML);"
        )

    return meta_refresh_list


def take_screenshots_and_compare(driver: webdriver.Chrome, duration=300, interval=5, similarity_threshold=90) -> list:
    """
    Takes screenshots of a webpage every 5 seconds for a specified duration,
    and stops if the similarity between consecutive screenshots is less than the specified threshold.
    Deletes images if similarity is above the threshold.
    """

    previous_filename = None
    index = 1
    img_lists = []
    try:
        # Open the webpage

        end_time = time.time() + duration
        while time.time() < end_time:
            # Generate a filename with the current index
            filename = TEMP_FILE_FOLDER + f'/compare_screenshot_{index}.png'

            # Take a screenshot and save it
            driver.save_screenshot(filename)

            if previous_filename:
                # Calculate similarity between the current and previous screenshot
                similarity = calculate_similarity(previous_filename, filename)

                # If similarity is above the threshold, delete the two images
                if similarity < similarity_threshold:
                    # Stop taking screenshots if similarity is less than the threshold
                    img_lists.append(encode_image(previous_filename))
                    img_lists.append(encode_image(filename))
                    break

            previous_filename = filename
            index += 1

            # Wait for the specified interval
            time.sleep(interval)
        return img_lists

    except Exception as e:
        print(f"An error occurred: {e}")


def calculate_similarity(image1_path, image2_path):
    """
    Calculates the similarity between two images using imagehash.
    """
    hash1 = imagehash.average_hash(Image.open(image1_path))
    hash2 = imagehash.average_hash(Image.open(image2_path))
    difference = hash1 - hash2
    max_hash_value = len(hash1.hash) ** 2
    similarity = (1 - (difference / max_hash_value)) * 100
    return similarity


def delete_all_files_in_folder(folder_path):
    """
    Deletes all files in the specified folder.
    """
    try:
        # List all files in the folder
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

        # Delete each file
        for file in files:
            file_path = os.path.join(folder_path, file)
            os.remove(file_path)

        print(f'All files in {folder_path} have been deleted.')

    except Exception as e:
        print(f"An error occurred: {e}")


def take_screenshot(driver, orientation, filename):
    """
    Takes a screenshot of the current view.
    """
    time.sleep(5)
    # Set the window size based on the orientation
    if orientation == 'portrait':
        driver.set_window_size(768, 1024)
    else:  # landscape
        driver.set_window_size(1024, 768)

    time.sleep(1)  # wait for the page to adjust to the new size
    driver.save_screenshot(filename)


def check_orientation_and_transform(driver: webdriver.Chrome) -> dict:
    """
    Extracts elements using CSS transform property and takes screenshots in portrait and landscape views.
    """
    orientation_dict = {}
    try:

        # Take screenshots in portrait and landscape views
        portrait_filename = TEMP_FILE_FOLDER + '/screenshot_portrait.png'
        landscape_filename = TEMP_FILE_FOLDER + '/screenshot_landscape.png'
        take_screenshot(driver, 'portrait', portrait_filename)
        take_screenshot(driver, 'landscape', landscape_filename)
        orientation_dict['portrait'] = encode_image(portrait_filename)
        orientation_dict['landscape'] = encode_image(landscape_filename)
        return orientation_dict

    except Exception as e:
        print(f"An error occurred: {e}")


def extract_multiple_ways(driver: webdriver.Chrome) -> dict:
    """
        Takes two screenshots of a webpage: one when the page first loads and one after scrolling to the bottom.
    """
    # Take the initial screenshot
    initial_screenshot_path = TEMP_FILE_FOLDER + '/initial.png'
    driver.save_screenshot(initial_screenshot_path)

    # Scroll to the bottom of the page
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    # Take the bottom screenshot
    bottom_screenshot_path = TEMP_FILE_FOLDER + '/bottom.png'
    driver.save_screenshot(bottom_screenshot_path)
    return {
        'initial': encode_image(initial_screenshot_path),
        'bottom': encode_image(bottom_screenshot_path)
    }


def get_outer_html_without_children(element):
    tag_name = element.tag_name
    attributes = element.get_property('attributes')
    attr_string = ' '.join([f'{attr["name"]}="{attr["value"]}"' for attr in attributes])
    start_tag = f'<{tag_name} {attr_string}>'
    end_tag = f'</{tag_name}>'
    text_content = element.text or ''
    return f'{start_tag}{text_content}{end_tag}'


def extract_links(driver: webdriver.Chrome) -> list:
    # Find all link elements and elements with role="link" on the page
    link_elements = driver.find_elements(By.XPATH, '//a | //*[@role="link"]')

    # Extract and modify the desired elements
    combined_elements = []
    for link in link_elements:
        # Replace aria-labelledby with aria-label if present
        if link.get_attribute('aria-labelledby'):
            aria_labelledby = link.get_attribute('aria-labelledby')
            referenced_elements = [driver.find_element(By.ID, ref_id) for ref_id in aria_labelledby.split()]
            aria_label_text = ' '.join([elem.text for elem in referenced_elements])
            driver.execute_script(f"arguments[0].setAttribute('aria-label', '{aria_label_text}');", link)
            driver.execute_script("arguments[0].removeAttribute('aria-labelledby');", link)

        # Check if the link is nested within a table or list
        ancestor = None
        try:
            ancestor = link.find_element(By.XPATH, './ancestor::table | ./ancestor::ul | ./ancestor::ol')
        except:
            pass

        if ancestor:
            combined_html = ancestor.get_attribute('outerHTML')
        else:
            combined_html = ''
            parent = link.find_element(By.XPATH, './..')
            if parent.tag_name.lower() == 'body':
                parent_html = ''
            elif parent.tag_name.lower() == 'a':
                parent_html = parent.get_attribute('outerHTML')
            else:
                parent_html = get_outer_html_without_children(parent)

                # Determine previous sibling's outerHTML or minimal HTML
                prev_sibling = driver.execute_script("return arguments[0].previousElementSibling;", link)
                if prev_sibling and prev_sibling.tag_name.lower() == 'a':
                    prev_sibling_html = prev_sibling.get_attribute('outerHTML')
                else:
                    prev_sibling_html = get_outer_html_without_children(prev_sibling) if prev_sibling else ''

                # Determine next sibling's outerHTML or minimal HTML
                next_sibling = driver.execute_script("return arguments[0].nextElementSibling;", link)
                if next_sibling and next_sibling.tag_name.lower() == 'a':
                    next_sibling_html = next_sibling.get_attribute('outerHTML')
                else:
                    next_sibling_html = get_outer_html_without_children(next_sibling) if next_sibling else ''

                link_html = link.get_attribute('outerHTML')

                # Construct the combined HTML with the child nested inside the parent and two siblings
                if parent_html == "":
                    combined_html = f"{prev_sibling_html}{link_html}{next_sibling_html}"
                else:
                    combined_html = f"{parent_html}{prev_sibling_html}{link_html}{next_sibling_html}</{parent.tag_name}>"

            combined_html = combined_html.replace('\n', '').replace('\t', '')
            combined_elements.append(combined_html.strip())

    return combined_elements


def get_computed_style(driver, element, style_property):
    return driver.execute_script(f"return window.getComputedStyle(arguments[0]).getPropertyValue('{style_property}');",
                                 element)


def is_rgba(color):
    return re.match(r'rgba?\(\d+,\s*\d+,\s*\d+(,\s*\d+(\.\d+)?)?\)', color) is not None


def convert_to_rgba(driver, color):
    js_code = """
    function convertColor(color) {
        var fakeDiv = document.createElement('div');
        fakeDiv.style.color = color;
        document.body.appendChild(fakeDiv);
        var computedColor = window.getComputedStyle(fakeDiv).color;
        document.body.removeChild(fakeDiv);

        // Convert RGB to RGBA if necessary
        if (computedColor.startsWith('rgb(')) {
            return computedColor.replace('rgb(', 'rgba(').replace(')', ', 1)');
        }
        return computedColor;
    }
    return convertColor(arguments[0]);
    """
    return driver.execute_script(js_code, color)


def extract_contrast_related_elements(driver: webdriver.Chrome):
    # Extract all elements

    elements = driver.find_elements(By.XPATH, "//*")

    related_elements = []
    elements_with_images = []
    elements_with_background_image = {}

    for elem in elements:
        background_color = get_computed_style(driver, elem, 'background-color')
        text_color = get_computed_style(driver, elem, 'color')
        font_size = get_computed_style(driver, elem, 'font-size')
        font_weight = get_computed_style(driver, elem, 'font-weight')
        background_image = get_computed_style(driver, elem, 'background-image')
        text_content = elem.text.strip()
        # Get CSS-generated content using JavaScript
        before_content = driver.execute_script(
            "return window.getComputedStyle(arguments[0], '::before').getPropertyValue('content');", elem)
        after_content = driver.execute_script(
            "return window.getComputedStyle(arguments[0], '::after').getPropertyValue('content');", elem)

        # Clean up the content if necessary (remove surrounding quotes)
        before_content = before_content.strip('"') if before_content else ''
        after_content = after_content.strip('"') if after_content else ''

        # Combine the contents if needed
        full_text_content = f"{before_content}{text_content}{after_content}"

        # Convert colors to RGBA if they are not already
        if background_color and not is_rgba(background_color):
            background_color = convert_to_rgba(driver, background_color)
        if text_color and not is_rgba(text_color):
            text_color = convert_to_rgba(driver, text_color)

        # Check if text is bold
        if font_weight in ['bold', '700']:
            font_weight = 'bold'
        else:
            font_weight = None

        # Build inline style
        # Get existing style
        existing_style = elem.get_attribute('style') or ""

        # Build new inline style
        style = existing_style
        if text_color and text_color != "rgb(0, 0, 0)":
            style += f"color: {text_color};"
        if font_size:
            style += f" font-size: {font_size};"
        if background_color and background_color != "rgba(0, 0, 0, 0)":
            style += f" background-color: {background_color};"
        if font_weight:
            style += f" font-weight: {font_weight};"

        outer_html = elem.get_attribute('outerHTML')
        if '<body' not in outer_html and '<head' not in outer_html:
            if background_image != 'none' and full_text_content:
                style = f"background-image: {background_image};"
                if text_color:
                    style += f" color: {text_color};"
                if font_size:
                    style += f" font-size: {font_size};"
                if font_weight:
                    style += f" font-weight: {font_weight};"
                driver.execute_script(f"arguments[0].setAttribute('style', '{style}')", elem)
                elements_with_images.append(elem)
            elif full_text_content and (background_color != "rgba(0, 0, 0, 0)" or text_color != "rgb(0, 0, 0)"):
                driver.execute_script(f"arguments[0].setAttribute('style', '{style}')", elem)
                # Convert the element to a BeautifulSoup object
                soup = BeautifulSoup(elem.get_attribute('outerHTML'), 'html.parser')
                # Remove the children by clearing the contents
                tag = soup.find()
                if tag:
                    tag.clear()

                # Append the modified HTML to related_elements
                new_html = str(soup)
                related_elements.append(new_html)

    # Take screenshots of elements with background images
    for elem in elements_with_images:
        try:
            # Scroll element into view
            driver.execute_script("arguments[0].scrollIntoView();", elem)
            location = elem.location
            size = elem.size
            screenshot_path = TEMP_FILE_FOLDER + f"/background_{location['x']}_{location['y']}.png"
            driver.save_screenshot(screenshot_path)

            # Crop the element from the screenshot
            image = Image.open(screenshot_path)
            left = location['x']
            top = location['y']
            right = location['x'] + size['width']
            bottom = location['y'] + size['height']
            cropped_image = image.crop((left, top, right, bottom))

            # Override the screenshot with the cropped image
            cropped_image.save(screenshot_path)

            # Encode the cropped image to base64
            buffered = BytesIO()
            cropped_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Store the HTML tag and encoded image
            elements_with_background_image[elem.get_attribute('outerHTML')] = img_str
        except:
            continue

    return related_elements, elements_with_background_image


def extract_form_input_elements(driver: webdriver.Chrome) -> dict:
    # Define the selectors for potential root containers
    container_selectors = [
        "form",
        "div[role='form']",
        "div[role='radiogroup']",
        "div[role='group']",
        "fieldset",
        "section:has(input, textarea, select)",
        "article:has(input, textarea, select)"
    ]

    all_containers = []
    all_containers_html = []

    # Iterate over selectors to find all containers
    for selector in container_selectors:
        containers = driver.find_elements(By.CSS_SELECTOR, selector)
        for container in containers:
            # Modify the labels within each container
            labels = container.find_elements(By.TAG_NAME, 'label')
            container_html = container.get_attribute('outerHTML')
            for label in labels:
                if label.get_attribute('for'):  # Check if label has 'for' attribute
                    # Update label with inline styles for visibility
                    new_label_html = get_label_html_with_inline_styles(label)
                    # Replace old label HTML with new HTML in the container's HTML
                    old_label_html = label.get_attribute('outerHTML')
                    container_html = container_html.replace(old_label_html, new_label_html)

            # Add container HTML to all_containers list
            all_containers.append(container)
            all_containers_html.append(container_html)

    # Filter out nested containers by checking containment in outerHTML
    root_containers_html = []
    for i, html in enumerate(all_containers_html):
        is_root = True
        for j, other_html in enumerate(all_containers_html):
            if i != j and other_html.find(html) != -1:
                is_root = False
                break
        if is_root:
            root_containers_html.append(html)

    # Extract all input elements with their labels outside the root containers
    inputs_with_labels = []
    all_inputs = driver.find_elements(By.TAG_NAME, 'input')
    all_text_areas = driver.find_elements(By.TAG_NAME, 'textarea')
    all_selects = driver.find_elements(By.TAG_NAME, 'select')

    for input_element in all_inputs + all_text_areas + all_selects:
        element_html = input_element.get_attribute('outerHTML')
        element_in_root_container = False
        for root_html in root_containers_html:
            if root_html.find(element_html) != -1:
                element_in_root_container = True
                break
        if not element_in_root_container:
            # Find associated label
            label = None
            if input_element.get_attribute('id'):
                labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_element.get_attribute('id')}']")
                if labels:
                    label = labels[0]
            if label:
                # Format input nested within label
                input_nested_label_html = f"<label>{label.text}:{element_html}</label>"
                inputs_with_labels.append(input_nested_label_html)

    return {"forms": root_containers_html, "inputs": inputs_with_labels}


def extract_headings_with_siblings(driver: webdriver.Chrome) -> list:
    # Define the selectors for heading elements including those with role "heading"
    heading_selectors = [
        "h1", "h2", "h3", "h4", "h5", "h6",
        "[role='heading']"
    ]

    headings_with_siblings = []

    # Iterate over selectors to find all heading elements
    for selector in heading_selectors:
        headings = driver.find_elements(By.CSS_SELECTOR, selector)
        for heading in headings:
            heading_html = heading.get_attribute('outerHTML')
            siblings_html = []

            # Get the next two siblings
            sibling = heading
            for _ in range(2):
                try:
                    sibling = sibling.find_element(By.XPATH, 'following-sibling::*[1]')
                    siblings_html.append(sibling.get_attribute('outerHTML'))
                except NoSuchElementException:
                    break

            # Format the output as a single string
            formatted_output = heading_html + ' ' + ' '.join(siblings_html)
            headings_with_siblings.append(formatted_output)

    return headings_with_siblings


def extract_headings_under_sections(driver: webdriver.Chrome) -> list:
    sections_data = []

    # Find all section elements
    sections = driver.find_elements(By.TAG_NAME, 'section')

    for section in sections:
        # Extract the section HTML without children
        section_html = section.get_attribute('outerHTML').split('>')[0] + '>'
        section_data = {
            'html': section_html,
            'no_heading': True  # Assume no heading by default
        }

        # Define the selectors for heading elements including those with role "heading"
        heading_selectors = [
            "h1", "h2", "h3", "h4", "h5", "h6",
            "[role='heading']"
        ]

        headings_html_list = []

        # Check for headings within the section
        for selector in heading_selectors:
            headings = section.find_elements(By.CSS_SELECTOR, selector)
            for heading in headings:
                heading_html = heading.get_attribute('outerHTML')
                siblings_html = []

                # Get the next two siblings
                sibling = heading
                for _ in range(2):
                    try:
                        sibling = sibling.find_element(By.XPATH, 'following-sibling::*[1]')
                        if sibling:
                            siblings_html.append(sibling.get_attribute('outerHTML'))
                        else:
                            break
                    except:
                        break

                # Format the output as a single string
                formatted_output = heading_html + ' ' + ' '.join(siblings_html)
                headings_html_list.append(formatted_output)

        if headings_html_list:
            section_data['no_heading'] = False
            section_data['headings'] = ' '.join(headings_html_list)

        sections_data.append(section_data)

    return sections_data


def has_whitespace_formatting(text):
    lines = text.splitlines()
    if len(lines) < 2:
        return False

    # Check for a pattern of columns
    for line in lines:
        # Split the line by whitespace and check if there are multiple segments
        segments = re.split(r'\s{2,}', line)  # Split by two or more whitespace characters
        if len(segments) < 2:
            return False

    return True


def has_spacing_within_word(text):
    # Regex to detect patterns where letters are separated by multiple spaces
    pattern = re.compile(r'\b(\w)(\s{2,})(\w)\b')
    matches = pattern.findall(text)
    return bool(matches)


def get_element_with_parent(element):
    """ Get element and its immediate parent """
    parent = element.find_element(By.XPATH, "parent::*")
    return parent.get_attribute('outerHTML') + element.get_attribute('outerHTML')


def extract_elements_with_parents(tag_names, driver):
    """ Extract specified elements and their immediate parent """
    data = []
    for tag in tag_names:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for element in elements:
            data.append(get_element_with_parent(element))
    return data


def extract_elements_by_xpath(xpaths, driver):
    """ Extract specified elements by XPath and their immediate parent """
    data = []
    for xpath in xpaths:
        elements = driver.find_elements(By.XPATH, xpath)
        for element in elements:
            data.append(get_element_with_parent(element))
    return data


def extract_elements(tag_names, driver):
    """ Extract specified elements without their parents """
    data = []
    for tag in tag_names:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for element in elements:
            data.append(element.get_attribute('outerHTML'))
    return data


def extract_images_with_siblings(driver):
    """ Extract img elements and their first preceding and following siblings """
    data = []
    images = driver.find_elements(By.TAG_NAME, "img")
    for img in images:
        img_html = img.get_attribute('outerHTML')
        try:
            preceding_sibling = img.find_element(By.XPATH, "preceding-sibling::*[1]").get_attribute('outerHTML')
        except Exception:
            preceding_sibling = None
        try:
            following_sibling = img.find_element(By.XPATH, "following-sibling::*[1]").get_attribute('outerHTML')
        except Exception:
            following_sibling = None
        data.append({
            'image': img_html,
            'preceding_sibling': preceding_sibling,
            'following_sibling': following_sibling
        })
    return data


def extract_info_relation_elements(driver: webdriver.Chrome) -> dict:
    # Extract all tables
    tables = driver.find_elements(By.TAG_NAME, "table")
    table_data = [table.get_attribute('outerHTML') for table in tables]

    # Extract all <pre> elements
    pre_elements = driver.find_elements(By.TAG_NAME, "pre")
    pre_data = [pre.get_attribute('outerHTML') for pre in pre_elements]

    # Extract elements with the onClick attribute and their actual functions
    onclick_elements = driver.find_elements(By.XPATH, "//*[@onclick]")
    onclick_data = [(element.get_attribute('outerHTML'), element.get_attribute('onclick')) for element in
                    onclick_elements]

    # Combine standard and framework-specific click data
    combined_click_data = onclick_data

    # Extract elements with the ARIA attribute role without extracting nested elements
    aria_role_elements = driver.find_elements(By.XPATH, "//*[@role]")
    aria_role_data = []

    for element in aria_role_elements:
        is_nested = False
        try:
            parent = element.find_element(By.XPATH, "ancestor::*[@role]")
            if parent:
                is_nested = True
        except Exception as e:
            # No ancestor found, so the element is not nested
            pass
        if not is_nested:
            aria_role_data.append(element.get_attribute('outerHTML'))

    # Extract potential tables formatted using white space characters
    potential_tables = driver.find_elements(By.XPATH, "//pre | //div | //p | //span")
    whitespace_tables = []
    for element in potential_tables:
        try:
            text = element.text.strip()
            if has_whitespace_formatting(text):
                if text not in whitespace_tables:
                    whitespace_tables.append(text)
        except StaleElementReferenceException as e:
            continue

    article_elements = driver.find_elements(By.TAG_NAME, "article")
    article_data = [article.get_attribute('outerHTML') for article in article_elements]

    # Extract specified elements with parents
    elements_with_parents = extract_elements_with_parents(
        ["li", "ul", "ol", "dt", "dd"], driver
    )

    # Extract radio button and checkbox separately
    radio_checkbox_elements = extract_elements_by_xpath(
        ["//input[@type='radio']", "//input[@type='checkbox']"],
        driver
    )

    # Extract fieldset, paragraph, and legend without parents
    fieldset_elements = extract_elements(["fieldset"], driver)
    paragraph_elements = extract_elements(["p"], driver)
    legend_elements = extract_elements(["legend"], driver)

    heading_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    # Extract all headings
    headings = extract_elements(heading_tags, driver)
    list_tags = ['ul', 'ol', 'li']
    # Extract list elements with their parents
    list_elements = extract_elements(list_tags, driver)
    # Extract links
    link_elements = extract_elements(["a"], driver)

    # Extract img elements with first preceding and following siblings
    image_elements_with_siblings = extract_images_with_siblings(driver)

    # JavaScript to find hidden elements
    script = """
    return Array.from(document.querySelectorAll('*')).filter(el => {
        return el.style.display === 'none' || el.style.visibility === 'hidden' || el.hidden;
    });
    """

    # Execute the script to get hidden elements
    hidden_elements = driver.execute_script(script)
    hidden_elements_htmls = [element.get_attribute('outerHTML') for element in hidden_elements]

    # JavaScript to find elements with ::before or ::after content
    script = """
    let elements = document.querySelectorAll('*');
    let result = [];
    elements.forEach(el => {
        let before = window.getComputedStyle(el, '::before').getPropertyValue('content');
        let after = window.getComputedStyle(el, '::after').getPropertyValue('content');
        if (before !== 'none' || after !== 'none') {
            result.push({
                before: before,
                after: after,
                html: el.outerHTML
            });
        }
    });
    return result;
    """

    # Execute the script to get elements with CSS-inserted content
    elements_with_css_content = driver.execute_script(script)

    # Ensure the result is a list of dictionaries and print the result
    formatted_elements = [
        {'before': element['before'], 'after': element['after'], 'html': element['html']}
        for element in elements_with_css_content
    ]

    return {
        "tables": table_data,
        "pre_elements": pre_data,
        "onclick_elements": combined_click_data,
        "aria_role_elements": aria_role_data,
        "whitespace_tables": whitespace_tables,
        "article_elements": article_data,
        "elements_with_parents": elements_with_parents,
        "radio_checkbox_elements": radio_checkbox_elements,
        "fieldset_elements": fieldset_elements,
        "paragraph_elements": paragraph_elements,
        "legend_elements": legend_elements,
        "headings": headings,
        "lists": list_elements,
        "links": link_elements,
        "hidden_elements": hidden_elements_htmls,
        "css_insertion_elements": formatted_elements,
        "image_elements_with_siblings": image_elements_with_siblings
    }


def remove_table_markup(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    linearized_content = []

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["th", "td"])
            linearized_content.append(" ".join(cell.get_text(strip=True) for cell in cells))

    return "\n".join(linearized_content)


def extract_and_linearize_tables(driver: webdriver.Chrome):
    # Extract all tables
    tables = driver.find_elements(By.TAG_NAME, "table")
    table_data = [table.get_attribute('outerHTML') for table in tables]

    # Extract potential tables formatted using white space characters
    potential_tables = driver.find_elements(By.XPATH, "//pre | //div | //p | //span")
    whitespace_list = []
    for element in potential_tables:
        text = element.text.strip()
        if has_spacing_within_word(text):
            if text not in whitespace_list:
                whitespace_list.append(text)

    # Linearize the table contents
    table_lists = []
    for table in table_data:
        linearized = remove_table_markup(table)
        table_lists.append({
            "original": table,
            "linearized": linearized
        })

    # CSS Styles: float, flex, grid
    css_selectors = [
        '[style*="float"]',
        '[style*="flex"]',
        '[style*="grid"]'
    ]

    # Find elements by CSS selectors
    css_elements = []
    for selector in css_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        css_elements.extend(elements)

    # ARIA Attributes: aria-flowto
    aria_elements = driver.find_elements(By.XPATH, '//*[@aria-flowto]')

    # Combine CSS and ARIA affected elements
    combined_elements = css_elements + aria_elements

    # Function to find common ancestor
    def find_common_ancestor(elements):
        ancestor_map = {}
        for element in elements:
            parent = element.find_element(By.XPATH, '..')
            grandparent = parent.find_element(By.XPATH, '..')
            ancestor_map[element] = (parent, grandparent)

        unique_ancestors = set()
        parent_set = set()
        grandparent_set = set()

        for element, (parent, grandparent) in ancestor_map.items():
            if parent in parent_set or grandparent in grandparent_set:
                continue
            parent_set.add(parent)
            grandparent_set.add(grandparent)
            unique_ancestors.add(parent if parent in parent_set else grandparent)

        return unique_ancestors

    unique_elements = find_common_ancestor(combined_elements)
    elements_rearranged = [ele.get_attribute('outerHTML') for ele in unique_elements]

    return table_lists, whitespace_list, elements_rearranged


def extract_name_role_elements(driver: webdriver.Chrome) -> dict:
    # Define the XPath to find all relevant elements
    xpaths = {
        'button': "//button | //input[@type='button' or @type='submit' or @type='reset'] | //*[@role='button']",
        'aria-hidden': "//*[@aria-hidden]",
        'menuitem': "//*[@role='menuitem']",
        'iframe': "//iframe",
        "link": "//a | //*[@role='link']",
        'script-controlled': (
            "//div[@onclick or @onfocus or @onblur or @onchange or @oninput or @onmouseover or @onmouseout or "
            "@ondblclick or @onkeydown or @onkeypress or @onkeyup] | "
            "//span[@onclick or @onfocus or @onblur or @onchange or @oninput or @onmouseover or @onmouseout or "
            "@ondblclick or @onkeydown or @onkeypress or @onkeyup]"
        )
    }

    element_html_dict = {
        'button': [],
        'aria-hidden': [],
        'menuitem': [],
        'iframe': [],
        'script-controlled': [],
        'link': []
    }

    for key, xpath in xpaths.items():
        try:
            # Find all elements matching the XPath for the current key
            elements = driver.find_elements(By.XPATH, xpath)

            for element in elements:
                # Check for aria-labelledby and replace it with aria-label if necessary
                aria_labelledby = element.get_attribute('aria-labelledby')
                if aria_labelledby:
                    labelledby_element = driver.find_element(By.ID, aria_labelledby)
                    aria_label = labelledby_element.text if labelledby_element else ''
                    driver.execute_script("arguments[0].setAttribute(arguments[1], arguments[2]);",
                                          element, 'aria-label', aria_label)
                    driver.execute_script("arguments[0].removeAttribute(arguments[1]);",
                                          element, 'aria-labelledby')
                # Append the src attribute into the iframe tag if it's an iframe
                if element.tag_name == 'iframe':
                    src = element.get_attribute('src')
                    driver.execute_script("arguments[0].setAttribute('src', arguments[1]);", element, src)

                # Get the outer HTML of the element
                outer_html = element.get_attribute('outerHTML')
                element_html_dict[key].append(outer_html)
        except:
            continue

    return element_html_dict


def extract_all_controls(driver: webdriver.Chrome) -> list:
    # Define the XPath to find the specified elements and icons
    control_xpaths = (
        "//select | "
        "//textarea | "
        "//datalist | "
        "//output | "
        "//meter | "
        "//progress | "
        "//details | "
        "//summary | "
        "//menu | "
        "//menuitem | "
        "//i | "
        "//svg | "
        "//*[@role='img'] | "
        "//*[contains(@class, 'icon') or contains(@class, 'icon-')]"
    )

    # Find all elements matching the XPath
    controls = driver.find_elements(By.XPATH, control_xpaths)

    control_html_list = []
    unique_elements_html = set()

    for control in controls:
        # Check if aria-labelledby needs to be converted to aria-label
        aria_labelledby = control.get_attribute('aria-labelledby')
        if aria_labelledby:
            # Replace aria-labelledby with aria-label
            labelled_element = driver.find_element(By.ID, aria_labelledby)
            if labelled_element:
                text_content = labelled_element.text.strip()
                driver.execute_script("arguments[0].setAttribute('aria-label', arguments[1])", control,
                                      text_content)
                driver.execute_script("arguments[0].removeAttribute('aria-labelledby')", control)

        # Add to set if not already included based on its outerHTML
        unique_elements_html.add(control.get_attribute('outerHTML'))

    return list(unique_elements_html)


def hash_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def capture_updating_moving_element(driver: webdriver.Chrome) -> dict:
    result_dict = {}
    # Find all <blink> and <marquee> elements
    blink_elements = driver.find_elements(By.TAG_NAME, 'blink')
    marquee_elements = driver.find_elements(By.TAG_NAME, 'marquee')

    # Extract the entire text content of the page
    all_text_content_prev = driver.find_element(By.TAG_NAME, 'body').text

    # Take the first screenshot
    screenshot_counter = 1
    driver.save_screenshot(TEMP_FILE_FOLDER + f'/moving_{screenshot_counter}.png')
    img_str_before = encode_image(TEMP_FILE_FOLDER + f'/moving_{screenshot_counter}.png')

    # Wait for 5 seconds
    time.sleep(5)

    # Extract the text content again and hash it
    all_text_content_after = driver.find_element(By.TAG_NAME, 'body').text

    # Take the second screenshot
    screenshot_counter += 1
    driver.save_screenshot(TEMP_FILE_FOLDER + f'/moving_{screenshot_counter}.png')
    img_str_after = encode_image(TEMP_FILE_FOLDER + f'/moving_{screenshot_counter}.png')

    updating_images = []
    # Check if the hashes are not equal
    if all_text_content_prev != all_text_content_after:
        while True:
            # Scroll down the page
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(5)  # Wait for the page to load

            # Take another screenshot
            updating_screenshot_counter = 0
            driver.save_screenshot(TEMP_FILE_FOLDER + f'/updating_{updating_screenshot_counter}.png')
            updating_images.append(encode_image(TEMP_FILE_FOLDER + f'/updating_{updating_screenshot_counter}.png'))
            updating_screenshot_counter += 1

            # Check if we've reached the bottom of the page
            if driver.execute_script("return (window.innerHeight + window.scrollY) >= document.body.scrollHeight;"):
                break

    result_dict['blink'] = [elem.get_attribute('outerHTML') for elem in blink_elements]
    result_dict['marquee'] = [elem.get_attribute('outerHTML') for elem in marquee_elements]
    result_dict['moving_images'] = [img_str_before, img_str_after]
    result_dict['updating_images'] = updating_images
    return result_dict


def extract_tag_with_attributes_only(element):
    soup = BeautifulSoup(element.get_attribute('outerHTML'), 'html.parser')
    tag = soup.find()
    # Remove the children
    for child in tag.find_all():
        child.decompose()
    return str(tag)


def extract_specific_role_elements(driver: webdriver.Chrome) -> dict:
    # Define the roles we are interested in
    roles = ['application', 'article', 'banner', 'complementary', 'contentinfo',
             'document', 'form', 'main', 'navigation', 'search']

    # Find elements by role
    elements_by_role = []
    for role in roles:
        elements_by_role.extend(driver.find_elements(By.XPATH, f"//*[@role='{role}']"))

    # Find <main> elements
    main_elements = driver.find_elements(By.TAG_NAME, 'main')

    # Find all hyperlink elements
    hyperlink_elements = driver.find_elements(By.TAG_NAME, 'a')

    # Find <form> elements
    form_elements = driver.find_elements(By.TAG_NAME, 'form')

    # Find <application> elements
    application_elements = driver.find_elements(By.TAG_NAME, 'application')

    # Find <article> elements
    article_elements = driver.find_elements(By.TAG_NAME, 'article')

    # Prepare the result dictionary
    result = {}

    # Process role-specific elements
    for element in elements_by_role:
        role = element.get_attribute('role')
        outer_html = extract_tag_with_attributes_only(element)

        if role not in result:
            result[role] = []

        result[role].append(outer_html)

    # Process <main> elements
    for element in main_elements:
        role = 'main'
        outer_html = extract_tag_with_attributes_only(element)

        if role not in result:
            result[role] = []

        result[role].append(outer_html)

    # Process hyperlink elements
    for element in hyperlink_elements:
        role = 'a'

        if role not in result:
            result[role] = []

        result[role].append(element.get_attribute('outerHTML'))

    # Process <form> elements
    for element in form_elements:
        tag = 'form'
        outer_html = extract_tag_with_attributes_only(element)

        if tag not in result:
            result[tag] = []

        result[tag].append(outer_html)

    # Process <application> elements
    for element in application_elements:
        tag = 'application'
        outer_html = extract_tag_with_attributes_only(element)

        if tag not in result:
            result[tag] = []

        result[tag].append(outer_html)

    # Process <article> elements
    for element in article_elements:
        tag = 'article'
        outer_html = extract_tag_with_attributes_only(element)

        if tag not in result:
            result[tag] = []

        result[tag].append(outer_html)

    return result


def extract_sensory_elements(driver: webdriver.Chrome) -> dict:
    def get_outer_html(element):
        if element is not None:
            return element.get_attribute('outerHTML')
        return ""

    text = driver.find_element(By.TAG_NAME, "body").text
    intermediate_sensory_result = detect_sensory_instructions(text)
    try:
        dict_obj = ast.literal_eval(intermediate_sensory_result)
        other_sensory_elements = dict_obj['other sensory_information']
        color_sensory_elements = dict_obj['color_information']
        other_sensory_results = []
        color_sensory_results = []

        for other_element in other_sensory_elements:
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{other_element}')]")
                parent = element.find_element(By.XPATH, "./..")

                try:
                    parent_sibling = parent.find_element(By.XPATH, "following-sibling::*[1]")
                except NoSuchElementException:
                    parent_sibling = None

                parent_html = parent.get_attribute('outerHTML')
                parent_sibling_html = parent_sibling.get_attribute("outerHTML") if parent_sibling else ""

                if parent.tag_name == "form" and (parent_sibling is None or parent_sibling.tag_name == "form"):
                    combined_html = parent_html
                else:
                    combined_html = f"{parent_html} {parent_sibling_html}"

                other_sensory_results.append(combined_html.strip())

            except Exception as e:
                continue

        for color_element in color_sensory_elements:
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{color_element}')]")
                parent = element.find_element(By.XPATH, "./..")

                try:
                    parent_sibling = parent.find_element(By.XPATH, "following-sibling::*[1]")
                except NoSuchElementException:
                    parent_sibling = None

                parent_html = parent.get_attribute("outerHTML")
                parent_sibling_html = parent_sibling.get_attribute("outerHTML") if parent_sibling else ""

                if parent.tag_name == "form" and (parent_sibling is None or parent_sibling.tag_name == "form"):
                    combined_html = parent_html
                else:
                    combined_html = f"{parent_html} {parent_sibling_html}"

                color_sensory_results.append(combined_html.strip())

            except Exception as e:
                continue
    except Exception as e:
        return {"other_sensory": [], "color_sensory": []}

    return {"other_sensory": other_sensory_results, "color_sensory": color_sensory_results}


def extract_location_related_information(driver: webdriver.Chrome) -> dict:
    # Load the screenshot of the page
    location_dict = {}
    driver.save_screenshot(TEMP_FILE_FOLDER + "/location.png")
    location_dict["screenshot"] = encode_image(TEMP_FILE_FOLDER + "/location.png")
    location_dict["title"] = driver.title
    return location_dict


def is_element_visible(element):
    try:
        # Check if the element is displayed
        if not element.is_displayed():
            return False

        # Check if the element is hidden via style
        style = element.get_attribute('style')
        if 'display: none' in style or 'visibility: hidden' in style or 'opacity: 0' in style:
            return False

        # If none of the conditions above are met, the element is visible
        return True
    except:
        return False


def extract_link_form_screenshot(driver: webdriver.Chrome) -> dict:
    # Find all anchor tags
    link_img_strs = []
    form_img_strs = []
    margin = 30

    # Get the initial scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Find all visible anchor tags and elements with role="link"
        anchor_links = [link for link in driver.find_elements(By.TAG_NAME, 'a') if is_element_visible(link)]
        role_links = [link for link in driver.find_elements(By.XPATH, '//*[@role="link"]') if is_element_visible(link)]
        all_links = anchor_links + role_links

        # Capture screenshots of visible links
        for i, link in enumerate(all_links):
            try:
                # Get the link's position and size
                location = link.location_once_scrolled_into_view
                size = link.size

                # Capture the screenshot of the entire page
                screenshot = driver.get_screenshot_as_png()

                # Open the screenshot using PIL
                screenshot_image = Image.open(BytesIO(screenshot))

                # Calculate the bounding box for the link
                left = max(location['x'] - margin, 0)
                top = max(location['y'] - margin, 0)
                right = location['x'] + size['width'] + margin
                bottom = location['y'] + size['height'] + margin

                # Crop the screenshot to the bounding box
                link_screenshot = screenshot_image.crop((left, top, right, bottom))

                # Save the screenshot
                link_screenshot.save(f'{TEMP_FILE_FOLDER}/link_{len(link_img_strs)}.png')
                link_img_strs.append(encode_image(f'{TEMP_FILE_FOLDER}/link_{len(link_img_strs)}.png'))
            except Exception as e:
                print(f"Error capturing link {i}: {str(e)}")
                continue

        # Find all visible form tags and elements with role="form"
        form_tags = [form for form in driver.find_elements(By.TAG_NAME, 'form') if is_element_visible(form)]
        role_forms = [form for form in driver.find_elements(By.XPATH, '//*[@role="form"]') if is_element_visible(form)]
        all_forms = form_tags + role_forms

        # Capture screenshots of visible forms
        for i, form in enumerate(all_forms):
            try:
                # Get the form's position and size
                location = form.location
                size = form.size
                screenshot = driver.get_screenshot_as_png()

                # Open the screenshot using PIL
                screenshot_image = Image.open(BytesIO(screenshot))

                # Calculate the bounding box for the form
                left = max(location['x'] - margin, 0)
                top = max(location['y'] - margin, 0)
                right = location['x'] + size['width'] + margin
                bottom = location['y'] + size['height'] + margin

                # Crop the screenshot to the bounding box
                form_screenshot = screenshot_image.crop((left, top, right, bottom))

                # Save the screenshot
                form_screenshot.save(TEMP_FILE_FOLDER + f'/form_{len(form_img_strs)}.png')
                form_img_strs.append(encode_image(TEMP_FILE_FOLDER + f'/form_{len(form_img_strs)}.png'))
            except Exception as e:
                print(f"Error capturing form {i}: {str(e)}")
                continue

        # Scroll down to the next page segment
        driver.execute_script("window.scrollBy(0, window.innerHeight);")

        # Wait for the scrolling to complete and content to load
        time.sleep(2)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    return {"links": link_img_strs, "forms": form_img_strs}


def extract_target_size(driver: webdriver.Chrome) -> dict:
    # JavaScript function to get the size and position of an element
    get_size_and_position_script = """
    function checkTargetSizeAndPosition(element) {
        var rect = element.getBoundingClientRect();
        return { 
            width: rect.width, 
            height: rect.height,
            top: rect.top,
            left: rect.left,
            tag: element.outerHTML
        };
    }
    return checkTargetSizeAndPosition(arguments[0]);
    """

    small_elements_list = []
    small_elements_enhanced_list = []
    last_screenshot = None

    # Get the initial scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # XPath for different control elements
        control_xpaths = (
            "//select | //textarea | //datalist | //output | //meter | //progress | //details | "
            "//summary | //menu | //menuitem | //i | //svg | //*[@role='img'] | "
            "//*[contains(@class, 'icon') or contains(@class, 'icon-')] | "
            "//button | //input[@type='button'] | //input[@type='submit'] | //input[@type='reset'] | "
            "//input[@type='checkbox'] | //input[@type='radio'] | //a[@href] | //option | "
            "//input[@type='search'] | //*[@role='button'] | //*[@role='checkbox'] | //*[@role='gridcell'] | "
            "//*[@role='link'] | //*[@role='menuitem'] | //*[@role='menuitemcheckbox'] | "
            "//*[@role='menuitemradio'] | //*[@role='option'] | //*[@role='radio'] | "
            "//*[@role='searchbox'] | //*[@role='switch'] | //*[@role='tab'] | //*[@role='treeitem']"
        )

        # Find all elements matching the combined XPath
        elements = driver.find_elements(By.XPATH, control_xpaths)

        # Extract sizes and positions of each visible element
        elements_info = []
        for element in elements:
            if is_element_visible(element):
                info = driver.execute_script(get_size_and_position_script, element)
                elements_info.append(info)

        # Filter elements with size less than 24x24 pixels
        small_elements = [info for info in elements_info if info['width'] < 24 or info['height'] < 24]
        small_elements_44 = [info for info in elements_info if info['width'] < 44 or info['height'] < 44]

        last_screenshot_small = None
        last_screenshot_str_small = None

        # Process small elements (less than 24x24 pixels)
        for i, info in enumerate(small_elements):
            scroll_script = f"window.scrollTo(0, {info['top']} + window.scrollY - window.innerHeight / 2);"
            driver.execute_script(scroll_script)

            # Take full screenshot of the page
            new_screenshot = driver.get_screenshot_as_png()
            full_screenshot_path = TEMP_FILE_FOLDER + f"/full_screenshot_element_{i + 1}.png"

            if last_screenshot_small is None or new_screenshot != last_screenshot_small:
                # Save the new screenshot as a file
                full_screenshot = Image.open(io.BytesIO(new_screenshot))
                full_screenshot.save(full_screenshot_path)

                # Encode the new screenshot and update the last screenshot
                full_screenshot_str = encode_image(full_screenshot_path)
                last_screenshot_str_small = full_screenshot_str
                last_screenshot_small = new_screenshot
            else:
                # Reuse the previous screenshot string
                full_screenshot_str = last_screenshot_str_small

            # Convert the screenshot to an OpenCV image
            screenshot_cv = cv2.cvtColor(np.array(full_screenshot), cv2.COLOR_RGB2BGR)

            # Draw circle on the screenshot
            center_x = int(info['left'] + info['width'] / 2)
            center_y = int(info['top'] + info['height'] / 2)
            cv2.circle(screenshot_cv, (center_x, center_y), 12, (0, 0, 255), 2)  # Draw red circle with radius 12

            # Convert the modified OpenCV image back to PIL Image
            screenshot_with_circle = Image.fromarray(cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2RGB))

            # Crop around the circle with margins
            margins = 20  # Margin in pixels
            top = max(0, int(info['top']) - margins)
            left = max(0, int(info['left']) - margins)
            bottom = min(screenshot_with_circle.height, int(info['top'] + info['height']) + margins)
            right = min(screenshot_with_circle.width, int(info['left'] + info['width']) + margins)

            if bottom <= top or right <= left:
                continue

            # Save the cropped image
            cropped_image_path = TEMP_FILE_FOLDER + f"/cropped_screenshot_element_{i + 1}.png"
            cropped_image = screenshot_with_circle.crop((left, top, right, bottom))
            cropped_image.save(cropped_image_path)
            cropped_image_str = encode_image(cropped_image_path)

            small_elements_list.append({"tag": info['tag'], "full": full_screenshot_str, "cropped": cropped_image_str})

        # Scroll down to the next page segment
        driver.execute_script("window.scrollBy(0, window.innerHeight);")

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    last_screenshot = None
    last_screenshot_str = None

    for i, info in enumerate(small_elements_44):
        scroll_script = f"window.scrollTo(0, {info['top']} + window.scrollY - window.innerHeight / 2);"
        driver.execute_script(scroll_script)

        # Take full screenshot of the page
        new_screenshot = driver.get_screenshot_as_png()
        full_screenshot_path = TEMP_FILE_FOLDER + f"/full_screenshot_element_44_{i + 1}.png"

        if last_screenshot is None or new_screenshot != last_screenshot:
            # Save the new screenshot as a file
            full_screenshot = Image.open(io.BytesIO(new_screenshot))
            full_screenshot.save(full_screenshot_path)

            # Encode the new screenshot and update the last screenshot
            full_screenshot_str_44 = encode_image(full_screenshot_path)
            last_screenshot_str = full_screenshot_str_44
            last_screenshot = new_screenshot
        else:
            # Reuse the previous screenshot string
            full_screenshot_str_44 = last_screenshot_str

        small_elements_enhanced_list.append({"tag": info['tag'], "full": full_screenshot_str_44})

    return {"small_elements": small_elements_list, "small_elements_44": small_elements_enhanced_list}


def get_css_property(element, property_name):
    return element.value_of_css_property(property_name)


def is_text_justified(element):
    text_align = get_css_property(element, 'text-align')
    text_justify = get_css_property(element, 'text-justify')
    display = get_css_property(element, 'display')
    justify_content = get_css_property(element, 'justify-content')
    align_items = get_css_property(element, 'align-items')

    # Check if text is justified using common properties
    return text_align == 'justify' or text_justify == 'distribute' or \
        (display in ['flex', 'inline-flex', 'grid', 'inline-grid'] and justify_content == 'space-between') or \
        align_items == 'stretch'


def calculate_line_spacing(line_height, font_size):
    if line_height == 'normal':
        return float(font_size) * 1.2  # Assuming browser's default normal line-height is 1.2 times the font size
    elif line_height.endswith('px'):
        return float(line_height.replace('px', ''))
    elif line_height.endswith('%'):
        return float(line_height.replace('%', '')) / 100 * float(font_size)
    else:
        return float(line_height) * float(font_size)


def crop_screenshot(driver, element, crop_path, margin=10, zoom_factor=2) -> bool:
    location = element.location
    size = element.size
    screenshot = driver.get_screenshot_as_png()

    # Get viewport dimensions
    window_width = driver.execute_script("return window.innerWidth;")
    window_height = driver.execute_script("return window.innerHeight;")

    image = Image.open(io.BytesIO(screenshot))
    left = max(location['x'] * zoom_factor - margin, 0)
    top = max(location['y'] * zoom_factor - margin, 0)
    right = min((location['x'] + size['width']) * zoom_factor + margin, window_width)
    bottom = min((location['y'] + size['height']) * zoom_factor + margin, window_height)

    if left < right and top < bottom:
        cropped_image = image.crop((left, top, right, bottom))
        cropped_image.save(crop_path)
        return True
    return False


def extract_text_blocks_with_details(driver: webdriver.Chrome) -> list:
    # driver.execute_script("document.body.style.zoom='200%'")
    original_size = driver.get_window_size()
    driver.maximize_window()

    # Define tags to search for text blocks
    tags = ['p', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'article', 'section', 'blockquote', 'li',
            'aside', 'footer', 'header', 'nav', 'figure', 'figcaption', 'code']

    # Define a regex pattern to identify blocks of text (more than one sentence)
    block_pattern = re.compile(r'([A-Z][^.!?]*[.!?]\s*){2,}')

    text_blocks_details = []
    text_set = set()

    for tag in tags:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for element in elements:
            text = element.text.strip()
            if block_pattern.search(text) and text not in text_set:
                text_set.add(text)
                # Scroll to the element and ensure it's fully visible
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(1)  # Wait for scrolling to complete

                # Get width, font size, justify, line spacing, and paragraph spacing
                width = float(get_css_property(element, 'width').replace('px', ''))
                font_size = float(get_css_property(element, 'font-size').replace('px', ''))
                line_height = get_css_property(element, 'line-height')
                line_spacing = calculate_line_spacing(line_height, font_size)
                margin_bottom = get_css_property(element, 'margin-bottom')

                # Calculate the number of characters per line
                avg_char_width = font_size * 0.6  # Approximation: average character width is 0.6 times the font size
                chars_per_line = int(width / avg_char_width)

                justified = is_text_justified(element)

                block_details = {
                    'text': text,
                    'width': width,
                    'font_size': font_size,
                    'chars_per_line': chars_per_line,
                    'justified': justified,
                    'line_spacing': line_spacing,
                    'paragraph_spacing': margin_bottom
                    # 'screenshot': screenshot_str
                }

                text_blocks_details.append(block_details)
    driver.execute_script("document.body.style.zoom='100%'")
    driver.set_window_size(original_size['width'], original_size['height'])
    text_blocks_details.append({
        'text': '',
        'width': '',
        'font_size': '',
        'chars_per_line': '',
        'justified': '',
        'line_spacing': '',
        'paragraph_spacing': '',
        'screenshot': encode_image(TEMP_FILE_FOLDER + "/screenshot_zoomed.png")
    })
    return text_blocks_details


def adjust_page_styles(driver):
    # JavaScript to adjust styles
    script = """
    const elements = document.querySelectorAll('*');
    elements.forEach(element => {
        const style = window.getComputedStyle(element);
        const fontSize = parseFloat(style.fontSize);
        if (fontSize > 0) {
            element.style.lineHeight = (1.5 * fontSize) + 'px';
            element.style.marginBottom = (2 * fontSize) + 'px';
            element.style.letterSpacing = (0.12 * fontSize) + 'px';
            element.style.wordSpacing = (0.16 * fontSize) + 'px';
        }
    });
    """
    # Execute the script
    driver.execute_script(script)


def revert_page_styles(driver):
    # JavaScript to revert styles
    script = """
    const elements = document.querySelectorAll('*');
    elements.forEach(element => {
        element.style.lineHeight = '';
        element.style.marginBottom = '';
        element.style.letterSpacing = '';
        element.style.wordSpacing = '';
    });
    """
    # Execute the script
    driver.execute_script(script)


def extract_text_spacing_screenshots(driver: webdriver.Chrome) -> list:
    adjust_page_styles(driver)
    screenshot_counter = 0
    images = []

    while True:
        # Check if we've reached the bottom of the page before taking a screenshot
        at_bottom = driver.execute_script(
            "return (window.innerHeight + window.scrollY) >= document.body.scrollHeight;")

        if at_bottom:
            # Take a screenshot at the bottom before breaking out of the loop
            screenshot_path = f'{TEMP_FILE_FOLDER}/textspacing_{screenshot_counter}.png'
            driver.save_screenshot(screenshot_path)
            images.append(encode_image(screenshot_path))
            break

        # Take a screenshot if not at the bottom
        screenshot_path = f'{TEMP_FILE_FOLDER}/textspacing_{screenshot_counter}.png'
        driver.save_screenshot(screenshot_path)
        images.append(encode_image(screenshot_path))
        screenshot_counter += 1

        # Scroll down the page
        driver.execute_script("window.scrollBy(0, window.innerHeight);")

    revert_page_styles(driver)
    return images


def find_related_screenshots(driver: webdriver.Chrome, folder_path) -> list:
    before_files = []
    screenshot_file = None

    # Walk through the directory
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # Check if the file ends with 'before'
            if file.endswith('before'):
                before_files.append(os.path.join(root, file))

    # If 'before' files are found, return them
    if before_files:
        return [encode_image(file) for file in before_files]

    # If no 'before' files are found, look for 'screenshot_original.png'
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file == 'screenshot_original.png':
                screenshot_file = os.path.join(root, file)
                break
        if screenshot_file:
            break

    # Return the 'screenshot_original.png' file if found, otherwise return an empty list
    return [encode_image(screenshot_file)] if screenshot_file else []


def extract_non_text_contrast(driver: webdriver.Chrome) -> dict:
    # Identify focusable elements
    focusable_selectors = 'a, button, input, textarea, [tabindex]'
    focusable_elements = driver.find_elements(By.CSS_SELECTOR, focusable_selectors)

    def get_css_property(element, property_name):
        return driver.execute_script(
            "return window.getComputedStyle(arguments[0]).getPropertyValue(arguments[1]);",
            element, property_name
        )

    # Extract CSS styles for focus state and compute contrast ratios
    focus_styles = []
    required_ratio = 3.0

    for element in focusable_elements:
        driver.execute_script("arguments[0].focus();", element)
        border_color = get_css_property(element, 'border-color')
        outline_color = get_css_property(element, 'outline-color')
        background_color = get_css_property(element, 'background-color')

        focus_styles.append({
            'element': element.get_attribute('outerHTML'),
            'border_color': border_color,
            'outline_color': outline_color,
            'background_color': background_color,
        })

    # Output the results in a structured format
    results = {
        'focusable_elements': focus_styles,
        'required_contrast_ratio': required_ratio
    }
    return results


def extract_event_function(element, event_type, driver):
    outer_html = driver.execute_script("return arguments[0].outerHTML;", element)

    # Extract standard JavaScript event handlers
    event_function = driver.execute_script("""
        var element = arguments[0];
        var eventHandler = element.getAttribute(arguments[1]);
        if (eventHandler) {
            try {
                return new Function(eventHandler).toString();
            } catch (e) {
                return eventHandler;
            }
        } else {
            return null;
        }
    """, element, event_type)

    return outer_html, event_function


def extract_event_handlers(driver) -> list:
    # Dictionaries to hold the element outerHTML and its associated function
    special_input_dict = {}
    other_input_dict = {}

    # Function to extract event handlers for a given element and event type

    # Get all input elements within the form
    input_elements = driver.find_elements(By.TAG_NAME, 'input')
    for input_element in input_elements:
        input_type = input_element.get_attribute('type')
        if input_type in ['radio', 'checkbox']:
            outer_html, onclick_function = extract_event_function(input_element, 'onclick', driver)
            if onclick_function:
                special_input_dict[outer_html] = onclick_function
        else:
            outer_html, onchange_function = extract_event_function(input_element, 'onchange', driver)
            if onchange_function:
                other_input_dict[outer_html] = onchange_function

    # Get all select elements within the form
    select_elements = driver.find_elements(By.TAG_NAME, 'select')
    for select_element in select_elements:
        outer_html, onchange_function = extract_event_function(select_element, 'onclick', driver)
        if onchange_function:
            special_input_dict[outer_html] = onchange_function

    return [special_input_dict, other_input_dict]


def extract_change_on_request_element(driver) -> list:
    # Dictionaries to hold the element outerHTML and its associated function code
    onclick_dict = {}
    onblur_dict = {}

    # Extract elements with onclick functions
    elements_with_onclick = driver.find_elements(By.CSS_SELECTOR, '[onclick]')
    for element in elements_with_onclick:
        outer_html, onclick_function = extract_event_function(element, 'onclick', driver)
        if onclick_function:
            onclick_dict[outer_html] = onclick_function

    # Extract input elements with onblur functions
    input_elements_with_onblur = driver.find_elements(By.CSS_SELECTOR, 'input')
    for input_element in input_elements_with_onblur:
        outer_html, onblur_function = extract_event_function(input_element, 'onblur', driver)
        if onblur_function:
            onblur_dict[outer_html] = onblur_function

    return [onclick_dict, onblur_dict]
