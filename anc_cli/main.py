import typer
from pathlib import Path
import pandas as pd 
import srsly
from anc_cli.utils import *
import spacy
from spacy.matcher import Matcher
import yaml
from rich import print

settings = yaml.load(Path('anc_cli/settings.yml').read_text(), Loader=yaml.Loader)
api_key = yaml.load(Path('anc_cli/apikey.yml').read_text(), Loader=yaml.Loader)
api_key = api_key["APIKEY"]

app = typer.Typer()
nlp = spacy.blank(settings['language'])

municipio_names = srsly.read_json('anc_cli/data/municipios.json')
departamentos = srsly.read_json('anc_cli/data/departamentos.json')


place_matcher = Matcher(nlp.vocab)
for municipio in municipio_names:
    pattern = [{"LOWER": {"FUZZY": f"{m}"}} for m in nlp(municipio)]
    place_matcher.add('municipio_'+municipio, [pattern])
for departamento in departamentos:
    pattern = [{"LOWER": {"FUZZY": f"{m}"}} for m in nlp(departamento)]
    place_matcher.add('departamento_'+departamento, [pattern])

terms = settings['terms']

language = settings['language']
output_dir = Path('anc_cli/output')
if not output_dir.exists():
    output_dir.mkdir(parents=True, exist_ok=True)
existing_data = [f.stem for f in output_dir.iterdir()]

@app.command()
def process(pdf_directory:str, force: bool = typer.Option(False, "--force", help='Ignore existing data and create new.')):
    pdf_directory = Path(pdf_directory)
    if pdf_directory.exists():
        print(f"[green] Processing {len(list(pdf_directory.iterdir()))} file [/green]")

        data = []
        for i, file_ in enumerate(pdf_directory.iterdir()):
            if file_.suffix == '.pdf' and file_.stem not in existing_data:
                json_response = pdf_to_data(file_, language, api_key)
                out_path = str((output_dir / f"{file_.stem}_{i}.json"))
                srsly.write_json(out_path, json_response)
                data.extend(json_response)
            elif file_.suffix == '.pdf' and file_.stem not in existing_data and force:
                typer.echo(f"Processing {len(data)} pages")


        doc_w_term = []
        doc_places = {}
        output = []
        if data:
            for index, page in enumerate(data):
                typer.echo(f"Processing page {index + 1}")
                for response in page['responses']:
                    for i, annotation in enumerate(response['textAnnotations']):
                        if i == 0:
                            # Process full text of document, identify pages that contain relevant terms
                            full_text = annotation.get('description', None)
                            doc = nlp(full_text)
                            term_matcher = Matcher(nlp.vocab)
                            for term in terms:
                                pattern = [{"LOWER": {"FUZZY": f"{m}"}} for m in nlp(term)]
                                term_matcher.add(term, [pattern])

                            matches = term_matcher(doc)
                            terms_found = [match_id for match_id, start, end in matches]
                    
                        if terms_found:
                            doc_w_term.append(i)
                            matches = place_matcher(doc)
                            spans = [doc[start:end] for match_id, start, end in matches]
                            match_ids = [match_id for match_id, start, end in matches]
                            doc_places[i] = [dict(index=i,start=span.start_char, end=span.end_char, text=span.text, match_id=match_id) for span, match_id in zip(spacy.util.filter_spans(spans), match_ids)]
                        
                    
            if doc_w_term: 
                for i, d in enumerate(data):
                    if i in doc_w_term:
                        for term in terms:
                            #For a given term, find the results located just to the right in a given area. 
                            # Allow Levenstein distance of 2 to account for OCR errors
                            results = get_data(d, term, 2)
                            for result in results:  
                                match_term = result['key'] #ex. DEPARTAMENTO
                                doc = nlp(result['value']) 
                                token_matches = place_matcher(doc)
                                doc = nlp(f"{result['prior_word']} {result['value']} {result['next_word']}")
                                span_matches = place_matcher(doc)
                                for token_match, span_match in zip(token_matches, span_matches):
                                    
                                    #ex. has span ('departamento_cauca', 0, 1, 100) ('departamento_valle del cauca', 0, 2, 75)
                                    #ex. not span ('municipio_barranquilla', 0, 1, 100) ('departamento_atlántico', 0, 1, 89)
                                    string_id = nlp.vocab.strings[token_match[0]]
                                    token_term = string_id.split("_")[0]

                                    string_id = nlp.vocab.strings[span_match[0]]
                                    span_term = string_id.split("_")[0]
                                    m = {}
                                    if span_term == token_term:
                                        m['match_term'] = span_term.title()
                                        string_id = nlp.vocab.strings[span_match[0]]
                                        m['match_name'] = string_id.split("_")[1].title().replace('Del','del')
                                    else:
                                        m['match_term'] = token_term.title()
                                        string_id = nlp.vocab.strings[token_match[0]]
                                        m['match_name'] = string_id.split("_")[1].title().replace('Del','del')
                                m['filename'] = result["filename"]
                                m['page'] = result["page"]
                                output.append(m)
                                
            if output:
                df = pd.DataFrame(output)
                df = df.drop_duplicates()
                print(df)

    else:
        typer.echo("Not a valid path, please check and try again.")
