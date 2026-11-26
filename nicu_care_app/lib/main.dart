import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'models/agent_response.dart';
import 'models/hospital_contact.dart';
import 'services/voice_assistant_service.dart';

void main() {
  runApp(const NICUCareApp());
}

class NICUCareApp extends StatelessWidget {
  const NICUCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NICU Baby Care Companion',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00897B),
          primary: const Color(0xFF00897B),
          secondary: const Color(0xFFFF7043),
          error: const Color(0xFFD32F2F),
        ),
        useMaterial3: true,
        fontFamily: 'sans-serif',
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final VoiceAssistantService _voiceService = VoiceAssistantService();
  final TextEditingController _textController = TextEditingController();

  final String _babyId = "baby_liam_01";
  bool _isRecording = false;
  bool _isLoading = false;
  AgentResponse? _latestResponse;

  HospitalEmergencyContact _hospitalContact = HospitalEmergencyContact(
    hospitalName: "BirthRight by Rainbow Children's Hospital",
    branchLocation: "Currency Nagar, Vijayawada, Andhra Pradesh",
    emergencyPhone: "+91 866 666 9000",
    nicuHelpline: "+91 866 669 0000",
    ambulancePhone: "0866-2459999",
    fullAddress: "Opp. Dr. Ramesh Hospitals, ITI Road, Currency Nagar, Vijayawada - 520008",
    googleMapsUrl: "https://maps.google.com/?q=Rainbow+Childrens+Hospital+Vijayawada",
    isVerified: true,
  );

  Future<void> _handleTextSubmit(String text) async {
    if (text.trim().isEmpty) return;
    setState(() => _isLoading = true);
    _textController.clear();

    try {
      final res = await _voiceService.sendTextQuery(text, _babyId);
      setState(() => _latestResponse = res);

      if (res.isEmergency) {
        _showEmergencyDialog(res);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error contacting assistant: $e")),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showEmergencyDialog(AgentResponse res) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFFFFEBEE),
        title: Row(
          children: const [
            Icon(Icons.warning_amber_rounded, color: Colors.red, size: 30),
            SizedBox(width: 8),
            Text("URGENT ATTENTION", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(res.textCard),
            const SizedBox(height: 16),
            const Text(
              "Immediate hospital action is required. Please call emergency dispatch or the 24/7 NICU Helpline:",
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
                minimumSize: const Size.fromHeight(46),
              ),
              icon: const Icon(Icons.phone_in_talk),
              label: Text("CALL NICU: ${_hospitalContact.nicuHelpline}"),
              onPressed: () => launchUrl(Uri.parse("tel:${_hospitalContact.nicuHelpline}")),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.red[900],
                minimumSize: const Size.fromHeight(42),
              ),
              icon: const Icon(Icons.local_hospital),
              label: const Text("DIAL NATIONAL EMERGENCY (108)"),
              onPressed: () => launchUrl(Uri.parse("tel:108")),
            ),
          ],
        ),
        actions: [
          TextButton(
            child: const Text("CLOSE ALERT"),
            onPressed: () => Navigator.pop(ctx),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("👶 Liam's Care Companion", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Theme.of(context).colorScheme.primary,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.emergency_share, color: Colors.amberAccent),
            tooltip: "Hospital Emergency Numbers",
            onPressed: () => _showHospitalDirectoryDialog(),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Corrected Gestational Age Banner
            Card(
              color: const Color(0xFFE0F2F1),
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Row(
                  children: [
                    const CircleAvatar(
                      backgroundColor: Color(0xFF00897B),
                      foregroundColor: Colors.white,
                      child: Icon(Icons.child_care),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: const [
                          Text("Baby Liam (Born 29w+2d Preterm)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                          SizedBox(height: 3),
                          Text("Chronological: 8 weeks | Corrected Age: 0 weeks (Term)", style: TextStyle(fontSize: 13, color: Colors.black87)),
                          Text("Target: 150–180 mL/kg/day (AAP Preterm Protocol)", style: TextStyle(fontSize: 12, color: Color(0xFF00695C), fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Emergency Hospital Banner
            Card(
              color: const Color(0xFFFFF3E0),
              elevation: 1,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: ListTile(
                leading: const Icon(Icons.local_hospital, color: Colors.deepOrange),
                title: Text(_hospitalContact.hospitalName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                subtitle: Text("24/7 NICU: ${_hospitalContact.nicuHelpline} | Vijayawada"),
                trailing: IconButton(
                  icon: const Icon(Icons.phone, color: Colors.deepOrange),
                  onPressed: () => launchUrl(Uri.parse("tel:${_hospitalContact.emergencyPhone}")),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Active Care Response Card
            if (_isLoading)
              const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()))
            else if (_latestResponse != null)
              _buildResponseCard(_latestResponse!),

            const SizedBox(height: 24),

            // Text Query Input
            TextField(
              controller: _textController,
              decoration: InputDecoration(
                hintText: "Ask advice or log: 'Baby drank 50 ml milk'...",
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: () => _handleTextSubmit(_textController.text),
                ),
              ),
              onSubmitted: _handleTextSubmit,
            ),
            const SizedBox(height: 20),

            // Quick Preset Suggestions
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.restaurant, size: 16),
                  label: const Text("Logged 50 mL milk"),
                  onPressed: () => _handleTextSubmit("Logged 50 mL fortified breast milk at 10 AM, baby drank well"),
                ),
                ActionChip(
                  avatar: const Icon(Icons.opacity, size: 16),
                  label: const Text("Changed diaper"),
                  onPressed: () => _handleTextSubmit("Changed diaper: wet with yellow seedy stool"),
                ),
                ActionChip(
                  avatar: const Icon(Icons.favorite, size: 16),
                  label: const Text("Kangaroo Care?"),
                  onPressed: () => _handleTextSubmit("How to safely practice kangaroo mother care skin to skin?"),
                ),
                ActionChip(
                  avatar: const Icon(Icons.warning, size: 16, color: Colors.red),
                  label: const Text("Test Emergency"),
                  onPressed: () => _handleTextSubmit("Baby's lips look blue and chest is retracting under ribs"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResponseCard(AgentResponse res) {
    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(
        side: BorderSide(
          color: res.isEmergency ? Colors.red : const Color(0xFF00897B),
          width: res.isEmergency ? 2 : 1,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  res.isEmergency ? Icons.warning_rounded : Icons.check_circle_rounded,
                  color: res.isEmergency ? Colors.red : const Color(0xFF00897B),
                ),
                const SizedBox(width: 8),
                Text(
                  res.isEmergency ? "CRITICAL CLINICAL ALERT" : "CARE GUIDANCE: ${res.intent}",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: res.isEmergency ? Colors.red : const Color(0xFF00897B),
                  ),
                ),
              ],
            ),
            const Divider(),
            Text(res.textCard, style: const TextStyle(fontSize: 15, height: 1.4)),
            if (res.voiceSummary.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.blueGrey[50],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.record_voice_over, color: Color(0xFF00897B), size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        "Spoken Note: \"${res.voiceSummary}\"",
                        style: const TextStyle(fontStyle: FontStyle.italic, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (res.nextReminderMinutes != null) ...[
              const SizedBox(height: 8),
              Text(
                "⏰ Next Feed Reminder: In ${res.nextReminderMinutes} minutes",
                style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFFE65100)),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _showHospitalDirectoryDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("🏥 Emergency Directory"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_hospitalContact.hospitalName, style: const TextStyle(fontWeight: FontWeight.bold)),
            Text(_hospitalContact.branchLocation),
            const SizedBox(height: 12),
            Text("🚨 General Emergency: ${_hospitalContact.emergencyPhone}"),
            Text("🍼 24/7 NICU Helpline: ${_hospitalContact.nicuHelpline}"),
            Text("🚑 Ambulance: ${_hospitalContact.ambulancePhone}"),
            const SizedBox(height: 12),
            Text("📍 Address: ${_hospitalContact.fullAddress}", style: const TextStyle(fontSize: 12)),
          ],
        ),
        actions: [
          TextButton(
            child: const Text("DIRECTIONS"),
            onPressed: () => launchUrl(Uri.parse(_hospitalContact.googleMapsUrl)),
          ),
          ElevatedButton(
            child: const Text("CALL NICU"),
            onPressed: () => launchUrl(Uri.parse("tel:${_hospitalContact.nicuHelpline}")),
          ),
        ],
      ),
    );
  }
}
