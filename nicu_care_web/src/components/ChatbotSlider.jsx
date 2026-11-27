import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  ChevronDown,
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  Sparkles,
  ShieldAlert,
  Loader2,
  Cpu,
  Globe,
  X
} from "lucide-react";
import { agentApi } from "../api";

const LANGUAGES = [
  { code: "en-US", label: "English", nativeLabel: "English", ttsLang: "en-US" },
  { code: "te-IN", label: "Telugu", nativeLabel: "తెలుగు", ttsLang: "te-IN" },
  { code: "hi-IN", label: "Hindi", nativeLabel: "हिन्दी", ttsLang: "hi-IN" },
  { code: "ta-IN", label: "Tamil", nativeLabel: "தமிழ்", ttsLang: "ta-IN" }
];

export default function ChatbotSlider({ baby }) {
  const babyName = baby?.name || "Baby";
  const babyId = baby?.baby_id || "";

  const [isOpen, setIsOpen] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("en-US");
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      sender: "assistant",
      text: `Hello! I am Baby ${babyName}'s Post-NICU Clinical Companion. You can ask me anything about ${babyName}'s feeding volume, safe room temperature, medications, or skin-to-skin Kangaroo care.`,
      voice: `Hello! I am Baby ${babyName}'s Post NICU Clinical Companion. You can ask me anything about ${babyName}'s feeding, safe sleep, or medications.`
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState("qwen2.5:3b");
  const messagesEndRef = useRef(null);

  // Speech Recognition Setup
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = selectedLanguage;

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputValue(transcript);
        setIsListening(false);
        // Automatically submit voice query and request voice output
        handleSend(transcript, true);
      };

      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognitionRef.current = recognition;
    }
  }, [selectedLanguage]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  function speakText(text, langCode = selectedLanguage) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const cleanText = text.replace(/[*_#`]/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = langCode;
    utterance.rate = 1.0;
    utterance.pitch = 1.05;

    // Pick voice matching langCode if available
    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find((v) => v.lang.startsWith(langCode.slice(0, 2)));
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    window.speechSynthesis.speak(utterance);
  }

  function toggleListening() {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in this browser. Please type your query.");
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setIsListening(true);
      recognitionRef.current.lang = selectedLanguage;
      recognitionRef.current.start();
    }
  }

  async function handleSend(textToSend, isVoiceInput = false) {
    const query = (textToSend || inputValue).trim();
    if (!query) return;

    const userMsg = {
      id: `usr_${Date.now()}`,
      sender: "user",
      text: query,
      isVoiceInput
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setLoading(true);

    try {
      const resp = await agentApi.sendQuery(query, babyId, selectedModel, selectedLanguage);
      const assistantText = resp.text_card || resp.draft_response || "Clinical guidance processed.";
      const voiceSummary = resp.voice_summary || assistantText;

      const botMsg = {
        id: `bot_${Date.now()}`,
        sender: "assistant",
        text: assistantText,
        voice: voiceSummary,
        modelUsed: resp.model_used || selectedModel,
        isEmergency: resp.is_emergency,
        language: resp.detected_language || selectedLanguage
      };

      setMessages((prev) => [...prev, botMsg]);

      // CRITICAL RULE: Voice output ONLY if user gave voice input
      if (isVoiceInput) {
        speakText(voiceSummary, resp.detected_language || selectedLanguage);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: "assistant",
          text: `⚠️ Error connecting to clinical assistant: ${err.message}. Please consult your pediatrician directly.`,
          isEmergency: false
        }
      ]);
    } finally {
      setLoading(false);
    }
  }

  const SUGGESTIONS = {
    "en-US": [
      "What should I do next?",
      "Safe room temperature",
      `${babyName}'s weight & feeding goal`,
      "Active prescribed drops",
      "Skin-to-skin Kangaroo care tips"
    ],
    "te-IN": [
      "తరువాత ఏమి చేయాలి?",
      "గది ఉష్ణోగ్రత ఎంత ఉండాలి?",
      `${babyName} బరువు మరియు ఫీడింగ్ వివరాలు`,
      "కంగారూ మదర్ కేర్ చిట్కాలు",
      "ప్రమాదకర లక్షణాలు ఏమిటి?"
    ],
    "hi-IN": [
      "अगला कदम क्या होना चाहिए?",
      "कमरे का सुरक्षित तापमान",
      `${babyName} का वजन और दूध की मात्रा`,
      "कंगारू मदर केयर के फायदे",
      "खतरे के लक्षण क्या हैं?"
    ],
    "ta-IN": [
      "அடுத்து நான் என்ன செய்ய வேண்டும்?",
      "அறையின் சரியான வெப்பநிலை",
      `${babyName} எடை மற்றும் பால் அளவு`,
      "கங்காரு தாய் பராமரிப்பு குறிப்புகள்"
    ]
  };

  const currentSuggestions = SUGGESTIONS[selectedLanguage] || SUGGESTIONS["en-US"];

  return (
    <div style={{
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: 60,
      fontFamily: "inherit"
    }}>
      {/* COLLAPSED STATE: Floating Action Buttons on Bottom Right */}
      {!isOpen ? (
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Quick Voice Mic Button (triggers voice input mode) */}
          <button
            type="button"
            onClick={() => {
              setIsOpen(true);
              setTimeout(() => toggleListening(), 300);
            }}
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              background: "#ffffff",
              color: "#0f766e",
              border: "2px solid #0f766e",
              boxShadow: "0 6px 16px rgba(15, 118, 110, 0.25)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              transition: "transform 0.15s ease"
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.05)")}
            onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
            title="Speak to Assistant (Voice Input & Voice Reply)"
          >
            <Mic size={20} />
          </button>

          {/* Expand Chat Bubble */}
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            style={{
              background: "linear-gradient(135deg, #0f766e, #0d9488)",
              color: "white",
              border: "none",
              padding: "12px 20px",
              borderRadius: "30px",
              boxShadow: "0 8px 24px rgba(15, 118, 110, 0.35)",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
              fontWeight: "700",
              fontSize: "14px",
              transition: "transform 0.15s ease"
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.02)")}
            onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
          >
            <Sparkles size={18} fill="white" />
            <span>Ask {babyName}'s Assistant</span>
          </button>
        </div>
      ) : (
        /* EXPANDED POPUP DRAWER (Bottom Right Card) */
        <div style={{
          width: "430px",
          maxWidth: "calc(100vw - 32px)",
          height: "590px",
          maxHeight: "calc(100vh - 80px)",
          background: "#ffffff",
          borderRadius: "18px",
          border: "1px solid #cbd5e1",
          boxShadow: "0 20px 40px -4px rgba(0, 0, 0, 0.25), 0 0 1px rgba(0, 0, 0, 0.1)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          animation: "slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards"
        }}>
          {/* Header Bar */}
          <div style={{
            padding: "14px 18px",
            background: "linear-gradient(135deg, #0f766e, #0d9488)",
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{
                background: "rgba(255,255,255,0.2)",
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}>
                <Sparkles size={16} fill="white" />
              </div>
              <div>
                <div style={{ fontSize: "14px", fontWeight: "700" }}>Baby {babyName}'s Clinical Assistant</div>
                <div style={{ fontSize: "11px", opacity: 0.9 }}>AAP / WHO Grounded Clinical QA</div>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              style={{
                background: "rgba(255,255,255,0.2)",
                border: "none",
                color: "white",
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer"
              }}
              title="Close Chat"
            >
              <X size={16} />
            </button>
          </div>

          {/* Sub Toolbar: Model Selection & Language Option Selector */}
          <div style={{
            padding: "8px 14px",
            background: "#f8fafc",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "11px",
            gap: "8px"
          }}>
            {/* Model Selector */}
            <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <Cpu size={13} color="#64748b" />
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                style={{
                  padding: "3px 6px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "11px",
                  background: "white",
                  outline: "none"
                }}
              >
                <option value="qwen2.5:3b">⚡ Qwen 2.5</option>
                <option value="medgemma1.5:latest">🩺 MedGemma 1.5</option>
              </select>
            </div>

            {/* Language Selector */}
            <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <Globe size={13} color="#0f766e" />
              <select
                value={selectedLanguage}
                onChange={(e) => {
                  setSelectedLanguage(e.target.value);
                  if (recognitionRef.current) {
                    recognitionRef.current.lang = e.target.value;
                  }
                }}
                style={{
                  padding: "3px 8px",
                  borderRadius: "6px",
                  border: "1px solid #0f766e",
                  fontSize: "11px",
                  fontWeight: "600",
                  color: "#0f766e",
                  background: "#f0fdfa",
                  outline: "none",
                  cursor: "pointer"
                }}
                title="Choose conversation and voice language"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.nativeLabel} ({lang.label})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Mode Banner Indicator */}
          <div style={{
            padding: "4px 14px",
            background: "#ecfdf5",
            borderBottom: "1px solid #d1fae5",
            fontSize: "10.5px",
            color: "#065f46",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}>
            <span>🎙️ Speak for Voice Reply • ⌨️ Type for Silent Text Reply</span>
            <span style={{ fontWeight: "700" }}>{LANGUAGES.find(l => l.code === selectedLanguage)?.nativeLabel}</span>
          </div>

          {/* Messages Scroll Feed */}
          <div style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            background: "#ffffff"
          }}>
            {messages.map((m) => {
              const isUser = m.sender === "user";
              return (
                <div
                  key={m.id}
                  style={{
                    display: "flex",
                    justifyContent: isUser ? "flex-end" : "flex-start"
                  }}
                >
                  <div style={{
                    maxWidth: "88%",
                    padding: "11px 15px",
                    borderRadius: "14px",
                    background: isUser ? "#0f766e" : "#f1f5f9",
                    color: isUser ? "#ffffff" : "#0f172a",
                    fontSize: "13px",
                    lineHeight: 1.5,
                    boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                    whiteSpace: "pre-line"
                  }}>
                    {m.isEmergency && (
                      <div style={{
                        background: "#fee2e2",
                        color: "#b91c1c",
                        padding: "6px 8px",
                        borderRadius: "6px",
                        fontWeight: "700",
                        fontSize: "11px",
                        marginBottom: "6px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px"
                      }}>
                        <ShieldAlert size={14} />
                        CLINICAL RED FLAG: CALL HELPLINE
                      </div>
                    )}

                    {m.text}

                    {!isUser && (
                      <div style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginTop: "8px",
                        paddingTop: "6px",
                        borderTop: "1px solid #e2e8f0",
                        fontSize: "11px",
                        color: "#64748b"
                      }}>
                        <span>{m.modelUsed ? `Model: ${m.modelUsed.split(":")[0]}` : "AAP / WHO Verified"}</span>
                        {/* Optional Manual Read-Aloud Button */}
                        <button
                          onClick={() => speakText(m.voice || m.text, m.language || selectedLanguage)}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#0f766e",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "3px",
                            fontSize: "11px",
                            fontWeight: "600"
                          }}
                          title="Click to hear speech output in chosen language"
                        >
                          <Volume2 size={12} /> Play Voice
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#64748b", fontSize: "12px", padding: "6px 10px" }}>
                <Loader2 size={15} className="animate-spin" />
                <span>Thinking in {LANGUAGES.find(l => l.code === selectedLanguage)?.label}...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips */}
          <div style={{
            padding: "8px 12px",
            background: "#f8fafc",
            borderTop: "1px solid #e2e8f0",
            display: "flex",
            gap: "6px",
            overflowX: "auto",
            whiteSpace: "nowrap"
          }}>
            {currentSuggestions.map((s, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(s, false)}
                style={{
                  background: "white",
                  border: "1px solid #cbd5e1",
                  color: "#334155",
                  padding: "4px 9px",
                  borderRadius: "12px",
                  fontSize: "11px",
                  fontWeight: "500",
                  cursor: "pointer",
                  flexShrink: 0
                }}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Bottom Input Area: Text Field & Microphone Button */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(inputValue, false);
            }}
            style={{
              padding: "10px 14px",
              background: "white",
              borderTop: "1px solid #e2e8f0",
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            {/* Microphone button for Voice Input */}
            <button
              type="button"
              onClick={toggleListening}
              style={{
                background: isListening ? "#e11d48" : "#f1f5f9",
                color: isListening ? "white" : "#0f766e",
                border: isListening ? "none" : "1px solid #cbd5e1",
                width: "38px",
                height: "38px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
              className={isListening ? "pulse-listening" : ""}
              title={isListening ? "Listening... click to stop" : "Speak via Microphone (Will speak response aloud)"}
            >
              {isListening ? <MicOff size={16} /> : <Mic size={16} />}
            </button>

            {/* Text input */}
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={isListening ? `Listening (${LANGUAGES.find(l => l.code === selectedLanguage)?.nativeLabel})...` : `Ask in ${LANGUAGES.find(l => l.code === selectedLanguage)?.label}...`}
              style={{
                flex: 1,
                padding: "9px 12px",
                borderRadius: "18px",
                border: isListening ? "2px solid #e11d48" : "1px solid #cbd5e1",
                fontSize: "13px",
                outline: "none"
              }}
            />

            {/* Send button for Text Input */}
            <button
              type="submit"
              disabled={loading || !inputValue.trim()}
              style={{
                background: "#0f766e",
                color: "white",
                border: "none",
                width: "38px",
                height: "38px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: (loading || !inputValue.trim()) ? "not-allowed" : "pointer",
                opacity: (loading || !inputValue.trim()) ? 0.6 : 1
              }}
              title="Send text query (Silent text output)"
            >
              <Send size={15} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}