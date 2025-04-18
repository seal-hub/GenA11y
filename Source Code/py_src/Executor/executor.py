import logging
from multiprocessing import Manager, Process
import pandas as pd
import requests
from requests.compat import chardet
from selenium.webdriver.firefox.options import Options
from ElementExtraction.extract_related_elements import *
from A11yDetector.a11y_detector import *


def extract_data_from_excel(file_path: str, start_row: int, end_row: int):
    """
    Reads data from an Excel file and returns a list of tuples.
    Each tuple contains the URL and the Folder Name from the respective columns.
    """
    # Read the Excel file
    df = pd.read_excel(file_path)

    # Extract data within the specified range of rows
    df_subset = df.iloc[start_row:end_row + 1]

    # Extract data from 'URL' and 'Folder Name' columns
    data_tuples = list(zip(df_subset['URL'], df_subset['Folder Name']))

    return data_tuples

def prepare_driver(url: str):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(url)
    wait_for_load(driver)
    return driver


def check_combined_detection(combined_detection_result: str) -> bool:
    # Check if combined result contains both "Yes" and "data-mutation-id"
    if "Yes" in combined_detection_result and ("data-mutation-id" in combined_detection_result):
        return True
    else:
        return False


def check_non_text_content(url: str):
    """
    SC 1.1.1: Non-text Content
    """
    driver = prepare_driver(url)
    visual_elements = extract_related_visual_elements(driver)
    detection_result = detect_non_text_content_aggregated_violation(visual_elements)
    driver.quit()
    return detection_result


def check_info_relation(url: str):
    """
    SC 1.3.1: Info and Relationships
    """
    driver = prepare_driver(url)
    relation_elements = extract_info_relation_elements(driver)
    # Reuse this in text resizing
    screenshot_list = extract_original_screenshot(driver)
    detection_result = aggregate_info_relation_violation_responses(relation_elements, screenshot_list)
    driver.quit()
    return detection_result


def check_meaningful_sequence(url: str):
    """
    SC 1.3.2: Meaningful Sequence
    """
    driver = prepare_driver(url)
    sequence_list = extract_and_linearize_tables(driver)
    detection_result = detect_meaningful_sequence_violation(sequence_list[0], sequence_list[1], sequence_list[2])
    driver.quit()
    return detection_result


def check_sensory_characteristics(url: str):
    """
    SC 1.3.3: Sensory Characteristics
    """
    driver = prepare_driver(url)
    sensory_elements = extract_sensory_elements(driver)
    detection_result = detect_sensory_characteristics_violation(sensory_elements)
    driver.quit()
    return detection_result


def check_orientation(url: str):
    """
    SC 1.3.4: Orientation
    """
    driver = prepare_driver(url)
    orientation_elements = check_orientation_and_transform(driver)
    detection_result = detect_orientation_violation(orientation_elements)
    driver.quit()
    return detection_result


def check_input_purpose(url: str):
    """
    SC 1.3.5: Input Purpose
    """
    driver = prepare_driver(url)
    input_elements = extract_input_elements(driver)
    detection_result = detect_input_without_purpose(input_elements)
    driver.quit()
    return detection_result


def check_use_of_color(url: str):
    """
    SC 1.4.1: Use of Color
    """
    driver = prepare_driver(url)
    link_form_screenshots = extract_link_form_screenshot(driver)
    detection_result = detect_use_of_color_violation(link_form_screenshots)
    driver.quit()
    return detection_result


def check_audio_control(url: str):
    """
    SC 1.4.2: Audio Control
    """
    driver = prepare_driver(url)
    audio_elements = find_autoplay_audio_elements(driver)
    detection_result = detect_no_audio_control(audio_elements)
    driver.quit()
    return detection_result


def check_color_contrast_aa(url: str):
    """
    SC 1.4.3: Contrast (Minimum)
    """
    driver = prepare_driver(url)
    contrast_related_elements, elements_with_background_image = extract_contrast_related_elements(driver)
    detection_result = detect_color_contrast_violation_aa(contrast_related_elements, elements_with_background_image)
    driver.quit()
    return detection_result


def check_resize_text(url: str):
    """
    SC 1.4.4: Resize Text
    """
    driver = prepare_driver(url)

    text_resizing_dict = extract_text_resizing(driver)
    detection_result = detect_text_resizing_violation(text_resizing_dict)
    driver.quit()
    return detection_result


def check_color_contrast_aaa(url: str):
    """
    SC 1.4.6: Contrast (Enhanced)
    """
    driver = prepare_driver(url)
    contrast_related_elements, elements_with_background_image = extract_contrast_related_elements(driver)
    detection_result = detect_color_contrast_violation_aaa(contrast_related_elements, elements_with_background_image)
    driver.quit()
    return detection_result


def check_image_of_text(url: str):
    """
    SC 1.4.5 & 1.4.9: Image of Text
    """
    driver = prepare_driver(url)
    image_text_elements = extract_img_urls(driver)
    detection_result = detect_misuse_images_of_text(image_text_elements)
    driver.quit()
    return detection_result


def check_visual_presentation(url: str):
    """
    SC 1.4.8: Visual Presentation
    """
    driver = prepare_driver(url)
    text_blocks = extract_text_blocks_with_details(driver)
    detection_result = detect_visual_presentation_violation(text_blocks)
    driver.quit()
    return detection_result


def check_reflow(url: str):
    """
    SC 1.4.10: Reflow
    """
    driver = prepare_driver(url)
    text_reflow_dict = extract_text_reflow(driver)
    detection_result = detect_reflow_violation(text_reflow_dict)
    driver.quit()
    return detection_result


def check_non_text_contrast(url: str):
    """
    SC 1.4.11: Non-text Contrast
    """
    driver = prepare_driver(url)
    focusable_element = extract_non_text_contrast(driver)
    detection_result = detect_non_text_contrast_violation(focusable_element['focusable_elements'])
    driver.quit()
    return detection_result


def check_text_spacing(url: str):
    """
    SC 1.4.12: Text Spacing
    """
    driver = prepare_driver(url)
    text_spacing_elements = extract_text_spacing_screenshots(driver)
    detection_result = detect_text_spacing_violation(text_spacing_elements)
    driver.quit()
    return detection_result


def check_timing_adjustable(url: str):
    """
    SC 2.2.1: Timing Adjustable
    """
    driver = prepare_driver(url)
    meta_element_redirection = extract_meta_refresh(driver)
    screenshots = take_screenshots_and_compare(driver, duration=20)
    detection_result = detect_timing_adjustable_violation([meta_element_redirection, screenshots])
    driver.quit()
    return detection_result


def check_pause_stop_hide(url: str):
    """
    SC 2.2.2: Pause, Stop, Hide
    """
    driver = prepare_driver(url)
    moving_and_updating = capture_updating_moving_element(driver)
    detection_result = detect_moving_updating_element_violation(moving_and_updating)
    driver.quit()
    return detection_result


def check_bypass_blocks(url: str):
    """
    SC 2.4.1: Bypass Blocks
    """
    driver = prepare_driver(url)
    bypass_blocks = extract_specific_role_elements(driver)
    detection_result = detect_bypass_blocks_violation(bypass_blocks)
    driver.quit()
    return detection_result


def check_page_title(url: str):
    """
    SC 2.4.2: Page Titled
    """
    driver = prepare_driver(url)
    page_title_dict = extract_page_title(driver)
    detection_result = detect_title_violation(page_title_dict)
    driver.quit()
    return detection_result


def check_link_purpose_a(url: str):
    """
    SC 2.4.4: Link Purpose (In Context)
    """
    driver = prepare_driver(url)
    link_related_elements = extract_links(driver)
    detection_result = detect_link_purpose_violation_a(link_related_elements)
    driver.quit()
    return detection_result


def check_multiple_ways(url: str):
    """
    SC 2.4.5: Multiple Ways
    """
    driver = prepare_driver(url)
    multiple_ways_screenshots = extract_multiple_ways(driver)
    detection_result = detect_multiple_ways_violation(multiple_ways_screenshots)
    driver.quit()
    return detection_result


def check_heading_label_description(url: str):
    """
    SC 2.4.6: Headings and Labels
    """
    driver = prepare_driver(url)
    form_input_dict = extract_form_input_elements(driver)
    heading_elements = extract_headings_with_siblings(driver)
    detection_result = detect_heading_label_description_violation(form_input_dict, heading_elements)
    driver.quit()
    return detection_result


def check_location(url: str):
    """
    SC 2.4.8: Location
    """
    driver = prepare_driver(url)
    location_related_elements = extract_location_related_information(driver)
    detection_result = detect_location_violation(location_related_elements)
    driver.quit()
    return detection_result


def check_link_purpose_aaa(url: str):
    """
    SC 2.4.9: Link Purpose (Link Only)
    """
    driver = prepare_driver(url)
    link_related_elements = extract_links(driver)
    detection_result = detect_link_purpose_violation_aaa(link_related_elements)
    driver.quit()
    return detection_result


def check_section_headings(url: str):
    """
    SC 2.4.10: Section Headings
    """
    driver = prepare_driver(url)
    heading_under_section_elements = extract_headings_under_sections(driver)
    detection_result = detect_section_heading_violation(heading_under_section_elements)
    driver.quit()
    return detection_result


def check_label_in_name(url: str):
    """
    SC 2.5.3: Label in Name
    """
    driver = prepare_driver(url)
    elements_with_text_and_aria = extract_label_in_name(driver)
    detection_result = detect_label_in_name_violation(elements_with_text_and_aria)
    driver.quit()
    return detection_result


def check_target_size_enhanced(url: str):
    """
    SC 2.5.5: Target Size (Enhanced)
    """
    driver = prepare_driver(url)
    target_size_elements = extract_target_size(driver)
    detection_result = detect_target_size_enhanced_violation(target_size_elements)
    driver.quit()
    return detection_result


def check_target_size_minimum(url: str):
    """
    SC 2.5.8: Target Size (Minimum)
    """
    driver = prepare_driver(url)
    target_size_elements = extract_target_size(driver)
    detection_result = detect_target_size_minimum_violation(target_size_elements)
    driver.quit()
    return detection_result


def check_language_of_page(url: str):
    """
    SC 3.1.1: Language of Page & SC 3.1.2: Language of Parts
    """
    driver = prepare_driver(url)
    lang_attr_dict = extract_lang_attr(driver)
    # Reuse in page title
    page_title_dict = extract_page_title(driver)
    detection_result = detect_lang_violation(page_title_dict, lang_attr_dict)
    driver.quit()
    return detection_result


def check_abbreviations(url: str):
    """
    SC 3.1.4: Abbreviations
    """
    driver = prepare_driver(url)
    # Call this after text resizing
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    detection_result = detect_abbreviations_violation(initial_screenshot_str)
    driver.quit()
    return detection_result


def check_on_input(url: str):
    """
    SC 3.2.2: On Input
    """
    driver = prepare_driver(url)
    special_input_dict, other_input_dict = extract_event_handlers(driver)
    detection_result = detect_on_input_violation(special_input_dict, other_input_dict)
    driver.quit()
    return detection_result


def check_change_on_request(url: str):
    """
    SC 3.2.5: Change on Request
    """
    driver = prepare_driver(url)
    onclick_event, onblur_event = extract_change_on_request_element(driver)
    detection_result = detect_change_on_request_violation(onclick_event, onblur_event)
    driver.quit()
    return detection_result


def check_error_identified(url: str):
    """
    SC 3.3.1: Error Identification
    """
    driver = prepare_driver(url)
    # Call this after text resizing
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    detection_result = detect_error_identified_violation(initial_screenshot_str)
    driver.quit()
    return detection_result


def check_labels_or_instructions(url: str):
    """
    SC 3.3.2: Labels or Instructions
    """
    driver = prepare_driver(url)
    form_elements = extract_form_elements(driver)
    detection_result = detect_missing_label_instruction(form_elements)
    driver.quit()
    return detection_result


def check_error_suggestion(url: str):
    """
    SC 3.3.3: Error Suggestion
    """
    driver = prepare_driver(url)
    # Call this after text resizing
    initial_screenshot_str = find_related_screenshots(driver, TEMP_FILE_FOLDER)
    detection_result = detect_error_suggestion_violation(initial_screenshot_str)
    driver.quit()
    return detection_result


def check_name_role_value(url: str):
    """
    SC 4.1.2: Name, Role, Value
    """
    driver = prepare_driver(url)
    name_role = extract_name_role_elements(driver)
    # Reuse this in Headings and Labels
    form_inputs = extract_form_input_elements(driver)
    detection_result = detect_name_role_value_violation(name_role, form_inputs)
    driver.quit()
    return detection_result


def check_info_relation_and_resize_text_and_others(url: str):
    """
    Combined: SC 1.3.1, 1.4.4, 1.4.10, 3.1.4, 3.3.1, 3.3.3
    """
    driver1 = prepare_driver(url)
    relation_elements = extract_info_relation_elements(driver1)
    screenshot_list = extract_original_screenshot(driver1)
    info_relation_result = aggregate_info_relation_violation_responses(relation_elements, screenshot_list)
    driver1.quit()

    driver2 = prepare_driver(url)
    text_resizing_dict = extract_text_resizing(driver2)
    resize_text_result = detect_text_resizing_violation(text_resizing_dict)
    driver2.quit()

    driver3 = prepare_driver(url)
    text_reflow_dict = extract_text_reflow(driver3)
    reflow_result = detect_reflow_violation(text_reflow_dict)
    driver3.quit()

    driver4 = prepare_driver(url)
    initial_screenshot_str_abbr = find_related_screenshots(driver4, TEMP_FILE_FOLDER)
    abbreviation_result = detect_abbreviations_violation(initial_screenshot_str_abbr)
    driver4.quit()

    driver5 = prepare_driver(url)
    error_identified_result = detect_error_identified_violation(initial_screenshot_str_abbr)
    driver5.quit()

    driver6 = prepare_driver(url)
    error_suggestion_result = detect_error_suggestion_violation(initial_screenshot_str_abbr)
    driver6.quit()

    driver7 = prepare_driver(url)
    text_blocks = extract_text_blocks_with_details(driver7)
    text_block_result = detect_visual_presentation_violation(text_blocks)
    driver7.quit()

    driver8 = prepare_driver(url)
    section_headings = extract_headings_under_sections(driver8)
    if screenshot_list:
        detection_headings_result = detect_section_heading_violation(section_headings, screenshot_list)
    else:
        detection_headings_result = detect_section_heading_violation(section_headings, initial_screenshot_str_abbr)
    driver8.quit()

    return {
        "1.3.1": info_relation_result,
        "1.4.4": resize_text_result,
        "1.4.8": text_block_result,
        "1.4.10": reflow_result,
        "2.4.10": detection_headings_result,
        "3.1.4": abbreviation_result,
        "3.3.1": error_identified_result,
        "3.3.3": error_suggestion_result
    }


def check_purpose_and_label_in_name(url: str):
    """
    Combined: SC 2.5.3
    """
    driver1 = prepare_driver(url)
    label_set = extract_label_in_name(driver1)
    driver1.quit()

    driver2 = prepare_driver(url)
    label_in_name_result = detect_label_in_name_violation(label_set)
    driver2.quit()

    return {
        "2.5.3": label_in_name_result
    }


def check_language_of_page_and_page_title(url: str):
    """
    Combined: SC 3.1.1, 3.1.2 & 2.4.2
    """
    driver1 = prepare_driver(url)
    lang_attr_dict = extract_lang_attr(driver1)
    page_title_dict = extract_page_title(driver1)
    language_result = detect_lang_violation(page_title_dict, lang_attr_dict)
    driver1.quit()

    driver2 = prepare_driver(url)
    page_title_result = detect_title_violation(page_title_dict)
    driver2.quit()

    return {
        "2.4.2": page_title_result,
        "3.1.1": language_result
    }


def check_name_role_value_and_heading_label_description(url: str):
    """
    Combined: SC 4.1.2 & 2.4.6
    """
    driver1 = prepare_driver(url)
    name_role = extract_name_role_elements(driver1)
    form_inputs = extract_form_input_elements(driver1)
    name_role_value_result = detect_name_role_value_violation(name_role, form_inputs)
    driver1.quit()

    driver2 = prepare_driver(url)
    heading_elements = extract_headings_with_siblings(driver2)
    heading_label_description_result = detect_heading_label_description_violation(form_inputs, heading_elements)
    driver2.quit()

    return {
        "2.4.6": heading_label_description_result,
        "4.1.2": name_role_value_result
    }


def run_check_function(check_function, website_url, a11y_result_dict, key):
    result = check_function(website_url)
    if "combined" in key:
        # Special handling for combined checks
        for criterion, criterion_result in result.items():
            a11y_result_dict[criterion] = criterion_result
    else:
        a11y_result_dict[key] = result


def main_process(website_url: str, folder_name: str):
    start_time = time.time()
    with Manager() as manager:
        a11y_results = manager.dict()

        # List of functions to run in parallel
        functions_to_run = [
            (check_non_text_content, website_url, a11y_results, "1.1.1"),
            (check_meaningful_sequence, website_url, a11y_results, "1.3.2"),
            (check_sensory_characteristics, website_url, a11y_results, "1.3.3"),
            (check_orientation, website_url, a11y_results, "1.3.4"),
            (check_input_purpose, website_url, a11y_results, "1.3.5"),
            (check_use_of_color, website_url, a11y_results, "1.4.1"),
            (check_audio_control, website_url, a11y_results, "1.4.2"),
            (check_color_contrast_aa, website_url, a11y_results, "1.4.3"),
            (check_color_contrast_aaa, website_url, a11y_results, "1.4.6"),
            (check_image_of_text, website_url, a11y_results, "1.4.51.4.9"),
            (check_non_text_contrast, website_url, a11y_results, "1.4.11"),
            (check_text_spacing, website_url, a11y_results, "1.4.12"),
            (check_timing_adjustable, website_url, a11y_results, "2.2.1"),
            (check_pause_stop_hide, website_url, a11y_results, "2.2.2"),
            (check_bypass_blocks, website_url, a11y_results, "2.4.1"),
            (check_link_purpose_a, website_url, a11y_results, "2.4.4"),
            (check_multiple_ways, website_url, a11y_results, "2.4.5"),
            (check_location, website_url, a11y_results, "2.4.8"),
            (check_link_purpose_aaa, website_url, a11y_results, "2.4.9"),
            (check_target_size_enhanced, website_url, a11y_results, "2.5.5"),
            (check_target_size_minimum, website_url, a11y_results, "2.5.8"),
            (check_on_input, website_url, a11y_results, "3.2.2"),
            (check_change_on_request, website_url, a11y_results, "3.2.5"),
            (check_labels_or_instructions, website_url, a11y_results, "3.3.2"),
            (check_info_relation_and_resize_text_and_others, website_url, a11y_results, "combined_1.3.1"),
            (check_purpose_and_label_in_name, website_url, a11y_results, "combined_1.3.6"),
            (check_language_of_page_and_page_title, website_url, a11y_results, "combined_3.1.1"),
            (check_name_role_value_and_heading_label_description, website_url, a11y_results, "combined_4.1.2")
        ]

        # Create and start processes
        processes = []
        for func, website_url, a11y_result_dict, key in functions_to_run:
            p = Process(target=run_check_function, args=(func, website_url, a11y_result_dict, key))
            processes.append(p)
            p.start()

        # Join processes (wait for all processes to finish)
        for p in processes:
            p.join()

        # Convert results to a regular dictionary and print
        final_results = dict(a11y_results)

        # Create the folder if it doesn't exist
        os.makedirs(folder_name, exist_ok=True)

        # Save the JSON files for criteria that have 'overall_violation' as 'Yes'
        for key, result in final_results.items():
            try:
                result = json.loads(result)
                if result:
                    file_path = os.path.join(folder_name, f"{key}.json")
                    # Save the result as a JSON file
                    with open(file_path, 'w') as f:
                        json.dump(result, f, indent=2)
            except Exception as e:
                print(f"Error saving the JSON file for {key}: {e}")
                file_path_txt = os.path.join(folder_name, f"{key}.txt")
                with open(file_path_txt, 'w') as f:
                    f.write(str(result))

        # Record the end time and calculate total time consumed
        end_time = time.time()
        total_time_seconds = end_time - start_time

        # Save the time consumed in a JSON file
        time_file_path = os.path.join(folder_name, "Time Consumed.json")
        with open(time_file_path, 'w') as f:
            json.dump({"time_consumed_seconds": total_time_seconds}, f, indent=4)


if __name__ == "__main__":
    # Set up the logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    # website_data = extract_data_from_excel("Real Website URLS.xlsx", 2, 5)
    # for url, folder_name in website_data:
    #     logger.info('The current URL is: ' + url + ':')
    #     delete_all_files_in_folder(TEMP_FILE_FOLDER)
    #     main_process(url, folder_name)
    # Create the Variability folder if it doesn't exist
    VARIABILITY_FOLDER = "Variability"
    if not os.path.exists(VARIABILITY_FOLDER):
        os.makedirs(VARIABILITY_FOLDER)

    website_data = extract_data_from_excel("Real Website URLS.xlsx", 0, 5)

    for url, folder_name in website_data:
        logger.info(f'The current URL is: {url}')

        # Create the folder for the current website under the Variability folder
        current_folder_path = os.path.join(VARIABILITY_FOLDER, folder_name)
        if not os.path.exists(current_folder_path):
            os.makedirs(current_folder_path)

        # Run the process 3 times for each URL
        for run_number in range(1, 4):
            logger.info(f'Run {run_number} for URL: {url}')

            # Create a subfolder for this run
            run_folder = os.path.join(current_folder_path, f'Run_{run_number}')
            if not os.path.exists(run_folder):
                os.makedirs(run_folder)

            # Clear the temporary file folder
            delete_all_files_in_folder(TEMP_FILE_FOLDER)

            # Execute the main process
            main_process(url, run_folder)
