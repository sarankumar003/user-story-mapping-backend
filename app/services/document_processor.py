"""
Document Processing Service
Handles BRD document parsing and text extraction
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
import PyPDF2
from docx import Document
from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes BRD documents and extracts text"""
    
    def __init__(self):
        self.supported_formats = settings.ALLOWED_FILE_TYPES.split(',')
    
    def extract_text(self, file_path: str) -> Optional[str]:
        """Extract text from document based on file type"""
        file_path = Path(file_path)
        
        logger.info(f"Extracting text from: {file_path}")
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        file_extension = file_path.suffix.lower()
        logger.info(f"File extension: {file_extension}")
        logger.info(f"Supported formats: {self.supported_formats}")
        
        if file_extension not in self.supported_formats:
            logger.error(f"Unsupported file format: {file_extension}")
            return None
        
        try:
            if file_extension == '.pdf':
                text = self._extract_pdf_text(file_path)
            elif file_extension in ['.docx', '.doc']:
                text = self._extract_word_text(file_path)
            else:
                logger.error(f"No processor for file type: {file_extension}")
                return None
            
            logger.info(f"Extracted text length: {len(text) if text else 0} characters")
            if text:
                logger.info(f"First 200 characters: {text[:200]}...")
            
            return text
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None
    
    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        text = ""
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
        
        return text.strip()
    
    def _extract_word_text(self, file_path: Path) -> str:
        """Extract text from Word document"""
        doc = Document(file_path)
        text = ""
        
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text.strip()
    
    def validate_file(self, file_path: str, file_size: int) -> Tuple[bool, str]:
        """Validate uploaded file"""
        file_path = Path(file_path)
        
        # Check file size
        if file_size > settings.UPLOAD_MAX_SIZE:
            return False, f"File size exceeds maximum allowed size of {settings.UPLOAD_MAX_SIZE} bytes"
        
        # Check file extension
        if file_path.suffix.lower() not in self.supported_formats:
            return False, f"Unsupported file format. Allowed formats: {', '.join(self.supported_formats)}"
        
        # Check if file exists
        if not file_path.exists():
            return False, "File not found"
        
        return True, "File is valid"
