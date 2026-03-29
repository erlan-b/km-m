import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class NotificationsRepository {
  NotificationsRepository(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> listNotifications({
    int page = 1,
    int pageSize = 20,
    bool unreadOnly = false,
  }) async {
    final response = await _dio.get(
      '/notifications',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        'unread_only': unreadOnly,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getUnreadCount() async {
    final response = await _dio.get('/notifications/unread-count');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> markAsRead(int notificationId) async {
    final response = await _dio.post('/notifications/$notificationId/read');
    return response.data as Map<String, dynamic>;
  }
}

final notificationsRepositoryProvider = Provider<NotificationsRepository>((
  ref,
) {
  return NotificationsRepository(ref.read(dioProvider));
});
