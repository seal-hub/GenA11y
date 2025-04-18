## Ablation Experiment

- **Other than GenA11y**, we have three models for our ablation experiment:

  1. **Base Model**: Utilizes the latest version of GPT-4O and is provided with the HTML of a website to detect accessibility violations.
  2. **Extraction-Only Model**: Incorporates the extraction component. The extracted elements are fed to the GPT-4O model with only basic prompting, instructing it to detect accessibility violations for these elements.
  3. **Prompting-Only Model**: Includes detailed prompting as discussed in Section 4.2 of the paper, but the input remains the raw HTML of a website.

  **Experiment Details**:
  The experiment was conducted on the Accessibility Tool Audit Dataset.

  **Important Note**:
  Ensure that your own `OPENAI_API_KEY` is placed inside the `A11yDetector` folder.
