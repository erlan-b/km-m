import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ListingsRepository {
  ListingsRepository(this._dio);
  final Dio _dio;

  String get _baseUrl => _dio.options.baseUrl.replaceFirst('/api/v1', '');

  String thumbnailUrl(int mediaId) => '$_baseUrl/api/v1/listing-media/$mediaId/thumbnail';
  String fullImageUrl(int mediaId) => '$_baseUrl/api/v1/listing-media/$mediaId/download';

  Future<Map<String, dynamic>> getListings({
    int page = 1,
    int pageSize = 20,
    String? query,
    int? categoryId,
    String? city,
    double? minPrice,
    double? maxPrice,
    String? sortBy,
    String? status,
    String? transactionType,
  }) async {
    final params = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
    };
    if (query != null && query.isNotEmpty) params['q'] = query;
    if (categoryId != null) params['category_id'] = categoryId;
    if (city != null && city.isNotEmpty) params['city'] = city;
    if (minPrice != null) params['min_price'] = minPrice;
    if (maxPrice != null) params['max_price'] = maxPrice;
    if (sortBy != null) params['sort_by'] = sortBy;
    if (status != null) params['status'] = status;
    if (transactionType != null) params['transaction_type'] = transactionType;

    final response = await _dio.get('/listings', queryParameters: params);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getListing(int id) async {
    final response = await _dio.get('/listings/$id');
    return response.data as Map<String, dynamic>;
  }

  Future<List<dynamic>> getListingMedia(int listingId) async {
    final response = await _dio.get('/listing-media/listings/$listingId');
    final data = response.data as Map<String, dynamic>;
    return data['items'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> getMyListings({int page = 1, int pageSize = 20}) async {
    final response = await _dio.get('/listings/my', queryParameters: {'page': page, 'page_size': pageSize});
    return response.data as Map<String, dynamic>;
  }
}

final listingsRepositoryProvider = Provider<ListingsRepository>((ref) {
  return ListingsRepository(ref.read(dioProvider));
});
