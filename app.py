import csv
import io
import json
import os
import re

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv()


def get_setting(name, default=None):
    value = os.getenv(name)
    if value is not None:
        return value
    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default


nvidia_api_key = get_setting("NVIDIA_API_KEY")
gemini_api_key = get_setting("GEMINI_API_KEY")
GEMINI_MODEL = get_setting("GEMINI_MODEL", "gemini-3.8-flash")
NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

DEFAULT_FIELDS = "title, description, price, url, category, features"
SAMPLE_COPY = """Northstar Insulated Travel Mug
Description: A double-wall stainless steel mug designed for daily commutes and weekend trips.
Price: $28.00
URL: https://example.com/products/northstar-mug
Category: Drinkware
Features:
- Keeps drinks hot for 6 hours or cold for 12 hours
- Leak-resistant flip lid
- Made with 80% recycled stainless steel
"""

st.set_page_config(page_title="Copy to API", page_icon="{ }", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    :root {
        --ink: #18211f;
        --muted: #687570;
        --paper: #f4f5ef;
        --panel: #ffffff;
        --line: #dce2d8;
        --accent: #d84c2f;
        --green: #236b55;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: #e9eee5; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] > div { padding-top: 1.6rem; }
    .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
    .eyebrow { color: var(--accent); font: 600 0.76rem 'IBM Plex Mono', monospace; letter-spacing: 0.08em; text-transform: uppercase; }
    h1 { font-size: 2.65rem !important; line-height: 1.08 !important; letter-spacing: 0 !important; margin: 0.4rem 0 0.55rem !important; }
    h2, h3 { letter-spacing: 0 !important; }
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { background: #fff; border-color: var(--line); border-radius: 5px; }
    [data-testid="stTextArea"] textarea { font-family: 'IBM Plex Mono', monospace; font-size: 0.88rem; line-height: 1.55; }
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button { border-radius: 4px; font-weight: 600; }
    [data-testid="stFormSubmitButton"] > button { background: var(--accent); color: #fff; border: 1px solid var(--accent); min-height: 2.8rem; }
    [data-testid="stFormSubmitButton"] > button:hover { background: #b93d25; border-color: #b93d25; color: white; }
    [data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); padding: 0.85rem 1rem; border-radius: 5px; }
    [data-testid="stCode"] pre { border: 1px solid var(--line); border-radius: 5px; }
    div[data-baseweb="tab-list"] { gap: 0.6rem; }
    button[data-baseweb="tab"] { border-radius: 3px 3px 0 0; }
    hr { border-color: var(--line); }
    @media (max-width: 768px) {
        h1 { font-size: 2rem !important; }
        .block-container { padding: 1.3rem 1rem 3rem; }
        [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 0.5rem !important; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
        }
        [data-testid="stFormSubmitButton"] > button { width: 100%; }
        [data-testid="stCode"] pre { max-width: 100%; overflow-x: auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def parse_fields(raw_fields):
    fields = []
    for item in raw_fields.split(","):
        field = re.sub(r"[^a-zA-Z0-9_ -]", "", item).strip().replace(" ", "_")
        if field and field not in fields:
            fields.append(field)
    return fields or DEFAULT_FIELDS.split(", ")


def normalize_label(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def match_field(label, fields):
    aliases = {
        "title": {"title", "name", "productname", "headline"},
        "description": {"description", "summary", "overview", "details"},
        "price": {"price", "cost", "amount"},
        "url": {"url", "link", "webaddress"},
        "category": {"category", "type", "department"},
        "features": {"feature", "features", "highlights", "benefits"},
    }
    label_key = normalize_label(label)
    for field in fields:
        field_key = normalize_label(field)
        if label_key == field_key or label_key in aliases.get(field_key, set()):
            return field
    return None


def extract_locally(text, fields):
    records = []
    for block in re.split(r"\n\s*\n+", text.strip()):
        if not block.strip():
            continue
        record = {field: None for field in fields}
        unlabelled = []
        active_features = None
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            bullet = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)$", line)
            if bullet and "features" in fields:
                if record["features"] is None:
                    record["features"] = []
                if isinstance(record["features"], list):
                    record["features"].append(bullet.group(1).strip())
                active_features = "features"
                continue
            labelled = re.match(r"^([A-Za-z][A-Za-z0-9 _/-]{0,39})\s*:\s*(.*)$", line)
            if labelled:
                field = match_field(labelled.group(1).strip(), fields)
                active_features = None
                if field:
                    value = labelled.group(2).strip()
                    if field == "features" and value:
                        record[field] = [value]
                        active_features = field
                    elif value:
                        record[field] = value
                else:
                    unlabelled.append(line)
                continue
            if active_features and record.get(active_features) is not None:
                record[active_features].append(line)
            else:
                unlabelled.append(line)
        if "title" in fields and record["title"] is None and unlabelled:
            record["title"] = unlabelled.pop(0).strip(" -*#")
        if "description" in fields and unlabelled:
            record["description"] = " ".join(unlabelled)
        if any(value is not None for value in record.values()):
            records.append(record)
    return records


def parse_records(response_text, fields):
    response_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip())
    data = json.loads(response_text)
    if isinstance(data, dict):
        data = data.get("records", [data])
    if not isinstance(data, list):
        raise ValueError("The model response was not a JSON array.")
    return [
        {field: item.get(field) for field in fields}
        for item in data
        if isinstance(item, dict)
    ]


def make_extraction_prompt(text, fields):
    return (
        "Convert the supplied web copy into clean structured records. Return only a JSON array "
        "of objects, using exactly these keys in every object: "
        f"{json.dumps(fields)}. Extract every distinct item you can identify. "
        "Use null for missing values, preserve feature lists as arrays, and do not invent facts.\n\n"
        "WEB COPY:\n"
        f"{text}"
    )


def extract_with_gemini(text, fields):
    prompt = make_extraction_prompt(text, fields)
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        params={"key": gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=60,
    )
    response.raise_for_status()
    response_body = response.json()
    response_text = response_body["candidates"][0]["content"]["parts"][0]["text"]
    return parse_records(response_text, fields)


def extract_with_nvidia(text, fields):
    with requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {nvidia_api_key}"},
        json={
            "model": NVIDIA_MODEL,
            "messages": [{"role": "user", "content": make_extraction_prompt(text, fields)}],
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=60,
        stream=True,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            payload = line.partition(":")[2].strip()
            if payload == "[DONE]":
                break
            event = json.loads(payload)
            for choice in event.get("choices", []):
                content = choice.get("delta", {}).get("content")
                if isinstance(content, str) and content:
                    yield content


def make_csv(records, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                field: json.dumps(record.get(field), ensure_ascii=False)
                if isinstance(record.get(field), (list, dict))
                else record.get(field)
                for field in fields
            }
        )
    return output.getvalue()


st.markdown('<div class="eyebrow">Web copy / structured output</div>', unsafe_allow_html=True)
st.title("Raw copy in. Clean records out.")
st.markdown("Turn pasted web content into consistent, API-ready JSON or CSV.")
st.divider()

with st.sidebar:
    st.markdown("### Output schema")
    raw_fields = st.text_input(
        "Fields, comma-separated",
        value=DEFAULT_FIELDS,
        help="These become the keys in every JSON record and the columns in your CSV.",
    )
    fields = parse_fields(raw_fields)
    st.caption(f"{len(fields)} fields: " + " / ".join(fields))
    st.divider()
    st.markdown("### Extraction provider")
    selected_provider = st.selectbox(
        "Provider",
        ["Automatic", "NVIDIA NIM", "Gemini", "Local"],
    )
    if selected_provider == "Automatic":
        extraction_provider = "Gemini" if gemini_api_key else "NVIDIA NIM" if nvidia_api_key else "Local"
    else:
        extraction_provider = selected_provider
    if extraction_provider == "NVIDIA NIM":
        if nvidia_api_key:
            st.success("NVIDIA NIM extraction is ready", icon="✅")
        else:
            st.warning("Set NVIDIA_API_KEY in .env, then restart the app.")
    elif extraction_provider == "Gemini":
        if gemini_api_key:
            st.success("Gemini extraction is ready", icon="✅")
            st.caption("Semantic extraction is enabled for messy or unlabelled copy.")
        else:
            st.warning("Set GEMINI_API_KEY in .env, then restart the app.")
    else:
        st.info("Local extraction is active")
        st.caption("Local mode recognizes labelled lines and bullet lists.")

if st.button("Load example copy"):
    st.session_state["source_copy"] = SAMPLE_COPY

with st.form("extract_form"):
    source_copy = st.text_area(
        "Paste web copy",
        key="source_copy",
        height=270,
        placeholder="Paste a product page, listing, article excerpt, or other web copy here...",
    )
    submitted = st.form_submit_button("Convert to records", use_container_width=True)

if submitted:
    if not source_copy.strip():
        st.warning("Paste some web copy first.")
    elif extraction_provider == "NVIDIA NIM" and not nvidia_api_key:
        st.error("NVIDIA_API_KEY is missing. Add it to .env and restart the app.")
    elif extraction_provider == "Gemini" and not gemini_api_key:
        st.error("GEMINI_API_KEY is missing. Add it to .env and restart the app.")
    else:
        try:
            if extraction_provider == "NVIDIA NIM":
                with st.status("Generating records with NVIDIA NIM...", expanded=True) as status:
                    response_text = st.write_stream(extract_with_nvidia(source_copy, fields))
                    status.update(label="NVIDIA NIM response received", state="complete", expanded=False)
                records = parse_records(response_text, fields)
                extraction_method = "NVIDIA NIM extraction"
            elif extraction_provider == "Gemini":
                records = extract_with_gemini(source_copy, fields)
                extraction_method = "Gemini semantic extraction"
            else:
                records = extract_locally(source_copy, fields)
                extraction_method = "Local labelled-text extraction"
            st.session_state["records"] = records
            st.session_state["extraction_method"] = extraction_method
            st.session_state["record_fields"] = fields
        except requests.RequestException as error:
            error_response = getattr(error, "response", None)
            status = getattr(error_response, "status_code", None)
            api_message = None
            if error_response is not None:
                try:
                    error_body = error_response.json()
                    if isinstance(error_body, dict):
                        error_info = error_body.get("error", error_body)
                        if isinstance(error_info, dict):
                            api_message = error_info.get("message") or error_info.get("detail")
                        elif isinstance(error_info, str):
                            api_message = error_info
                except (AttributeError, ValueError):
                    pass
            detail = f" (HTTP {status}: {api_message})" if status and api_message else f" (HTTP {status})" if status else ""
            st.error(f"{extraction_provider} could not process this copy{detail}. Check the API key, model access, and network connection.")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            st.error("The response could not be read as structured JSON. Try again or simplify the source copy.")

records = st.session_state.get("records")
result_fields = st.session_state.get("record_fields", fields)
if records is not None:
    st.divider()
    st.markdown("### Structured output")
    metric_records, metric_fields, metric_method = st.columns([1, 1, 2])
    metric_records.metric("Records", len(records))
    metric_fields.metric("Fields", len(result_fields))
    metric_method.caption("EXTRACTION MODE")
    metric_method.markdown(f"**{st.session_state.get('extraction_method', 'Ready')}**")

    json_output = json.dumps(records, indent=2, ensure_ascii=False)
    csv_output = make_csv(records, result_fields)
    download_json, download_csv, _ = st.columns([1, 1, 3])
    download_json.download_button(
        "Download JSON",
        data=json_output,
        file_name="clean_records.json",
        mime="application/json",
        use_container_width=True,
    )
    download_csv.download_button(
        "Download CSV",
        data=csv_output,
        file_name="clean_records.csv",
        mime="text/csv",
        use_container_width=True,
    )
    json_tab, csv_tab = st.tabs(["JSON preview", "CSV preview"])
    with json_tab:
        st.code(json_output, language="json")
    with csv_tab:
        st.code(csv_output, language="csv")