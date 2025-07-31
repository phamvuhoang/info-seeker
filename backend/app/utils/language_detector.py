import re
from typing import Dict, Optional, Tuple
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException


class LanguageDetector:
    """Language detection utility for multi-language support"""
    
    # Language code to name mapping
    LANGUAGE_NAMES = {
        'en': 'English',
        'es': 'Spanish', 
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'th': 'Thai',
        'vi': 'Vietnamese',
        'nl': 'Dutch',
        'sv': 'Swedish',
        'da': 'Danish',
        'no': 'Norwegian',
        'fi': 'Finnish',
        'pl': 'Polish',
        'cs': 'Czech',
        'hu': 'Hungarian',
        'ro': 'Romanian',
        'bg': 'Bulgarian',
        'hr': 'Croatian',
        'sk': 'Slovak',
        'sl': 'Slovenian',
        'et': 'Estonian',
        'lv': 'Latvian',
        'lt': 'Lithuanian',
        'el': 'Greek',
        'tr': 'Turkish',
        'he': 'Hebrew',
        'fa': 'Persian',
        'ur': 'Urdu',
        'bn': 'Bengali',
        'ta': 'Tamil',
        'te': 'Telugu',
        'ml': 'Malayalam',
        'kn': 'Kannada',
        'gu': 'Gujarati',
        'pa': 'Punjabi',
        'mr': 'Marathi',
        'ne': 'Nepali',
        'si': 'Sinhala',
        'my': 'Myanmar',
        'km': 'Khmer',
        'lo': 'Lao',
        'ka': 'Georgian',
        'am': 'Amharic',
        'sw': 'Swahili',
        'zu': 'Zulu',
        'af': 'Afrikaans',
        'sq': 'Albanian',
        'az': 'Azerbaijani',
        'be': 'Belarusian',
        'bs': 'Bosnian',
        'eu': 'Basque',
        'gl': 'Galician',
        'is': 'Icelandic',
        'ga': 'Irish',
        'mk': 'Macedonian',
        'mt': 'Maltese',
        'cy': 'Welsh'
    }
    
    # Language-specific response instructions
    LANGUAGE_INSTRUCTIONS = {
        'en': "Respond in English.",
        'es': "Responde en español.",
        'fr': "Répondez en français.",
        'de': "Antworten Sie auf Deutsch.",
        'it': "Rispondi in italiano.",
        'pt': "Responda em português.",
        'ru': "Отвечайте на русском языке.",
        'ja': "日本語で回答してください。",
        'ko': "한국어로 답변해 주세요.",
        'zh': "请用中文回答。",
        'ar': "أجب باللغة العربية.",
        'hi': "हिंदी में उत्तर दें।",
        'th': "ตอบเป็นภาษาไทย",
        'vi': "Trả lời bằng tiếng Việt.",
        'nl': "Antwoord in het Nederlands.",
        'sv': "Svara på svenska.",
        'da': "Svar på dansk.",
        'no': "Svar på norsk.",
        'fi': "Vastaa suomeksi.",
        'pl': "Odpowiedz po polsku.",
        'cs': "Odpovězte v češtině.",
        'hu': "Válaszoljon magyarul.",
        'ro': "Răspundeți în română.",
        'bg': "Отговорете на български.",
        'hr': "Odgovorite na hrvatskom.",
        'sk': "Odpovedajte v slovenčine.",
        'sl': "Odgovorite v slovenščini.",
        'et': "Vastake eesti keeles.",
        'lv': "Atbildiet latviešu valodā.",
        'lt': "Atsakykite lietuvių kalba.",
        'el': "Απαντήστε στα ελληνικά.",
        'tr': "Türkçe cevap verin.",
        'he': "ענה בעברית.",
        'fa': "به فارسی پاسخ دهید.",
        'ur': "اردو میں جواب دیں۔",
        'bn': "বাংলায় উত্তর দিন।",
        'ta': "தமிழில் பதிலளிக்கவும்।",
        'te': "తెలుగులో సమాధానం ఇవ్వండి।",
        'ml': "മലയാളത്തിൽ ഉത്തരം നൽകുക।",
        'kn': "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ।",
        'gu': "ગુજરાતીમાં જવાબ આપો।",
        'pa': "ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।",
        'mr': "मराठीत उत्तर द्या।",
        'ne': "नेपालीमा जवाफ दिनुहोस्।",
        'si': "සිංහලෙන් පිළිතුරු දෙන්න.",
        'my': "မြန်မာဘာသာဖြင့် ဖြေကြားပါ။",
        'km': "ឆ្លើយជាភាសាខ្មែរ។",
        'lo': "ຕອບເປັນພາສາລາວ.",
        'ka': "უპასუხეთ ქართულად.",
        'am': "በአማርኛ ይመልሱ።",
        'sw': "Jibu kwa Kiswahili.",
        'zu': "Phendula ngesiZulu.",
        'af': "Antwoord in Afrikaans.",
        'sq': "Përgjigjuni në shqip.",
        'az': "Azərbaycan dilində cavab verin.",
        'be': "Адкажыце па-беларуску.",
        'bs': "Odgovorite na bosanskom.",
        'eu': "Erantzun euskeraz.",
        'gl': "Responde en galego.",
        'is': "Svaraðu á íslensku.",
        'ga': "Freagair as Gaeilge.",
        'mk': "Одговорете на македонски.",
        'mt': "Wieġeb bil-Malti.",
        'cy': "Atebwch yn Gymraeg."
    }
    
    @classmethod
    def detect_language(cls, text: str) -> Tuple[str, float]:
        """
        Detect language of the given text
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not text or len(text.strip()) < 3:
            return 'en', 0.5  # Default to English for very short text
        
        try:
            # Clean text for better detection
            cleaned_text = cls._clean_text_for_detection(text)
            
            if len(cleaned_text) < 3:
                return 'en', 0.5
            
            detected_lang = detect(cleaned_text)
            confidence = 0.8  # langdetect doesn't provide confidence, so we use a default
            
            # Validate detected language
            if detected_lang in cls.LANGUAGE_NAMES:
                return detected_lang, confidence
            else:
                return 'en', 0.5  # Fallback to English
                
        except LangDetectException:
            return 'en', 0.5  # Fallback to English on detection error
        except Exception as e:
            print(f"Language detection error: {e}")
            return 'en', 0.5
    
    @classmethod
    def _clean_text_for_detection(cls, text: str) -> str:
        """Clean text to improve language detection accuracy"""
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
        
        # Remove numbers and special characters but keep letters and basic punctuation
        text = re.sub(r'[^\w\s\.\!\?\,\;\:\-\'\"]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    @classmethod
    def get_language_instruction(cls, language_code: str) -> str:
        """Get language-specific instruction for AI agents"""
        return cls.LANGUAGE_INSTRUCTIONS.get(language_code, cls.LANGUAGE_INSTRUCTIONS['en'])
    
    @classmethod
    def get_language_name(cls, language_code: str) -> str:
        """Get human-readable language name"""
        return cls.LANGUAGE_NAMES.get(language_code, 'English')
    
    @classmethod
    def is_supported_language(cls, language_code: str) -> bool:
        """Check if language is supported"""
        return language_code in cls.LANGUAGE_NAMES
    
    @classmethod
    def get_supported_languages(cls) -> Dict[str, str]:
        """Get all supported languages"""
        return cls.LANGUAGE_NAMES.copy()


# Global instance
language_detector = LanguageDetector()
