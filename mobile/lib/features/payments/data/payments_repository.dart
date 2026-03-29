import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class PaymentsRepository {
  PaymentsRepository(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> listMyPayments({
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

    final response = await _dio.get('/payments/me', queryParameters: query);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createPayment({
    int? listingId,
    int? promotionId,
    required Object amount,
    required String currency,
    String paymentProvider = 'mock',
    String? description,
  }) async {
    final payload = <String, dynamic>{
      'listing_id': listingId,
      'promotion_id': promotionId,
      'amount': amount,
      'currency': currency,
      'payment_provider': paymentProvider,
      'description': description,
    };

    final response = await _dio.post('/payments', data: payload);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> confirmPayment(
    int paymentId, {
    String? providerReference,
  }) async {
    final response = await _dio.post(
      '/payments/$paymentId/confirm',
      data: {'provider_reference': providerReference},
    );
    return response.data as Map<String, dynamic>;
  }
}

final paymentsRepositoryProvider = Provider<PaymentsRepository>((ref) {
  return PaymentsRepository(ref.read(dioProvider));
});
