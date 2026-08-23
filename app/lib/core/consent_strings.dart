/// User-facing consent copy. Keep versioned when this wording changes.
class ConsentStrings {
  ConsentStrings._();

  static const String version = '1.0';
  static const String title = 'Before You Start';
  static const String subtitle =
      'Please read and provide your consent for this screening.';
  static const String whatWillHappen = 'What will happen?';
  static const List<String> steps = [
    'We will use your smartphone camera to capture an image of your eye or inner eyelid.',
    'The image will be analyzed by computer vision and an AI model to produce an estimated haemoglobin level.',
    'The result is a screening estimate only.',
    'This result does not replace a blood test or a medical diagnosis.',
    'If the image quality is poor or the required eye region cannot be identified, the screening may not provide a result.',
    'You may stop the screening at any time before submitting the image.',
  ];
  static const String dataUse =
      'Your image may be processed by the application and backend to perform the screening analysis.';
  static const String important = 'Important';
  static const String disclaimer =
      'This screening provides an estimated haemoglobin level. It is not a medical diagnosis and should not be used as a substitute for professional medical advice or a confirmatory blood test.';
  static const String agree =
      'I understand the above information and agree to continue with the screening.';
  static const String continueLabel = 'Continue';
}
