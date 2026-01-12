"""
AI-Powered Document Processing
Uses Groq for fast AI document analysis.
"""

from __future__ import annotations

import os
import io
from typing import Literal

import fitz  # PyMuPDF

# Try to import OpenAI SDK (works with Groq too)
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class AIError(Exception):
    """Error during AI processing."""
    pass


def get_ai_client():
    """Get Groq client."""
    if not HAS_OPENAI:
        raise AIError("OpenAI SDK not installed. Run: pip install openai")
    
    # Use Groq - API key from environment variable only
    api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        raise AIError("GROQ_API_KEY environment variable not set. Add it to server/.env file.")
    
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )


def extract_text_from_pdf(pdf_bytes: bytes, max_chars: int = 100000) -> str:
    """Extract text from PDF for AI processing."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        total_chars = 0
        
        for page in doc:
            page_text = page.get_text()
            if total_chars + len(page_text) > max_chars:
                # Truncate
                remaining = max_chars - total_chars
                text_parts.append(page_text[:remaining])
                text_parts.append("\n\n[Document truncated due to length...]")
                break
            text_parts.append(page_text)
            total_chars += len(page_text)
        
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        raise AIError(f"Failed to extract text from PDF: {e}")


class AISummarizer:
    """AI-powered document summarization."""
    
    @staticmethod
    def summarize(
        pdf_bytes: bytes,
        length: Literal["brief", "medium", "detailed"] = "medium",
        style: Literal["bullets", "prose", "outline"] = "bullets",
    ) -> str:
        """Generate AI summary of document.
        
        Args:
            pdf_bytes: PDF file contents
            length: Summary length preference
            style: Output style
            
        Returns:
            Summary text
        """
        client = get_ai_client()
        text = extract_text_from_pdf(pdf_bytes)
        
        if not text.strip():
            raise AIError("No text content found in PDF")
        
        # Build prompt
        length_instructions = {
            "brief": "Provide a brief 1-2 paragraph summary.",
            "medium": "Provide a comprehensive 3-5 paragraph summary covering all main points.",
            "detailed": "Provide a detailed analysis covering all major topics, arguments, and conclusions.",
        }
        
        style_instructions = {
            "bullets": "Format the output as bullet points.",
            "prose": "Format the output as flowing prose paragraphs.",
            "outline": "Format the output as a structured outline with headers and sub-points.",
        }
        
        prompt = f"""Analyze the following document and provide a summary.

{length_instructions.get(length, length_instructions["medium"])}
{style_instructions.get(style, style_instructions["bullets"])}

Document content:
---
{text}
---

Summary:"""
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a professional document analyst. Provide clear, accurate summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3,
            )
            return response.choices[0].message.content or "No summary generated."
        except Exception as e:
            raise AIError(f"AI summarization failed: {e}")


class AIChatPDF:
    """AI-powered document Q&A."""
    
    @staticmethod
    def ask(pdf_bytes: bytes, question: str) -> str:
        """Answer a question about the document.
        
        Args:
            pdf_bytes: PDF file contents
            question: User's question
            
        Returns:
            Answer text
        """
        if not question.strip():
            raise AIError("Question cannot be empty")
        
        client = get_ai_client()
        text = extract_text_from_pdf(pdf_bytes)
        
        if not text.strip():
            raise AIError("No text content found in PDF")
        
        prompt = f"""Based on the following document, answer the user's question accurately and concisely.

Document content:
---
{text}
---

User's question: {question}

Provide a direct, helpful answer based only on the document content. If the answer cannot be found in the document, say so clearly."""
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a helpful document analyst. Answer questions based only on the provided document content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.2,
            )
            return response.choices[0].message.content or "No answer generated."
        except Exception as e:
            raise AIError(f"AI Q&A failed: {e}")


class AITranslator:
    """AI-powered document translation."""
    
    LANGUAGE_NAMES = {
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "hi": "Hindi",
    }
    
    @staticmethod
    def translate(pdf_bytes: bytes, target_language: str) -> bytes:
        """Translate document to target language.
        
        Note: This returns a text file, not a formatted PDF.
        Full PDF translation with layout preservation requires more complex processing.
        
        Args:
            pdf_bytes: PDF file contents
            target_language: Target language code
            
        Returns:
            Translated text as bytes
        """
        client = get_ai_client()
        text = extract_text_from_pdf(pdf_bytes)
        
        if not text.strip():
            raise AIError("No text content found in PDF")
        
        lang_name = AITranslator.LANGUAGE_NAMES.get(target_language, target_language)
        
        prompt = f"""Translate the following document to {lang_name}. 
Preserve the original formatting and structure as much as possible.

Document:
---
{text}
---

Translated document:"""
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": f"You are a professional translator. Translate accurately to {lang_name} while preserving meaning and tone."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.3,
            )
            translated = response.choices[0].message.content or "Translation failed."
            return translated.encode("utf-8")
        except Exception as e:
            raise AIError(f"AI translation failed: {e}")


def check_ai_status() -> dict:
    """Check AI system status."""
    api_key_set = bool(os.environ.get("GROQ_API_KEY"))
    
    status = {
        "openai_sdk_installed": HAS_OPENAI,
        "api_key_configured": api_key_set,
        "provider": "Groq",
        "model": "llama-3.3-70b-versatile",
        "ready": HAS_OPENAI and api_key_set,
        "message": "",
    }
    
    if not HAS_OPENAI:
        status["message"] = "OpenAI SDK not installed. Run: pip install openai"
    elif not api_key_set:
        status["message"] = "GROQ_API_KEY not set. Add it to server/.env file."
    else:
        status["message"] = "AI features ready (powered by Groq + Llama 3.3 70B)"
    
    return status
