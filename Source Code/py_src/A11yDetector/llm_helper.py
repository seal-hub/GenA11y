import os
from dotenv import dotenv_values
from openai import OpenAI


def detect_sensory_instructions(text):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    config = dotenv_values(env_path)
    client = OpenAI(api_key=config["OPENAI_API_KEY"])
    system_message = {
        "role": "system",
        "content": (
            "You are an accessibility expert. Your task is to identify and extract instructions containing sensory "
            "information such as color, shape, size, position, or orientation that are used to locate an element inside"
            "a webpage, according to WCAG 1.3.3 Sensory Characteristics. Please differentiate color information from "
            "other sensory information. Use the following JSON "
            "structure:\n"
            "{\n"
            "  \"other_sensory_information\": [],\n"
            "  \"color_information\": []\n"
            "}\n"
            "The text for analysis is provided below the line of dashes."
        )
    }
    user_message = {
        "role": "user",
        "content": f"--------------------------------------\nText for analysis: {text}"
    }
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[system_message, user_message],
        temperature=0.0
    )

    return response.choices[0].message.content


