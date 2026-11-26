class HospitalEmergencyContact {
  final String hospitalName;
  final String branchLocation;
  final String emergencyPhone;
  final String nicuHelpline;
  final String ambulancePhone;
  final String fullAddress;
  final String googleMapsUrl;
  final bool isVerified;

  HospitalEmergencyContact({
    required this.hospitalName,
    required this.branchLocation,
    required this.emergencyPhone,
    required this.nicuHelpline,
    required this.ambulancePhone,
    required this.fullAddress,
    required this.googleMapsUrl,
    required this.isVerified,
  });

  factory HospitalEmergencyContact.fromJson(Map<String, dynamic> json) {
    return HospitalEmergencyContact(
      hospitalName: json['hospital_name'] ?? 'Discharge Hospital',
      branchLocation: json['branch_location'] ?? '',
      emergencyPhone: json['emergency_phone'] ?? '108',
      nicuHelpline: json['nicu_helpline'] ?? json['emergency_phone'] ?? '108',
      ambulancePhone: json['ambulance_phone'] ?? '108',
      fullAddress: json['full_address'] ?? '',
      googleMapsUrl: json['google_maps_url'] ?? '',
      isVerified: json['is_verified'] ?? false,
    );
  }
}

