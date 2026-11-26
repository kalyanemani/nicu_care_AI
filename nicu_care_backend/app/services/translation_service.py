"""
Multilingual Clinical Translation & NLU Service:
Supports Telugu (te-IN), Hindi (hi-IN), Tamil (ta-IN), and English (en-US).
Normalizes vernacular neonatal queries into canonical clinical concepts for reasoning,
and renders culturally soothing native language voice notes and display cards.
"""
import re
from typing import Tuple, Dict, Any, Optional


class MultilingualTranslationService:
    """
    Bidirectional translation and clinical phrase mapping engine.
    Offline-capable with zero-latency deterministic routing.
    """

    # Telugu Clinical Term Lexicon
    TELUGU_MAP = {
        "పాలు": "breast milk",
        "ఫీడింగ్": "feed",
        "వాంతులు": "vomit",
        "ఆకుపచ్చ వాంతులు": "green vomit bilious",
        "ఆకుపచ్చ": "green",
        "నీలం రంగు": "blue cyanosis",
        "నీలం": "blue",
        "ఆయాసం": "chest retraction breathing distress",
        "శ్వాస": "breathing",
        "జ్వరం": "fever",
        "డైపర్": "diaper",
        "మలము": "stool poop",
        "బరువు": "weight",
        "కంగారూ కేర్": "kangaroo mother care",
        "నిద్ర": "safe sleep",
        "ఆసుపత్రి": "hospital",
        "రెయిన్బో": "Rainbow Hospital",
        "ఎమర్జెన్సీ": "emergency",
    }

    # Hindi Clinical Term Lexicon
    HINDI_MAP = {
        "दूध": "breast milk",
        "उल्टी": "vomit",
        "हरी उल्टी": "green vomit bilious",
        "हरा": "green",
        "नीला": "blue cyanosis",
        "सांस": "breathing distress retraction",
        "बुखार": "fever",
        "डायपर": "diaper",
        "वजन": "weight",
        "अस्पताल": "hospital",
        "आपातकाल": "emergency",
    }

    def detect_language(self, text: str) -> str:
        """Detects whether text is in Telugu, Hindi, or English."""
        # Telugu Unicode range: \u0C00-\u0C7F
        if re.search(r'[\u0C00-\u0C7F]', text):
            return "te-IN"
        # Devanagari (Hindi) Unicode range: \u0900-\u097F
        elif re.search(r'[\u0900-\u097F]', text):
            return "hi-IN"
        # Tamil Unicode range: \u0B80-\u0BFF
        elif re.search(r'[\u0B80-\u0BFF]', text):
            return "ta-IN"
        return "en-US"

    def translate_to_canonical_english(self, text: str, lang: Optional[str] = None) -> Tuple[str, str]:
        """
        Translates vernacular mother input into canonical English clinical query.
        Returns: (canonical_query, detected_language)
        """
        detected_lang = lang or self.detect_language(text)

        if detected_lang == "te-IN":
            canonical = text
            for tel_word, eng_concept in self.TELUGU_MAP.items():
                if tel_word in canonical:
                    canonical = canonical.replace(tel_word, eng_concept)
            return canonical, "te-IN"

        elif detected_lang == "hi-IN":
            canonical = text
            for hin_word, eng_concept in self.HINDI_MAP.items():
                if hin_word in canonical:
                    canonical = canonical.replace(hin_word, eng_concept)
            return canonical, "hi-IN"

        return text, "en-US"

    def render_native_response(
        self,
        text_card: str,
        voice_summary: str,
        target_lang: str,
        is_emergency: bool = False,
        model: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Renders native language voice note and card formatting in the target language (Telugu, Hindi, Tamil, etc.).
        Uses an LLM translation synthesis pass when available, with reliable clinical fallback templates.
        """
        lang_names = {
            "te-IN": "Telugu",
            "hi-IN": "Hindi",
            "ta-IN": "Tamil",
            "en-US": "English"
        }
        target_language_name = lang_names.get(target_lang, "English")
        if target_lang == "en-US":
            return text_card, voice_summary

        # Attempt high-quality clinical translation using the routed fast LLM
        try:
            from .llm_service import llm_service
            translation_prompt = f"""You are an empathetic, expert pediatric nurse and medical translator.
Translate the following neonatal clinical guidance into fluent, warm, culturally soothing {target_language_name}.
Preserve all specific numerical values, units (mL, g, hours, °C), medicine names, and clinical facts accurately.
Write directly in the {target_language_name} script (Telugu / Devanagari Hindi / Tamil).

Text to translate:
{voice_summary or text_card[:400]}

Provide ONLY two parts formatted exactly as:
CARD: <translated markdown response for parent>
VOICE: <1-2 concise, calming sentences in {target_language_name} suitable for text-to-speech>
"""
            model_to_use = model or llm_service.get_routed_model("pediatric_math") or "qwen2.5:3b"
            llm_out = llm_service.invoke(
                system_prompt=f"You are a professional medical translator for {target_language_name}.",
                prompt=translation_prompt,
                model_name=model_to_use
            )

            card_trans = ""
            voice_trans = ""
            for line in llm_out.strip().split("\n"):
                if line.startswith("CARD:"):
                    card_trans = line[5:].strip()
                elif line.startswith("VOICE:"):
                    voice_trans = line[6:].strip()

            if not card_trans:
                card_trans = llm_out.strip()
            if not voice_trans:
                voice_trans = card_trans.split(".")[0] + "."

            if card_trans and len(card_trans) > 10:
                header = {
                    "te-IN": "✅ నవజాత శిశు సంరక్షణ మార్గదర్శకాలు (NICU Care Guidance)",
                    "hi-IN": "✅ नवजात शिशु देखभाल मार्गदर्शन (NICU Care Guidance)",
                    "ta-IN": "✅ பிறந்த குழந்தை பராமரிப்பு வழிகாட்டுதல் (NICU Care Guidance)",
                }.get(target_lang, "✅ NICU Care Guidance")
                
                disclaimer = {
                    "te-IN": "*గమనిక: ఈ మార్గదర్శకత్వం అవగాహన కొరకు మాత్రమే. మందులు లేదా ఫీడింగ్ మార్చే ముందు వైద్యుడిని సంప్రదించండి.*",
                    "hi-IN": "*सूचना: यह मार्गदर्शन केवल सहायता के लिए है। किसी भी बदलाव से पहले अपने डॉक्टर से सलाह लें।*",
                    "ta-IN": "*குறிப்பு: இது தகவல் மற்றும் ஆதரவுக்காக மட்டுமே. மாற்றங்களைச் செய்வதற்கு முன் மருத்துவரை அணுகவும்.*",
                }.get(target_lang, "*Guidance is for supportive care. Consult your pediatrician before adjustments.*")

                full_card = f"{header}\n\n{card_trans}\n\n---\n{disclaimer}"
                return full_card, voice_trans
        except Exception:
            pass

        # Fallback templates if LLM translation call is unavailable
        if target_lang == "te-IN":
            if is_emergency:
                native_voice = "వెంటనే మీ ఆసుపత్రిలోని NICU ఎమర్జెన్సీ విభాగానికి కాల్ చేయండి. ఈ లక్షణాలు తక్షణ వైద్య సహాయం కోరుతున్నాయి."
                native_header = "⚠️ తక్షణ వైద్య సహాయం అవసరం (URGENT CLINICAL ATTENTION NEEDED)"
            else:
                native_voice = "పీడియాట్రిక్ మార్గదర్శకాల ప్రకారం మీ బాబు ఆరోగ్యం మరియు సంరక్షణ వివరాలు నమోదు చేయబడ్డాయి."
                native_header = "✅ నవజాత శిశు సంరక్షణ మార్గదర్శకాలు (NICU Care Guidance)"

            formatted_card = (
                f"{native_header}\n\n"
                f"{text_card}\n\n"
                f"---\n"
                f"*గమనిక: ఈ మార్గదర్శకత్వం అవగాహన మరియు సహాయం కొరకు మాత్రమే. మందులు లేదా ఫీడింగ్ మార్చే ముందు వైద్యుడిని సంప్రదించండి.*"
            )
            return formatted_card, native_voice

        elif target_lang == "hi-IN":
            if is_emergency:
                native_voice = "कृपया तुरंत अपने अस्पताल के एनआईसीयू आपातकालीन नंबर पर कॉल करें। यह स्थिति तुरंत डॉक्टर को दिखाने की है।"
                native_header = "⚠️ तत्काल चिकित्सकीय ध्यान आवश्यक (URGENT ATTENTION NEEDED)"
            else:
                native_voice = "बाल रोग विशेषज्ञों के दिशानिर्देशों के अनुसार शिशु की देखभाल संबंधी विवरण दर्ज कर लिया गया है।"
                native_header = "✅ नवजात शिशु देखभाल मार्गदर्शन (NICU Care Guidance)"

            formatted_card = (
                f"{native_header}\n\n"
                f"{text_card}\n\n"
                f"---\n"
                f"*सूचना: यह मार्गदर्शन केवल सहायता और शैक्षिक उद्देश्य के लिए है। किसी भी बदलाव से पहले अपने डॉक्टर से सलाह लें।*"
            )
            return formatted_card, native_voice

        return text_card, voice_summary


# Global Singleton Translation Service
translation_service = MultilingualTranslationService()
