import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class PromotionsRepository {
  PromotionsRepository(this._dio);

  final Dio _dio;

  Future<List<Map<String, dynamic>>> listPromotionPackages() async {
    final response = await _dio.get('/promotions/packages');
    final data = response.data as Map<String, dynamic>;
    final items = data['items'];
    if (items is! List) {
      return <Map<String, dynamic>>[];
    }

    return items
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<Map<String, dynamic>> purchasePromotion({
    required int listingId,
    required int promotionPackageId,
    String? targetCity,
    int? targetCategoryId,
  }) async {
    final payload = <String, dynamic>{
      'listing_id': listingId,
      'promotion_package_id': promotionPackageId,
      'target_city': targetCity,
      'target_category_id': targetCategoryId,
    };

    final response = await _dio.post('/promotions/purchase', data: payload);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listMyPromotions({
    int page = 1,
    int pageSize = 20,
    String? statusFilter,
  }) async {
    final query = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
      if (statusFilter != null && statusFilter.isNotEmpty)
        'status_filter': statusFilter,
    };

    final response = await _dio.get('/promotions/my', queryParameters: query);
    return response.data as Map<String, dynamic>;
  }
}

final promotionsRepositoryProvider = Provider<PromotionsRepository>((ref) {
  return PromotionsRepository(ref.read(dioProvider));
});
