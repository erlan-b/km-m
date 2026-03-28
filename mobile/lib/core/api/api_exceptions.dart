class ApiException implements Exception {
  ApiException({required this.statusCode, required this.message, this.detail});

  final int statusCode;
  final String message;
  final String? detail;

  @override
  String toString() => 'ApiException($statusCode): $message';

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isConflict => statusCode == 409;
  bool get isValidationError => statusCode == 422;
}
