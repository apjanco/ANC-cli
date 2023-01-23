import base64
import io
import os
import typer
from pathlib import Path
import pandas as pd 
from googleapiclient.discovery import build
from pdf2image import convert_from_path
from PIL import Image
from fuzzysearch import find_near_matches

type_ =  'DOCUMENT_TEXT_DETECTION'

def in_box(box_top_right, box_bottom_right, word_upper_left): #bl, tr, p): 
  """https://www.tutorialspoint.com/check-if-a-point-lies-on-or-inside-a-rectangle-in-python
  however this uses 0,0 in lower left, we need in upper left
  ex: (990, 1166) (500, 1184) (214, 630)
  """
  box_bottom_right_x = box_bottom_right[0]
  box_bottom_right_y = box_bottom_right[1]
  box_top_right_x = box_top_right[0]
  box_top_right_y = box_top_right[1]
  word_x = word_upper_left[0]
  word_y = word_upper_left[1]
  # word_x 879 should be larger than box_top_right_x 700 True
  # box_top_right_y plus or minus 50
  
  # word x is to the right of the term
  # word y is below the 
  if (word_x > box_top_right_x and box_top_right_y < word_y  and word_y < box_bottom_right_y + 75): #TODO add slider to adjust this value
    return True
  else :
    return False

def get_data(form:dict, field:str, difference:int) -> list:
    '''
    Takes the json response from Google Vision for a single image.
    The image has one of the fields present in it.
    This function, identifies the location of the field in the image
    It then find the nearest value to the right 
    Then it checks the result against a list of valid results with fuzzy search
    It returns the text of the form value.

            Parameters:
                    form (dict): The result from Google Vision for an image
                    field
                    difference
            Returns:
                    field (str): A string of the field (departamento...)
    '''
    results = []
    page = form['page']
    filename = form['filename']
    for i, word in enumerate(form['responses'][0]['textAnnotations']):
      if i != 0:
        text = word['description']    
        for match in find_near_matches(field.lower(), text.lower(), max_l_dist=difference):
          verticies = word['boundingPoly']['vertices']
          #upper left
          ulX = verticies[0]['x']
          ulY = verticies[0]['y']
          #lower left
          lolX = verticies[1]['x']
          lolY = verticies[1]['y']
          # lower right
          lorX = verticies[2]['x']
          lorY = verticies[2]['y']
          # upper right
          uprX = verticies[3]['x']
          uprY = verticies[3]['y']
          
          #Search box 
          x1 = uprX 
          x2 = lorX 
          y1 = uprY
          y2 = lolY
          box_bottom_left = (x2,y2)
          box_top_right = (x1,y1)

          # iterate over the words
          for i, w in enumerate(form['responses'][0]['textAnnotations']):
            if i != 0:
              verts = w['boundingPoly']['vertices']
                  
              #upper left
              word_upper_left = (verts[0]['x'],verts[0]['y'])
              if in_box(box_bottom_left, box_top_right, word_upper_left):
                  prior_word = ''
                  try:
                    prior_word = form['responses'][0]['textAnnotations'][i-1]['description']
                  except:
                    pass
                  next_word = ''
                  try:
                    next_word = form['responses'][0]['textAnnotations'][i+1]['description']
                  except:
                    pass
                  results.append(dict(value=w['description'], key=word['description'],page=page,filename=filename, next_word=next_word,prior_word=prior_word))
    return results

def image_to_byte_array(image: Image) -> bytes:
  imgByteArr = io.BytesIO()
  image.save(imgByteArr, format=image.format)
  imgByteArr = imgByteArr.getvalue()
  return imgByteArr

def has_terms(text:str):
  """A helper function to check if a text contains relevant terms"""
  match_terms = ['departamento', 'municipo','DEP.INT.COM.']
  for term in match_terms:
    if find_near_matches(term, text.lower(), max_l_dist=1):
      return True
  return False

def pdf_to_data(path:str, language:str, APIKEY:str):
    if APIKEY:
        images = convert_from_path(path)
        data = []
        for i, image in enumerate(images):
            #Path(f'image{i}.jpg').write_bytes(image_to_byte_array(image))
            image_content = base64.b64encode(image_to_byte_array(image))
            vservice = build('vision', 'v1', developerKey=APIKEY)
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
            responses = request.execute(num_retries=3)
            responses['page'] = i
            responses['filename'] = path
            data.append(responses)
        return data
    else:
        typer.echo(f"Please set the API key.")