import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class PublicUsersRepository {
  PublicUsersRepository(this._dio);
  final Dio _dio;

  Future<Map<String, dynamic>> getPublicUser(int userId) async {
    final response = await _dio.get('/public/users/$userId');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getUserListings(int userId, {int page = 1, int pageSize = 20}) async {
    final response = await _dio.get('/public/users/$userId/listings', queryParameters: {'page': page, 'page_size': pageSize});
    return response.data as Map<String, dynamic>;
  }
}

final publicUsersRepositoryProvider = Provider<PublicUsersRepository>((ref) {
  return PublicUsersRepository(ref.read(dioProvider));
});
