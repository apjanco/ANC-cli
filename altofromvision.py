import os
from pathlib import Path
import json
import base64
from xml.etree.ElementTree import Element, SubElement, tostring

import typer
from typing_extensions import Annotated
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
APIKEY = os.environ.get("APIKEY")

app = typer.Typer()


def vision(file_path: str):
    type_ = "DOCUMENT_TEXT_DETECTION"
    image = Path(file_path).read_bytes()

    image_content = base64.b64encode(image)
    vservice = build("vision", "v1", developerKey=APIKEY)
    language = "es"
    request = vservice.images().annotate(
        body={
            "requests": [
                {
                    "image": {"content": image_content.decode("UTF-8")},
                    "imageContext": {"languageHints": [language]},
                    "features": [{"type": type_}],
                }
            ]
        }
    )
    return request.execute(num_retries=3)


def lines_from_paragraphs(response: dict):
    lines = []
    blocks = response["responses"][0]["fullTextAnnotation"]["pages"][0]["blocks"]
    for block in blocks:
        paragraphs = block["paragraphs"]
        for paragraph in paragraphs:
            paragraph_text = ""
            for word in paragraph["words"]:
                w = ""
                for symbol in word["symbols"]:
                    w += symbol["text"]
                paragraph_text += w + " "

            lines.append({"text": paragraph_text, "bbox": paragraph["boundingBox"]})
    return lines


def vision_to_alto(filename: str, response: json):
    # Create the ALTO XML document
    alto = Element(
        "alto",
        {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns": "http://www.loc.gov/standards/alto/ns-v4#",
            "xsi:schemaLocation": "http://www.loc.gov/standards/alto/ns-v4# http://www.loc.gov/standards/alto/v4/alto-4-0.xsd",
        },
    )

    # Add the Description element
    description = SubElement(alto, "Description")
    measurement_unit = SubElement(description, "MeasurementUnit")
    measurement_unit.text = "pixel"
    source_image_information = SubElement(description, "sourceImageInformation")
    file_name = SubElement(source_image_information, "fileName")
    file_name.text = filename

    # Add the Tags element
    tags = SubElement(alto, "Tags")
    title = SubElement(
        tags,
        "OtherTag",
        {"ID": "BT1", "LABEL": "Title", "DESCRIPTION": "block type Title"},
    )
    main = SubElement(
        tags,
        "OtherTag",
        {"ID": "BT2", "LABEL": "Main", "DESCRIPTION": "block type Main"},
    )
    commentary = SubElement(
        tags,
        "OtherTag",
        {"ID": "BT3", "LABEL": "Commentary", "DESCRIPTION": "block type Commentary"},
    )
    illustration = SubElement(
        tags,
        "OtherTag",
        {
            "ID": "BT4",
            "LABEL": "Illustration",
            "DESCRIPTION": "block type Illustration",
        },
    )
    text = SubElement(
        tags,
        "OtherTag",
        {"ID": "BT7", "LABEL": "text", "DESCRIPTION": "block type text"},
    )
    default = SubElement(
        tags, "OtherTag", {"ID": "LT7", "LABEL": "default", "DESCRIPTION": "line type"}
    )

    # Add the layout information
    layout = SubElement(alto, "Layout")
    width = str(response["responses"][0]["fullTextAnnotation"]["pages"][0]["width"])
    height = str(response["responses"][0]["fullTextAnnotation"]["pages"][0]["height"])
    page = SubElement(
        layout,
        "Page",
        {
            "WIDTH": width,
            "HEIGHT": height,
            "PHYSICAL_IMG_NR": "0",
            "ID": "eSc_dummypage_",
        },
    )
    print_space = SubElement(
        page, "PrintSpace", {"HPOS": "0", "VPOS": "0", "WIDTH": width, "HEIGHT": height}
    )

    # Add the text annotations as text blocks, text lines, and strings
    # For each paragraph, add words
    lines = lines_from_paragraphs(response)
    for line in lines:
        paragraph_text = line["text"]
        paragraph_bbox = line["bbox"]
        text_block = SubElement(
            print_space,
            "TextBlock",
            {
                "HPOS": str(paragraph_bbox["vertices"][0]["x"]),
                "VPOS": str(paragraph_bbox["vertices"][0]["y"]),
                "WIDTH": str(
                    paragraph_bbox["vertices"][2]["x"]
                    - paragraph_bbox["vertices"][0]["x"]
                ),
                "HEIGHT": str(
                    paragraph_bbox["vertices"][2]["y"]
                    - paragraph_bbox["vertices"][0]["y"]
                ),
                "ID": "text_block_1",
            },
        )
        shape = SubElement(text_block, "Shape")
        polygon = SubElement(
            shape,
            "Polygon",
            {
                "POINTS": " ".join(
                    [
                        f"{vertex['x']} {vertex['y']}"
                        for vertex in paragraph_bbox["vertices"]
                    ]
                )
            },
        )
        # generate line id
        line_id = (
            "line_"
            + str(paragraph_bbox["vertices"][0]["x"])
            + "_"
            + str(paragraph_bbox["vertices"][0]["y"])
        )
        height_ = (
            paragraph_bbox["vertices"][2]["y"] - paragraph_bbox["vertices"][0]["y"]
        )

        text_line = SubElement(
            text_block,
            "TextLine",
            {
                "ID": line_id,
                "BASELINE": f"{paragraph_bbox['vertices'][0]['x']} {paragraph_bbox['vertices'][0]['y']+ height_} {paragraph_bbox['vertices'][2]['x']} {paragraph_bbox['vertices'][2]['y']}",
                "HPOS": str(paragraph_bbox["vertices"][0]["x"]),
                "VPOS": str(paragraph_bbox["vertices"][0]["y"]),
                "WIDTH": str(
                    paragraph_bbox["vertices"][2]["x"]
                    - paragraph_bbox["vertices"][0]["x"]
                ),
                "HEIGHT": str(
                    paragraph_bbox["vertices"][2]["y"]
                    - paragraph_bbox["vertices"][0]["y"]
                ),
            },
        )
        string = SubElement(
            text_line,
            "String",
            {
                "CONTENT": paragraph_text,
                "HPOS": str(paragraph_bbox["vertices"][0]["x"]),
                "VPOS": str(paragraph_bbox["vertices"][0]["y"]),
                "WIDTH": str(
                    paragraph_bbox["vertices"][2]["x"]
                    - paragraph_bbox["vertices"][0]["x"]
                ),
                "HEIGHT": str(
                    paragraph_bbox["vertices"][2]["y"]
                    - paragraph_bbox["vertices"][0]["y"]
                ),
            },
        )

    # Output the ALTO XML document
    return tostring(alto, encoding="unicode")


@app.command()
def main(folder_path: Annotated[Path, typer.Argument()]):
    if folder_path.exists():
        outpath = Path(folder_path / "alto")
        if not outpath.exists():
            outpath.mkdir(parents=True, exist_ok=True)

        for image in folder_path.glob("**/*.jpg"):
            response = vision(str(image))
            xml = vision_to_alto(image.name, response)
            # save to disk
            (outpath / image.name.replace(".jpg", ".xml")).write_text(xml)


if __name__ == "__main__":
    typer.run(main)
