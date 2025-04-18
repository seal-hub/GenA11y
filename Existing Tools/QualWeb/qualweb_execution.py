import glob
import re
import subprocess
import json
import os
import pandas as pd

def run_qualweb_command(url, report_type):
    command = f'qw -u {url} -r {report_type}'
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    print("Command Output:")
    print(result.stdout)

def extract_wcag_failures(json_data):
    wcag_failures = []
    for item in json_data['@graph']:
        if 'assertions' in item:
            for assertion in item['assertions']:
                test = assertion['test']
                result = assertion['result']
                if 'isPartOf' in test and result['outcome'] == 'earl:failed' and test['isPartOf']:
                    wcag_failures.append({
                        'title': test['title'],
                        'description': test['description'],
                        'wcag_criteria': test['isPartOf'],
                        'pointer': result['source'][0]['result']['pointer'] if 'source' in result and result['source'] else 'N/A',
                        'outcome': result['outcome']
                    })
    return wcag_failures

def read_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def find_first_json_file(directory):
    json_files = glob.glob(os.path.join(directory, "*.json"))
    if json_files:
        return json_files[0]
    else:
        raise FileNotFoundError("No JSON file found in the directory")

def sanitize_folder_name(name):
    return re.sub(r'[^A-Za-z0-9]+', '_', name)

def delete_all_json_files(directory):
    json_files = glob.glob(os.path.join(directory, "*.json"))
    for json_file in json_files:
        os.remove(json_file)
    print(f"Deleted {len(json_files)} JSON files from {directory}")

def main():
    # Read URLs and WCAG criteria from Excel file in the previous folder, place your test case file here
    excel_path = os.path.join(os.path.dirname(__file__), '../Test Cases.xlsx')
    df = pd.read_excel(excel_path)
    
    scan_data = df[['URL', 'WCAG Criterion']].dropna().to_dict('records')
    
    for data in scan_data:
        scan_url = data['URL']
        wcag_criterion = data['WCAG Criterion']
        report_type = 'earl'
    
        # Run the QualWeb command
        run_qualweb_command(scan_url, report_type)
    
        # Find the first JSON file in the current directory
        json_file_path = find_first_json_file(os.getcwd())
    
        # Read the JSON file
        json_data = read_json_file(json_file_path)
    
        # Extract WCAG failures
        wcag_failures = extract_wcag_failures(json_data)
    
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
    
        # Determine the output file name
        domain_name = scan_url.split('/')[-1]
        output_file_name = f"{domain_name}_QualWeb_Result.json"
    
        # Save the filtered failures to a new JSON file in the corresponding subfolder
        output_file_path = os.path.join(criterion_dir, output_file_name)
        with open(output_file_path, 'w') as output_file:
            json.dump(wcag_failures, output_file, indent=4)
    
        # Delete all JSON files in the current directory
        delete_all_json_files(os.getcwd())


if __name__ == '__main__':
    main()