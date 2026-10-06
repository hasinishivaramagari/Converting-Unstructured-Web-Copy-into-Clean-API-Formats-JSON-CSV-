# WebCopy API Converter

A Streamlit app that turns pasted, unstructured web copy into normalized JSON or CSV. Choose an AI provider for semantic extraction, or use the local parser for labelled text and bullet lists.

## Features

- Paste text into the app and convert it into structured records.
- Choose an output schema by entering comma-separated field names.
- Select NVIDIA NIM, Gemini, Local, or Automatic extraction.
- Stream NVIDIA response text while generation is in progress.
- Preview and download the results as JSON or CSV.

The app accepts pasted text; it does not fetch webpages or import HTML by URL.

## Requirements

- Python 3.11 or another version supported by the packages in `requirements.txt`
- API key for NVIDIA NIM or Gemini if using an AI provider. Local extraction does not require an API key.

## Setup

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux, activate the environment with:

```sh
source .venv/bin/activate
```

## API keys

Create a `.env` file in the project root, next to `app.py`. Add only the provider keys you intend to use:

```dotenv
NVIDIA_API_KEY=your-nvidia-api-key
```

`GEMINI_API_KEY` and `NVIDIA_API_KEY` are optional individually. Keep real keys private; `.env` is excluded from Git. Restart the app after changing `.env` so the new values are loaded.

For Streamlit Community Cloud, deploy `app.py` from this GitHub repository and add any provider keys under the app's **Settings > Secrets** as TOML:

```toml
GEMINI_API_KEY = "your-gemini-api-key"
NVIDIA_API_KEY = "your-nvidia-api-key"
GEMINI_MODEL = "gemini-3.8-flash"
```

Only add the keys for providers you use. The app can also deploy without keys and use Local extraction.

## Run

From the project root, with the virtual environment active:

```sh
streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`.

## Extraction providers

- **Automatic** uses Gemini when `GEMINI_API_KEY` is set; otherwise NVIDIA NIM when `NVIDIA_API_KEY` is set; otherwise Local.
- **Gemini** uses the model set by `GEMINI_MODEL`, defaulting to `gemini-3.8-flash`.
- **NVIDIA NIM** uses `nvidia/nemotron-3.5-lightning-30b-a3b` and streams generated text to the interface.
- **Local** recognizes labelled lines such as `Price: $28` and feature bullet lists. It does not call a hosted model.

The app reports whether a key is configured, but the provider validates it only when a conversion request is sent.

## Output

JSON output is an array of records using the selected fields. CSV output uses the same fields as columns; list and object values are serialized as JSON within their cells.

```json
[
	{
		"title": "Northstar Insulated Travel Mug",
		"price": "$28.00",
		"features": ["Leak-resistant flip lid"]
	}
]
```
