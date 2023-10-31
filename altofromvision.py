#TODO add escriptorium-connector, Typer cli
# 1 fetch images from local, process and push to eScriptorium
# 2 fetch images/transcriptions from eScriptorium, process and push changes
# 3 ask which they prefer? 
# 4 also need batch export of text from eScriptorium (or already exists? What form is best for them?)

import json
from xml.etree.ElementTree import Element, SubElement, tostring

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
    
def vision_to_alto(filename:str, response:json):
    # Create the ALTO XML document
    alto = Element('alto', {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                            'xmlns': 'http://www.loc.gov/standards/alto/ns-v4#',
                            'xsi:schemaLocation': 'http://www.loc.gov/standards/alto/ns-v4# http://www.loc.gov/standards/alto/v4/alto-4-0.xsd'})

    # Add the Description element
    description = SubElement(alto, 'Description')
    measurement_unit = SubElement(description, 'MeasurementUnit')
    measurement_unit.text = 'pixel'
    source_image_information = SubElement(description, 'sourceImageInformation')
    file_name = SubElement(source_image_information, 'fileName')
    file_name.text = filename

    # Add the Tags element
    tags = SubElement(alto, 'Tags')
    title = SubElement(tags, 'OtherTag', {'ID': 'BT1', 'LABEL': 'Title', 'DESCRIPTION': 'block type Title'})
    main = SubElement(tags, 'OtherTag', {'ID': 'BT2', 'LABEL': 'Main', 'DESCRIPTION': 'block type Main'})
    commentary = SubElement(tags, 'OtherTag', {'ID': 'BT3', 'LABEL': 'Commentary', 'DESCRIPTION': 'block type Commentary'})
    illustration = SubElement(tags, 'OtherTag', {'ID': 'BT4', 'LABEL': 'Illustration', 'DESCRIPTION': 'block type Illustration'})
    text = SubElement(tags, 'OtherTag', {'ID': 'BT7', 'LABEL': 'text', 'DESCRIPTION': 'block type text'})
    default = SubElement(tags, 'OtherTag', {'ID': 'LT7', 'LABEL': 'default', 'DESCRIPTION': 'line type'})

    # Add the layout information
    layout = SubElement(alto, 'Layout')
    width = str(response['responses'][0]['fullTextAnnotation']['pages'][0]['width'])
    height = str(response['responses'][0]['fullTextAnnotation']['pages'][0]['height'])
    page = SubElement(layout, 'Page', {'WIDTH': width, 'HEIGHT': height, 'PHYSICAL_IMG_NR': '0', 'ID': 'eSc_dummypage_'})
    print_space = SubElement(page, 'PrintSpace', {'HPOS': '0', 'VPOS': '0', 'WIDTH': width, 'HEIGHT': height})

    # Add the text annotations as text blocks, text lines, and strings
    # For each paragraph, add words 
    lines = lines_from_paragraphs(response)
    for line in lines:
        paragraph_text = line['text']
        paragraph_bbox = line['bbox']
        text_block = SubElement(print_space, 'TextBlock', {'HPOS': str(paragraph_bbox['vertices'][0]['x']), 'VPOS': str(paragraph_bbox['vertices'][0]['y']), 'WIDTH': str(paragraph_bbox['vertices'][2]['x'] - paragraph_bbox['vertices'][0]['x']), 'HEIGHT': str(paragraph_bbox['vertices'][2]['y'] - paragraph_bbox['vertices'][0]['y']), 'ID': 'text_block_1'})
        shape = SubElement(text_block, 'Shape')
        polygon = SubElement(shape, 'Polygon', {'POINTS': ' '.join([f"{vertex['x']} {vertex['y']}" for vertex in paragraph_bbox['vertices']])})
        # generate line id
        line_id = 'line_' + str(paragraph_bbox['vertices'][0]['x']) + '_' + str(paragraph_bbox['vertices'][0]['y'])
        height_ = paragraph_bbox['vertices'][2]['y'] - paragraph_bbox['vertices'][0]['y']

        text_line = SubElement(text_block, 'TextLine', {'ID': line_id, 'BASELINE': f"{paragraph_bbox['vertices'][0]['x']} {paragraph_bbox['vertices'][0]['y']+ height_} {paragraph_bbox['vertices'][2]['x']} {paragraph_bbox['vertices'][2]['y']}", 'HPOS': str(paragraph_bbox['vertices'][0]['x']), 'VPOS': str(paragraph_bbox['vertices'][0]['y']), 'WIDTH': str(paragraph_bbox['vertices'][2]['x'] - paragraph_bbox['vertices'][0]['x']), 'HEIGHT': str(paragraph_bbox['vertices'][2]['y'] - paragraph_bbox['vertices'][0]['y'])})
        string = SubElement(text_line, 'String', {'CONTENT': paragraph_text, 'HPOS': str(paragraph_bbox['vertices'][0]['x']), 'VPOS': str(paragraph_bbox['vertices'][0]['y']), 'WIDTH': str(paragraph_bbox['vertices'][2]['x'] - paragraph_bbox['vertices'][0]['x']), 'HEIGHT': str(paragraph_bbox['vertices'][2]['y'] - paragraph_bbox['vertices'][0]['y'])})
        
    # Output the ALTO XML document
    return tostring(alto, encoding='unicode')

if __name__ == '__main__':
    
    with open('anc-1.json', 'r') as f:
        response = json.load(f)
        filename = 'anc-1.png'
        xml = vision_to_alto(filename,response)
        # save to disk
        with open('anc-1.xml', 'w') as f:
            f.write(xml)
