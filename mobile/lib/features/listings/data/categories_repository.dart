import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class CategoriesRepository {
  CategoriesRepository(this._dio);
  final Dio _dio;

  Future<List<dynamic>> getCategories({bool? activeOnly}) async {
    final params = <String, dynamic>{};
    if (activeOnly == true) params['active_only'] = true;
    final response = await _dio.get('/categories', queryParameters: params);
    final data = response.data as Map<String, dynamic>;
    return data['items'] as List<dynamic>;
  }
}

final categoriesRepositoryProvider = Provider<CategoriesRepository>((ref) {
  return CategoriesRepository(ref.read(dioProvider));
});
