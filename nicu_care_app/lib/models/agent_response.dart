import 'dart:convert';
import 'dart:typed_data';

class AgentResponse {
  final String textCard;
  final String voiceSummary;
  final bool isEmergency;
  final String detectedLanguage;
  final String intent;
  final bool wikiUpdated;
  final int? nextReminderMinutes;
  final Uint8List? audioBytes;

  AgentResponse({
    required this.textCard,
    required this.voiceSummary,
    required this.isEmergency,
    required this.detectedLanguage,
    required this.intent,
    required this.wikiUpdated,
    this.nextReminderMinutes,
    this.audioBytes,
  });

  factory AgentResponse.fromJson(Map<String, dynamic> json, {Uint8List? audio}) {
    return AgentResponse(
      textCard: json['text_card'] ?? 'No response content.',
      voiceSummary: json['voice_summary'] ?? '',
      isEmergency: json['is_emergency'] ?? false,
      detectedLanguage: json['detected_language'] ?? 'en-US',
      intent: json['intent'] ?? 'CLINICAL_QA',
      wikiUpdated: json['wiki_updated'] ?? false,
      nextReminderMinutes: json['next_reminder_minutes'],
      audioBytes: audio ?? (json['audio_base64'] != null ? base64Decode(json['audio_base64']) : null),
    );
  }
}
