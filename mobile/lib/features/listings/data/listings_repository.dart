import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ListingsRepository {
  ListingsRepository(this._dio);
  final Dio _dio;

  String get _baseUrl => _dio.options.baseUrl.replaceFirst('/api/v1', '');

  String thumbnailUrl(int mediaId) =>
      '$_baseUrl/api/v1/listing-media/$mediaId/thumbnail';
  String fullImageUrl(int mediaId) =>
      '$_baseUrl/api/v1/listing-media/$mediaId/download';

  String absoluteUrl(String relativeOrAbsolutePath) {
    if (relativeOrAbsolutePath.startsWith('http://') ||
        relativeOrAbsolutePath.startsWith('https://')) {
      return relativeOrAbsolutePath;
    }
    if (relativeOrAbsolutePath.startsWith('/')) {
      return '$_baseUrl$relativeOrAbsolutePath';
    }
    return '$_baseUrl/$relativeOrAbsolutePath';
  }

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
    final params = <String, dynamic>{'page': page, 'page_size': pageSize};
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

  Future<List<dynamic>> getMyListingMedia(int listingId) async {
    final response = await _dio.get('/listing-media/listings/$listingId/my');
    final data = response.data as Map<String, dynamic>;
    return data['items'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> getMyListings({
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _dio.get(
      '/listings/my',
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createListing(
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.post('/listings', data: payload);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateListing(
    int listingId,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.patch('/listings/$listingId', data: payload);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateListingStatus(
    int listingId,
    String action,
  ) async {
    final response = await _dio.patch(
      '/listings/$listingId/status',
      data: {'action': action},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> archiveListing(int listingId) async {
    final response = await _dio.delete('/listings/$listingId');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> restoreListing(int listingId) async {
    final response = await _dio.post('/listings/$listingId/restore');
    return response.data as Map<String, dynamic>;
  }

  Future<void> hardDeleteListing(int listingId) async {
    await _dio.delete('/listings/$listingId/hard');
  }

  Future<List<dynamic>> uploadListingMedia({
    required int listingId,
    required List<String> filePaths,
  }) async {
    final formData = FormData();
    for (final filePath in filePaths) {
      final fileName = filePath.split(RegExp(r'[\\/]+')).last;
      formData.files.add(
        MapEntry(
          'files',
          await MultipartFile.fromFile(filePath, filename: fileName),
        ),
      );
    }

    final response = await _dio.post(
      '/listing-media/listings/$listingId/upload',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    final data = response.data as Map<String, dynamic>;
    return data['items'] as List<dynamic>;
  }

  Future<void> deleteListingMedia(int mediaId) async {
    await _dio.delete('/listing-media/$mediaId');
  }
}

final listingsRepositoryProvider = Provider<ListingsRepository>((ref) {
  return ListingsRepository(ref.read(dioProvider));
});
