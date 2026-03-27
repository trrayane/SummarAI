import io
import PyPDF2
import docx
from pathlib import Path


class FileParser:
    SUPPORTED_FORMATS = ['.pdf', '.docx', '.txt']

    def parse(self, file) -> str:
        filename = file.filename.lower()

        # Lire tous les bytes en mémoire avant que FastAPI ferme le fichier
        contents = file.file.read()

        if filename.endswith('.pdf'):
            return self._parse_pdf(contents)
        elif filename.endswith('.docx'):
            return self._parse_docx(contents)
        elif filename.endswith('.txt'):
            return contents.decode('utf-8')
        else:
            raise ValueError(f"Format non supporté: {filename}. Formats acceptés: {self.SUPPORTED_FORMATS}")

    def _parse_pdf(self, contents: bytes) -> str:
        reader = PyPDF2.PdfReader(io.BytesIO(contents))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()

    def _parse_docx(self, contents: bytes) -> str:
        doc = docx.Document(io.BytesIO(contents))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs)