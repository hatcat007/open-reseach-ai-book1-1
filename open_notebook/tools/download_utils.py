from typing import Dict, Any, Optional
from open_notebook.domain.notebook import Note
import json
import io

# For DOCX
from docx import Document
from docx.shared import Inches

# For PDF (Markdown -> HTML -> PDF)
import markdown # For converting Markdown to HTML
from weasyprint import HTML # For converting HTML to PDF

def note_to_txt(note: Note) -> str:
    """Converts a Note object to a plain text string."""
    return f"Title: {note.title or 'Untitled Note'}\n\n{note.content or ''}"

def note_to_md(note: Note) -> str:
    """Converts a Note object to a Markdown string."""
    return f"# {note.title or 'Untitled Note'}\n\n{note.content or ''}"

def note_to_json(note: Note) -> str:
    """Serializes a Note object to a JSON string."""
    note_data = {
        "id": note.id,
        "title": note.title or 'Untitled Note',
        "content": note.content or '',
        "note_type": note.note_type,
        "created": note.created.isoformat() if note.created else None,
        "updated": note.updated.isoformat() if note.updated else None,
    }
    return json.dumps(note_data, indent=2)

def note_to_docx_bytes(note: Note) -> bytes:
    """Converts a Note object to DOCX format (bytes)."""
    document = Document()
    document.add_heading(note.title or 'Untitled Note', level=1)
    
    # Add content. Handles None content gracefully.
    content = note.content or ""
    # Simple paragraph addition. For complex markdown, a more sophisticated parser might be needed.
    # For now, we treat the content as plain text for DOCX.
    # If content is Markdown, it will appear as raw Markdown text.
    document.add_paragraph(content)
    
    bio = io.BytesIO()
    document.save(bio)
    return bio.getvalue()

def note_to_pdf_bytes(note: Note) -> bytes:
    """Converts a Note object to PDF format (bytes) via HTML."""
    # Convert note content (assumed to be Markdown) to HTML
    # Ensure title and content are not None
    title = note.title or 'Untitled Note'
    md_content = f"# {title}\n\n{note.content or ''}"
    html_content = markdown.markdown(md_content, extensions=['extra', 'sane_lists'])

    # Basic styling (optional, but improves readability)
    styled_html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: sans-serif; margin: 2em; }}
                h1 {{ color: #333; }}
                p {{ line-height: 1.6; }}
                pre {{ background-color: #f4f4f4; padding: 1em; border-radius: 5px; overflow-x: auto; }}
                code {{ font-family: monospace; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
    </html>
    """
    
    return HTML(string=styled_html).write_pdf() 