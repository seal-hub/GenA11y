import requests
import os
import json
import pandas as pd
import re

def send_request_to_wave(api_key: str, scan_url: str):
    # Constructing the request URL
    request_url = f"http://wave.webaim.org/api/request?key={api_key}&url={scan_url}&reporttype=4"

    # Sending the GET request
    response = requests.get(request_url)

    if response.status_code == 200:
        response_data = response.json()

        # Extracting only error and contrast categories
        filtered_data = {
            "error": response_data.get("categories", {}).get("error", {}),
            "contrast": response_data.get("categories", {}).get("contrast", {})
        }

        # Sending requests for each ID and appending guideline names to filtered_data
        for category_name, category_data in filtered_data.items():
            items = category_data.get('items', {})
            if isinstance(items, dict):
                for item_key, item in items.items():
                    doc_request_url = f"https://wave.webaim.org/api/docs?id={item['id']}"
                    doc_response = requests.get(doc_request_url)
                    if doc_response.status_code == 200:
                        doc_data = doc_response.json()

                        # Extracting the name under guidelines and appending it to the item
                        guideline_names = [guideline.get("name", "") for guideline in doc_data.get("guidelines", [])]
                        item["guideline_names"] = guideline_names
                    else:
                        print(f"Failed to retrieve documentation for ID: {item['id']}. Status Code:",
                              doc_response.status_code)

        return filtered_data
    else:
        print("Failed to retrieve data for URL:", scan_url, "Status Code:", response.status_code)
        print("Response Body:", response.text)
        return None

def sanitize_folder_name(name):
    return re.sub(r'[^A-Za-z0-9]+', '_', name)

def main():
    # Read URLs and WCAG criteria from Excel file in the previous folder, place your test case file here
    excel_path = os.path.join(os.path.dirname(__file__), '../Test Cases.xlsx')
    df = pd.read_excel(excel_path)
    
    scan_data = df[['URL', 'WCAG Criterion']].dropna().to_dict('records')
    
    # Your API key
    api_key = "Your API Key"
    
    for idx, data in enumerate(scan_data):
        scan_url = data['URL']
        wcag_criterion = data['WCAG Criterion']
    
        print(f"Processing URL {idx + 1}/{len(scan_data)}: {scan_url}")
    
        # Run the WAVE API command and get the errors and contrast issues
        filtered_data = send_request_to_wave(api_key, scan_url)
    
        if filtered_data:
            # Sanitize the WCAG criterion for folder creation
            sanitized_criterion = sanitize_folder_name(wcag_criterion)
    
            # Ensure the 'results' folder exists
            results_dir = os.path.join(os.path.dirname(__file__), 'results')
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
    
            # Ensure the subfolder for the WCAG criterion exists
            criterion_dir = os.path.join(results_dir, sanitized_criterion)
            if not os.path.exists(criterion_dir):
                os.makedirs(criterion_dir)
    
            # Extracting the domain name to use as part of the file name
            domain_name = scan_url.split('/')[-2] if scan_url.endswith('/') else scan_url.split('/')[-1]
            output_file_name = f"{domain_name}_WaveAPI_Result.json"
    
            # Save the filtered data to a new JSON file in the corresponding subfolder
            output_file_path = os.path.join(criterion_dir, output_file_name)
            with open(output_file_path, 'w') as file:
                json.dump(filtered_data, file, indent=4)
    
            print(f"Response data saved to {output_file_path}")


if __name__ == '__main__':
    main()