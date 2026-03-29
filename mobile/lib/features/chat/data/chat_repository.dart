import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ChatRepository {
  ChatRepository(this._dio);

  final Dio _dio;

  String get _baseUrl => _dio.options.baseUrl.replaceFirst('/api/v1', '');

  String attachmentDownloadUrl(int attachmentId) =>
      '$_baseUrl/api/v1/attachments/$attachmentId/download';

  Future<Map<String, dynamic>> listConversations({
    int page = 1,
    int pageSize = 20,
    int? listingId,
  }) async {
    final params = <String, dynamic>{'page': page, 'page_size': pageSize};
    if (listingId != null) {
      params['listing_id'] = listingId;
    }

    final response = await _dio.get('/conversations', queryParameters: params);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> openConversationForListing(int listingId) async {
    final response = await _dio.post(
      '/conversations',
      data: {'listing_id': listingId},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getConversation(int conversationId) async {
    final response = await _dio.get('/conversations/$conversationId');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listMessages({
    required int conversationId,
    int page = 1,
    int pageSize = 30,
    bool markRead = true,
  }) async {
    final response = await _dio.get(
      '/messages',
      queryParameters: {
        'conversation_id': conversationId,
        'page': page,
        'page_size': pageSize,
        'mark_read': markRead,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> sendTextMessage({
    required int conversationId,
    required String textBody,
  }) async {
    final response = await _dio.post(
      '/messages/text',
      data: {'conversation_id': conversationId, 'text_body': textBody.trim()},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> sendMessageWithAttachments({
    required int conversationId,
    String? textBody,
    required List<String> filePaths,
  }) async {
    final normalizedText = textBody?.trim();

    final formData = FormData();
    formData.fields.add(MapEntry('conversation_id', '$conversationId'));
    if (normalizedText != null && normalizedText.isNotEmpty) {
      formData.fields.add(MapEntry('text_body', normalizedText));
    }

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
      '/messages',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Uint8List> downloadAttachmentBytes(int attachmentId) async {
    final response = await _dio.get<List<int>>(
      '/attachments/$attachmentId/download',
      options: Options(responseType: ResponseType.bytes),
    );
    final bytes = response.data ?? const <int>[];
    return Uint8List.fromList(bytes);
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.read(dioProvider));
});
