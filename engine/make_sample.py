"""Generate docs/sample.docx using zipfile only."""
import argparse, zipfile
from pathlib import Path
CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:sz w:val="26"/></w:rPr></w:style>
</w:styles>"""
SECT1 = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:left="1440" w:right="1440" w:top="1440" w:bottom="1440"/></w:sectPr>'
SECT2 = '<w:sectPr><w:pgSz w:w="8391" w:h="11906"/><w:pgMar w:left="1134" w:right="1134" w:top="1134" w:bottom="1134"/></w:sectPr>'
SECT3 = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:left="3600" w:right="3600" w:top="3600" w:bottom="3600"/></w:sectPr>'
def _run(text, direct=None):
    rpr = f'<w:rPr><w:rFonts w:ascii="{direct["font"]}"/><w:sz w:val="{direct["sz"]}"/></w:rPr>' if direct else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'
def _p(text, style=None, direct=None, sect=None):
    inner = ""
    if style: inner += f'<w:pStyle w:val="{style}"/>'
    if direct:
        inner += f'<w:rPr><w:rFonts w:ascii="{direct["font"]}"/><w:sz w:val="{direct["sz"]}"/></w:rPr>'
        inner += f'<w:spacing w:line="{direct["line"]}" w:lineRule="auto" w:after="{direct["after"]}"/>'
    if sect: inner += sect
    return f"<w:p>{'<w:pPr>'+inner+'</w:pPr>' if inner else ''}{_run(text, direct)}</w:p>"
def make(path):
    d2 = {"font": "Georgia", "sz": 22, "line": 288, "after": 0}
    d3 = {"font": "Arial", "sz": 40, "line": 720, "after": 600}
    body = (_p("Okavango Notes", "Heading1")
            + _p("The Okavango Delta floods near Maun each winter.")
            + _p("Water", "Heading2")
            + _p("Channels carry the flood south from Angola.", sect=SECT1)
            + _p("River Life", "Heading1")
            + _p("Visitors reach Maun by air.", direct=d2)
            + _p("Boats leave at dawn.", direct=d2, sect=SECT2)
            + _p("We left Maun at dawn.", direct=d3)
            + _p("The Delta fades.", direct=d3))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}{SECT3}</w:body></w:document>')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", STYLES)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="docs/sample.docx")
    make(ap.parse_args().path)
if __name__ == "__main__": main()
