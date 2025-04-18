import json
import re
import requests
from transformers import GPT2Tokenizer

# Initialize the tokenizer
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")


def count_tokens(message: str) -> int:
    # Use the tokenizer to count the number of tokens
    tokens = tokenizer.encode(message, add_special_tokens=False)
    return len(tokens)


def chunk_dict(data: dict, chunk_size: int):
    """Chunk a dictionary into smaller dictionaries of a specified size."""
    keys = list(data.keys())
    for i in range(0, len(keys), chunk_size):
        yield {key: data[key] for key in keys[i:i + chunk_size]}


def chunk_list(data: list, chunk_size: int):
    """Chunk a list into smaller lists of a specified size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def chunk_data(data, threshold_tokens: int = 80000, max_chunk_tokens: int = 40000):
    """Chunk the data into smaller parts if it exceeds the threshold number of tokens."""

    # Function to calculate the total number of tokens in the data
    def total_data_tokens(data):
        if isinstance(data, dict):
            return sum(count_tokens(str(key)) + count_tokens(str(value)) for key, value in data.items())
        elif isinstance(data, list):
            return sum(count_tokens(str(item)) for item in data)
        else:
            raise ValueError("Input data should be a dictionary or list.")

    def chunk_by_token_count(data, max_tokens):
        if isinstance(data, dict):
            items = list(data.items())
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("Input data should be a dictionary or list.")

        current_tokens = 0
        current_chunk = {} if isinstance(data, dict) else []
        for item in items:
            if isinstance(data, dict):
                key, value = item
                item_tokens = count_tokens(str(key)) + count_tokens(str(value))
            else:
                item_tokens = count_tokens(str(item))

            if current_tokens + item_tokens > max_tokens:
                yield current_chunk
                current_chunk = {key: value} if isinstance(data, dict) else [item]
                current_tokens = item_tokens
            else:
                if isinstance(data, dict):
                    current_chunk[key] = value
                else:
                    current_chunk.append(item)
                current_tokens += item_tokens
        if current_chunk:
            yield current_chunk

    total_tokens = total_data_tokens(data)

    if total_tokens > threshold_tokens:
        return list(chunk_by_token_count(data, max_chunk_tokens))
    else:
        return [data]


def aggregate_responses(responses):
    """Aggregate multiple JSON responses into a single JSON object."""
    overall_violation = "No"
    violated_elements_and_reasons = []

    for response in responses:
        try:
            response_json = json.loads(response)
            if response_json.get("overall_violation") == "Yes":
                overall_violation = "Yes"
                violated_elements_and_reasons.extend(response_json.get("violated_elements_and_reasons", []))
        except json.JSONDecodeError:
            # If a JSONDecodeError occurs, attempt to correct the format
            corrected_response = correct_json_format(response)
            try:
                response_json = json.loads(corrected_response)
                if response_json.get("overall_violation") == "Yes":
                    overall_violation = "Yes"
                    violated_elements_and_reasons.extend(response_json.get("violated_elements_and_reasons", []))
            except json.JSONDecodeError:
                print("Invalid JSON response after correction:", response)
                continue

    # Construct the final aggregated response
    aggregated_response = {
        "overall_violation": overall_violation,
        "violated_elements_and_reasons": violated_elements_and_reasons
    }
    return aggregated_response


def check_url_status(url):
    """
    Send a request to the given URL and return the status code.
    """
    try:
        response = requests.head(url)
        return response.status_code
    except requests.RequestException as e:
        print(f"Request failed for URL: {url} - Error: {e}")
        return None


def correct_json_format(response):
    """Attempt to correct common JSON format issues."""

    response = re.sub(
        r'(<img [^>]*src="[^">]*)'
        r'(?<!")(\s|>|$)',  # Ensure it's the end of the tag or it's missing a closing quote
        r'\1"',  # Append a closing quote to the src attribute
        response
    )

    # Ensure that the "element" string itself is properly closed with a quote
    response = re.sub(
        r'("element":\s*".*?)(?<!")$',  # Matches "element" fields that are missing a closing quote
        r'\1"',  # Append a closing quote to the "element" field
        response
    )

    # Ensure all HTML tags are closed properly
    response = re.sub(
        r'(<img [^>]*)(?<!>)(\s|$)',  # Find img tags that are not closed
        r'\1>',  # Close the tag
        response
    )

    # Close JSON objects correctly
    # Finds any objects within arrays that do not end with a closing brace before a comma or closing bracket
    response = re.sub(
        r'(\{[^}]*)(?<!\})(,|\])',  # Looks for any object that doesn't end with }
        r'\1}',  # Close the object
        response
    )

    # Close the overall JSON object and array if necessary
    if not response.strip().endswith(']}'):
        response = response.rstrip() + ']}'

    return response
