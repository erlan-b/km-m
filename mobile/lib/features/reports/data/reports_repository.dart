import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ReportsRepository {
  ReportsRepository(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> createReport({
    required String targetType,
    required int targetId,
    required String reasonCode,
    String? reasonText,
  }) async {
    final payload = <String, dynamic>{
      'target_type': targetType,
      'target_id': targetId,
      'reason_code': reasonCode,
      'reason_text': reasonText,
    };

    final response = await _dio.post('/reports', data: payload);
    return response.data as Map<String, dynamic>;
  }
}

final reportsRepositoryProvider = Provider<ReportsRepository>((ref) {
  return ReportsRepository(ref.read(dioProvider));
});
