import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ListingsRepository {
  ListingsRepository(this._dio);
  final Dio _dio;

  String get _baseUrl => _dio.options.baseUrl.replaceFirst('/api/v1', '');
  final Map<int, String?> _thumbnailUrlCache = <int, String?>{};
  final Map<int, Future<String?>> _thumbnailInFlight = <int, Future<String?>>{};

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

  String? _normalizeUrl(dynamic rawUrl) {
    final value = rawUrl?.toString().trim();
    if (value == null || value.isEmpty) {
      return null;
    }
    return absoluteUrl(value);
  }

  String? extractThumbnailUrl(Map<String, dynamic> listing) {
    final directCandidates = <dynamic>[
      listing['thumbnail_url'],
      listing['primary_thumbnail_url'],
      listing['primary_media_thumbnail_url'],
      listing['cover_thumbnail_url'],
      listing['image_url'],
    ];

    for (final candidate in directCandidates) {
      final normalized = _normalizeUrl(candidate);
      if (normalized != null) {
        return normalized;
      }
    }

    final media = listing['media'];
    if (media is List) {
      for (final rawItem in media) {
        if (rawItem is! Map) {
          continue;
        }
        final item = Map<String, dynamic>.from(rawItem);
        final normalized = _normalizeUrl(
          item['thumbnail_url'] ?? item['file_url'] ?? item['url'],
        );
        if (normalized != null) {
          return normalized;
        }
      }
    }

    return null;
  }

  Future<String?> _fetchPrimaryThumbnailUrl(int listingId) async {
    try {
      final media = await getListingMedia(listingId);
      for (final rawItem in media) {
        if (rawItem is! Map) {
          continue;
        }
        final item = Map<String, dynamic>.from(rawItem);
        final normalized = _normalizeUrl(
          item['thumbnail_url'] ?? item['file_url'],
        );
        if (normalized != null) {
          _thumbnailUrlCache[listingId] = normalized;
          return normalized;
        }
      }
      _thumbnailUrlCache[listingId] = null;
      return null;
    } catch (_) {
      return null;
    } finally {
      _thumbnailInFlight.remove(listingId);
    }
  }

  Future<String?> getPrimaryThumbnailUrl(int listingId) {
    if (_thumbnailUrlCache.containsKey(listingId)) {
      return Future<String?>.value(_thumbnailUrlCache[listingId]);
    }

    final inFlight = _thumbnailInFlight[listingId];
    if (inFlight != null) {
      return inFlight;
    }

    final request = _fetchPrimaryThumbnailUrl(listingId);
    _thumbnailInFlight[listingId] = request;
    return request;
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
