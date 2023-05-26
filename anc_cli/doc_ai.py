#google-cloud-documentai-2.15.0
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
from typing import List, Sequence
from pathlib import Path 
import spacy 
from spaczz.matcher import FuzzyMatcher

PROJECT_ID = "894403265340"
LOCATION = "us"  # Format is 'us' or 'eu'

PROCESSOR_ID = "ab6bfed15ce9abda"  # Create processor in Cloud Console
MIME_TYPE = "application/pdf"

def get_table_data(
    rows: Sequence[documentai.Document.Page.Table.TableRow], text: str
) -> List[List[str]]:
    """
    Get Text data from table rows
    """
    all_values: List[List[str]] = []
    for row in rows:
        current_row_values: List[str] = []
        for cell in row.cells:
            current_row_values.append(
                text_anchor_to_text(cell.layout.text_anchor, text)
            )
        all_values.append(current_row_values)
    return all_values

def text_anchor_to_text(text_anchor: documentai.Document.TextAnchor, text: str) -> str:
    """
    Document AI identifies table data by their offsets in the entirity of the
    document's text. This function converts offsets to a string.
    """
    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        response += text[start_index:end_index]
    return response.strip().replace("\n", " ")

def pdf_to_data(file_path: str) -> List[List[str]]:
    docai_client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(
                api_endpoint=f"{LOCATION}-documentai.googleapis.com"
            )
        )

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    resource_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    # Read the file into memory
    file_content = Path(file_path).read_bytes()

    # Load Binary Data into Document AI RawDocument Object
    raw_document = documentai.RawDocument(content=file_content, mime_type=MIME_TYPE)

    # Configure the process request
    request = documentai.ProcessRequest(name=resource_name, raw_document=raw_document)

    # Use the Document AI client to process the sample form
    result = docai_client.process_document(request=request)

    document = result.document
    data = {}
    data['file'] = file_path
    data['text'] = document.text
    data['items'] = []
    for page in document.pages:
        for table in page.tables:
            row = get_table_data(table.body_rows, document.text)
            data['items'].append(row)
    return data

# Flatten list using a recursive function
def flatten(lst):
    flattened = []
    for i in lst:
        if isinstance(i, list):
            flattened.extend(flatten(i))
        else:
            flattened.append(i)
    return flattened

def process_data(data: List[dict], terms:list, match_ratio:int, term_matcher, place_matcher,language:str) -> List[dict]:
    nlp = spacy.blank("es")
    result = []
    for i, page in enumerate(data):
        f = page['file']
        data = {}
        data['file'] = str(f)
        for term in terms:
            data[term] = []
        items = flatten(page['items'])
        for ix, item in enumerate(items):
            doc = nlp(item)
            matches = term_matcher(doc)
            term_match = [match_id for match_id, start, end, ratio in matches if ratio > match_ratio]
            try:
                doc = nlp(items[ix +1 ])
                matches = place_matcher(doc)
                place_match = [match_id for match_id, start, end, ratio in matches if ratio > match_ratio]
                data[term_match[0].lower()].append(place_match[0].split('_')[1])
                #print(term_match[0],'==', place_match[0])
            except IndexError:
                pass
        for term in terms:
            data[term] = list(set(data[term]))
        result.append(data)
    print(result)
    return result