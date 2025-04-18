import json
import os
import time

import pandas as pd
from dotenv import dotenv_values
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from consts import ABLATION_JSON_FORMAT

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '..', '..', 'A11yDetector', '.env')
config = dotenv_values(env_path)
client = OpenAI(api_key=config["OPENAI_API_KEY"])
sys_message = ("Use your knowledge about WCAG to determine if the website has any "
               "accessibility issues."
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
                                                response_format=ABLATION_JSON_FORMAT,
                                                messages=[{"role": "system", "content": sys_message},
                                                    {"role": "user", "content": user_message}
                                                          ],
                                                temperature=0.0)
    return completion


def read_urls_from_excel(file_path, start_index=None, end_index=None):
    """
    Read the list of values from the 'URL' column in an Excel file.
    """
    # Load the Excel file into a DataFrame
    df = pd.read_excel(file_path)

    # Check if 'URL' column exists in the DataFrame
    if 'URL' in df.columns:
        # If start_index or end_index is provided, slice the DataFrame accordingly
        if start_index is not None or end_index is not None:
            df = df.iloc[start_index:end_index+1]

        # Extract the 'URL' column as a list
        url_list = df['URL'].dropna().tolist()
        return url_list
    else:
        raise ValueError("The column 'URL' was not found in the Excel file.")


def check_website_accessibility(url):
    """Check the accessibility of a website using the OpenAI model."""
    driver = prepare_driver(url)
    page_source = driver.page_source
    user_message = (f"You will be provided with the page source of a website. Using the page source and WCAG "
                    f"Guidelines,"
                    f"please identify and report any violations of WCAG criteria."
                    f"The relevant information for your assessment begins after the dashed line."
                    f"---------------------------------"
                    f"Page Source: {page_source}")
    response = send_request_to_model("gpt-4o-2024-08-06", user_message)
    return response.choices[0].message.content


def save_results_to_json(results, index, output_folder):
    """Save the results to a JSON file under the Results folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    file_name = os.path.join(output_folder, f"{index}.json")
    with open(file_name, 'w') as json_file:
        json.dump(results, json_file, indent=8)


