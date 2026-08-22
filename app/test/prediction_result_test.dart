import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:anaemia_screening_app/services/api_service.dart';
import 'package:anaemia_screening_app/services/screening_history_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Fixtures mirror the REAL backend response schema documented in
/// backend/API_DOCUMENTATION.md and captured in END_TO_END_TEST.md.
/// Values below are the actual model outputs from a real inference run.
void main() {
  group('PredictionResult.fromJson — real backend payloads', () {
    test('parses PREDICTION_COMPLETE with all real fields', () {
      final json = jsonDecode('''
      {
        "success": true,
        "status": "PREDICTION_COMPLETE",
        "data": {
          "estimated_hb_g_dl": 6.366367340087891,
          "hb_std_g_dl": 0.6795263290405273,
          "confidence_interval_95": [5.03, 7.7],
          "confidence_status": "MEDIUM_CONFIDENCE",
          "image_quality": {
            "status": "GOOD",
            "score": 0.8243265262401682,
            "failure_reasons": []
          },
          "roi": {"status": "VALID"},
          "recommendation": "Screening estimate only. Consider confirmatory testing when appropriate.",
          "model": {"name": "MobileNetV3-small", "version": "anaemia-hb-mobilenetv3-v1"}
        },
        "meta": {"inference_seconds": 2.1888}
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);

      expect(result.success, isTrue);
      expect(result.status, PredictionStatus.predictionComplete);
      expect(result.data, isNotNull);
      expect(result.data!.estimatedHb, closeTo(6.366367340087891, 1e-9));
      expect(result.data!.hbStd, closeTo(0.6795263290405273, 1e-9));
      expect(result.data!.confidenceInterval95, [5.03, 7.7]);
      expect(result.data!.confidenceStatus, 'MEDIUM_CONFIDENCE');
      expect(result.data!.quality.status, 'GOOD');
      expect(result.data!.quality.score, closeTo(0.8243265262401682, 1e-9));
      expect(result.data!.roiStatus, 'VALID');
      expect(result.data!.recommendation,
          'Screening estimate only. Consider confirmatory testing when appropriate.');
      expect(result.data!.model.name, 'MobileNetV3-small');
      expect(result.data!.model.version, 'anaemia-hb-mobilenetv3-v1');
      expect(result.canRetryUpload, isFalse);
    });

    test('parses LOW_CONFIDENCE success payload', () {
      final json = jsonDecode('''
      {
        "success": true,
        "status": "LOW_CONFIDENCE",
        "data": {
          "estimated_hb_g_dl": 9.1,
          "hb_std_g_dl": 2.4,
          "confidence_interval_95": [4.4, 13.8],
          "confidence_status": "LOW_CONFIDENCE",
          "image_quality": {"status": "GOOD", "score": 0.7, "failure_reasons": []},
          "roi": {"status": "VALID"},
          "recommendation": "Screening estimate only.",
          "model": {"name": "MobileNetV3-small", "version": "anaemia-hb-mobilenetv3-v1"}
        }
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.status, PredictionStatus.lowConfidence);
      expect(result.data, isNotNull);
      expect(result.data!.confidenceStatus, 'LOW_CONFIDENCE');
    });

    test('parses ROI_FAILED failure payload', () {
      final json = jsonDecode('''
      {
        "success": false,
        "status": "ROI_FAILED",
        "data": {
          "retry": true,
          "message": "A valid conjunctiva ROI mask is required for prediction."
        }
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.success, isFalse);
      expect(result.status, PredictionStatus.roiFailed);
      expect(result.data, isNull);
      expect(result.message,
          'A valid conjunctiva ROI mask is required for prediction.');
    });

    test('parses IMAGE_QUALITY_FAILED with failure reasons', () {
      final json = jsonDecode('''
      {
        "success": false,
        "status": "IMAGE_QUALITY_FAILED",
        "data": {
          "retry": true,
          "message": "Please capture a clearer image.",
          "failure_reasons": ["too_blurry", "too_dark"]
        }
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.status, PredictionStatus.imageQualityFailed);
      expect(result.data, isNull);
      expect(result.message, 'Please capture a clearer image.');
    });

    test('parses MODEL_NOT_READY payload', () {
      final json = jsonDecode('''
      {
        "success": false,
        "status": "MODEL_NOT_READY",
        "data": {
          "retry": true,
          "message": "The AI screening model is not currently available."
        }
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.status, PredictionStatus.modelNotReady);
      expect(result.data, isNull);
    });

    test('parses INFERENCE_ERROR as retryable', () {
      final json = jsonDecode('''
      {
        "success": false,
        "status": "INFERENCE_ERROR",
        "data": {"retry": false, "message": "Inference failed. Please try again."}
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.status, PredictionStatus.inferenceError);
      expect(result.canRetryUpload, isTrue);
    });

    test('parses VALIDATION_ERROR payload', () {
      final json = jsonDecode('''
      {
        "success": false,
        "status": "VALIDATION_ERROR",
        "message": "Unsupported file format. Please upload a JPG, PNG, or WebP image."
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.status, PredictionStatus.validationError);
      expect(result.data, isNull);
    });

    test('missing estimated_hb in success payload yields no data', () {
      final json = jsonDecode('''
      {"success": true, "status": "PREDICTION_COMPLETE", "data": {}}
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      expect(result.data, isNull);
    });
  });

  group('ScreeningHistoryService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('addFromResult stores real fields and getAll returns them', () async {
      final json = jsonDecode('''
      {
        "success": true,
        "status": "PREDICTION_COMPLETE",
        "data": {
          "estimated_hb_g_dl": 6.37,
          "hb_std_g_dl": 0.68,
          "confidence_interval_95": [5.03, 7.7],
          "confidence_status": "MEDIUM_CONFIDENCE",
          "image_quality": {"status": "GOOD", "score": 0.82, "failure_reasons": []},
          "roi": {"status": "VALID"},
          "recommendation": "Screening estimate only.",
          "model": {"name": "MobileNetV3-small", "version": "anaemia-hb-mobilenetv3-v1"}
        }
      }
      ''') as Map<String, dynamic>;

      final result = PredictionResult.fromJson(json);
      await ScreeningHistoryService.instance.addFromResult(result);

      final records = await ScreeningHistoryService.instance.getAll();
      expect(records.length, 1);
      expect(records.first.estimatedHb, closeTo(6.37, 1e-9));
      expect(records.first.hbStd, closeTo(0.68, 1e-9));
      expect(records.first.confidenceStatus, 'MEDIUM_CONFIDENCE');
      expect(records.first.modelVersion, 'anaemia-hb-mobilenetv3-v1');
    });

    test('clear removes all records', () async {
      final json = jsonDecode('''
      {
        "success": true,
        "status": "PREDICTION_COMPLETE",
        "data": {
          "estimated_hb_g_dl": 7.0,
          "hb_std_g_dl": 0.5,
          "confidence_interval_95": [6.0, 8.0],
          "confidence_status": "HIGH_CONFIDENCE",
          "image_quality": {"status": "GOOD", "score": 0.9, "failure_reasons": []},
          "roi": {"status": "VALID"},
          "recommendation": "Screening estimate only.",
          "model": {"name": "MobileNetV3-small", "version": "anaemia-hb-mobilenetv3-v1"}
        }
      }
      ''') as Map<String, dynamic>;

      await ScreeningHistoryService.instance
          .addFromResult(PredictionResult.fromJson(json));
      await ScreeningHistoryService.instance.clear();

      final records = await ScreeningHistoryService.instance.getAll();
      expect(records, isEmpty);
    });
  });
}