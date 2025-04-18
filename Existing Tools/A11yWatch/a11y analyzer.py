import json
import os
import re
import requests
import pandas as pd


def send_request_to_a11ywatch(website_url):
    url = "https://api.a11ywatch.com/api/scan"
    headers = {
        "Authorization": "Placed your API key here",
        "Content-Type": "application/json"
    }
    data = {
        "url": f"{website_url}"
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        response_data = response.json()
        # Extracting only the issues with type 'error'
        errors = [issue for issue in response_data.get('data', {}).get('issues', []) if issue['type'] == 'error']
        return errors
    else:
        return None


def sanitize_folder_name(name):
    return re.sub(r'[^A-Za-z0-9]+', '_', name)


def main():
    # Read URLs and WCAG criteria from Excel file in the previous folder, place your test case file here
    excel_path = os.path.join(os.path.dirname(__file__), '../Test Cases.xlsx')
    df = pd.read_excel(excel_path)
    scan_data = df[['URL', 'WCAG Criterion']].dropna().to_dict('records')
    
    for data in scan_data:
        scan_url = data['URL']
        print(scan_url)
        wcag_criterion = data['WCAG Criterion']
    
        # Run the A11yWatch command and get the errors
        errors = send_request_to_a11ywatch(scan_url)
    
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
        domain_name = scan_url.split('/')[-1]
        output_file_name = f"{domain_name}_A11yWatch_Result.json"
    
        # Save the errors to a new JSON file in the corresponding subfolder
        output_file_path = os.path.join(criterion_dir, output_file_name)
        with open(output_file_path, 'w') as file:
            json.dump(errors, file, indent=4)
            print(f"Errors saved to {output_file_path}")
    



if __name__ == '__main__':
    main()