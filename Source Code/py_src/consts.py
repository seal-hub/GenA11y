import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_FILE_FOLDER = os.path.join(BASE_DIR, "TEMP_IMAGES")
JSON_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "accessibility_violation_report",
        "description": "Report of accessibility violations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "overall_violation": {
                    "type": "string",
                    "description": "Indicates whether there is an overall violation",
                    "enum": ["Yes", "No"]
                },
                "violated_elements_and_reasons": {
                    "type": "array",
                    "description": "List of elements that violated accessibility criteria and the reasons",
                    "items": {
                        "type": "object",
                        "properties": {
                            "element": {
                                "type": "string",
                                "description": "OuterHTML of the violated element"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Explanation of why it violates the criterion and the criterion number"
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "Recommendation to fix the violation for this specific element"
                            }
                        },
                        "required": ["element", "reason", "recommendation"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["overall_violation", "violated_elements_and_reasons"],
            "additionalProperties": False
        }
    }
}

ABLATION_JSON_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "accessibility_violation_report",
        "description": "Report of accessibility violations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "violated_success_criteria": {
                    "type": "array",
                    "description": "List of success criteria that were violated",
                    "items": {
                        "type": "object",
                        "properties": {
                            "criterion": {
                                "type": "string",
                                "description": "The specific success criterion that was violated"
                            },
                            "violated_elements_and_reasons": {
                                "type": "array",
                                "description": "List of elements that violated the success criterion and the reasons",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "element": {
                                            "type": "string",
                                            "description": "OuterHTML of the violated element"
                                        },
                                        "reason": {
                                            "type": "string",
                                            "description": "Explanation of why it violates the criterion"
                                        },
                                        "recommendation": {
                                            "type": "string",
                                            "description": "Recommendation to fix the violation for this specific element"
                                        }
                                    },
                                    "required": ["element", "reason", "recommendation"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["criterion", "violated_elements_and_reasons"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["violated_success_criteria"],
            "additionalProperties": False
        }
    }
}

