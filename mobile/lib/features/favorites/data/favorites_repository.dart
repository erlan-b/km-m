import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class FavoritesRepository {
  FavoritesRepository(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> listFavorites({
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _dio.get(
      '/favorites',
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> addFavorite(int listingId) async {
    final response = await _dio.post('/favorites/$listingId');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> removeFavorite(int listingId) async {
    final response = await _dio.delete('/favorites/$listingId');
    return response.data as Map<String, dynamic>;
  }

  Future<Set<int>> fetchFavoriteIds({
    int pageSize = 100,
    int maxPages = 10,
  }) async {
    final result = <int>{};
    var page = 1;

    while (page <= maxPages) {
      final data = await listFavorites(page: page, pageSize: pageSize);
      final items = data['items'];
      if (items is! List || items.isEmpty) {
        break;
      }

      for (final raw in items) {
        if (raw is Map && raw['id'] is num) {
          result.add((raw['id'] as num).toInt());
        }
      }

      final totalPages = (data['total_pages'] as num?)?.toInt() ?? 0;
      if (totalPages == 0 || page >= totalPages) {
        break;
      }
      page += 1;
    }

    return result;
  }
}

final favoritesRepositoryProvider = Provider<FavoritesRepository>((ref) {
  return FavoritesRepository(ref.read(dioProvider));
});
