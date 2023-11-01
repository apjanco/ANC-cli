import base64
from googleapiclient.discovery import build
from pathlib import Path
from PIL.PpmImagePlugin import PpmImageFile
import srsly 
from pdf2image import convert_from_path
#https://geonames.nga.mil/geonames/GNSData/


type_ =  'DOCUMENT_TEXT_DETECTION' #@param ['TEXT_DETECTION', "DOCUMENT_TEXT_DETECTION", "LABEL_DETECTION", "IMAGE_PROPERTIES", "OBJECT_LOCALIZATION", "WEB_DETECTION" ] {type:"string"}
APIKEY="" 

def lines_from_paragraphs(response:dict):
    lines = []
    blocks  = response['responses'][0]['fullTextAnnotation']['pages'][0]['blocks']
    for block in blocks:
        paragraphs = block['paragraphs']
        for paragraph in paragraphs:
            paragraph_text = ""
            for word in paragraph['words']:
                w = ""
                for symbol in word['symbols']:
                    w += symbol['text']
                paragraph_text += w + ' '
                
            lines.append({'text':paragraph_text, 'bbox':paragraph['boundingBox']})
    return lines

def find_next_word(lines:list, text:str):
    try:
        start = [t for t in lines if text.lower() in t['text'].lower()][0]
        # find the word after the start word using the x and y coordinates of the bounding box
        next = [t for t in lines if t['bbox']['vertices'][0]['x'] > start['bbox']['vertices'][0]['x'] and t['bbox']['vertices'][0]['y'] > start['bbox']['vertices'][0]['y']][0]
        return next
    except:
        return None

def vision(file: str):
    image = Path(file).read_bytes()
    image_content = base64.b64encode(image)
    vservice = build('vision', 'v1', developerKey=APIKEY)
    language = 'es'
    request = vservice.images().annotate(body={
             'requests': [{
                           'image': {
                                     'content': image_content.decode('UTF-8')
                                    },
                           'imageContext': {
                                     'languageHints': [language]},
                                      'features': [{
                           'type': type_
                                        }]
                                      }]
                    })
    return request.execute(num_retries=3)

def pdf_to_img(pdf:str):
    output = []
    images = convert_from_path(pdf)
    filename = Path(pdf).stem
    for i, image in enumerate(images):
        image.save(f'{filename}_{i}.jpg')
        output.append(f'{filename}_{i}.jpg')
    return output 

for jpg in Path().cwd().glob('*.pdf'):
    data = []
    images = pdf_to_img(str(jpg))
    for image in images:
        row = {}
        response = vision(image)
        lines = lines_from_paragraphs(response)
        municipio = find_next_word(lines, 'municip')
        if municipio:
            row['municipio'] = municipio['text']
        depintcom = find_next_word(lines, 'dep.int')
        if depintcom:
            row['depintcom'] = depintcom['text']
        departamento = find_next_word(lines, 'departamen')
        if departamento:
            row['departamento'] = departamento['text']
        data.append(row) 
    srsly.write_json(jpg.stem + '.json', data)