import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/payments_repository.dart';

class PaymentHistoryScreen extends ConsumerStatefulWidget {
  const PaymentHistoryScreen({super.key});

  @override
  ConsumerState<PaymentHistoryScreen> createState() =>
      _PaymentHistoryScreenState();
}

class _PaymentHistoryScreenState extends ConsumerState<PaymentHistoryScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  int _page = 1;
  int _totalPages = 1;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool append = false}) async {
    if (append && (_loading || _loadingMore)) {
      return;
    }

    setState(() {
      if (append) {
        _loadingMore = true;
      } else {
        _loading = true;
        _error = null;
      }
    });

    try {
      final data = await ref
          .read(paymentsRepositoryProvider)
          .listMyPayments(page: _page, pageSize: 20);

      final rawItems = data['items'];
      final items = rawItems is List
          ? rawItems
                .whereType<Map>()
                .map((item) => Map<String, dynamic>.from(item))
                .toList()
          : <Map<String, dynamic>>[];
      final totalPages = (data['total_pages'] as num?)?.toInt() ?? 0;

      if (!mounted) {
        return;
      }

      setState(() {
        if (append) {
          _items.addAll(items);
        } else {
          _items = items;
        }
        _totalPages = totalPages <= 0 ? 1 : totalPages;
        _loading = false;
        _loadingMore = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  Future<void> _refresh() async {
    _page = 1;
    await _load();
  }

  void _loadMore() {
    if (_loading || _loadingMore || _page >= _totalPages) {
      return;
    }
    _page += 1;
    _load(append: true);
  }

  String _formatMoney(dynamic amount, String currency) {
    final value = amount is num
        ? amount.toDouble()
        : double.tryParse(amount.toString()) ?? 0;
    final wholePart = value.toInt();

    final buffer = StringBuffer();
    final text = wholePart.toString();
    for (var i = 0; i < text.length; i++) {
      if (i > 0 && (text.length - i) % 3 == 0) {
        buffer.write(' ');
      }
      buffer.write(text[i]);
    }
    return '${buffer.toString()} $currency';
  }

  String _formatDateTime(dynamic raw) {
    final value = raw?.toString();
    if (value == null || value.isEmpty) {
      return '';
    }

    final parsed = DateTime.tryParse(value)?.toLocal();
    if (parsed == null) {
      return '';
    }

    return DateFormat('dd.MM.yyyy HH:mm').format(parsed);
  }

  String _statusLabel(String status, S l) {
    switch (status) {
      case 'pending':
        return l.paymentPending;
      case 'successful':
        return l.paymentSuccessful;
      case 'failed':
        return l.paymentFailed;
      default:
        return status;
    }
  }

  ({Color bg, Color fg}) _statusColors(String status) {
    switch (status) {
      case 'pending':
        return (bg: AppTheme.statusWarningBg, fg: const Color(0xFF8A6A00));
      case 'successful':
        return (bg: AppTheme.statusSuccessBg, fg: AppTheme.statusSuccess);
      case 'failed':
        return (bg: AppTheme.statusErrorBg, fg: AppTheme.statusError);
      case 'cancelled':
      case 'refunded':
        return (bg: AppTheme.bgMuted, fg: AppTheme.textSubtle);
      default:
        return (bg: AppTheme.bgMuted, fg: AppTheme.textSubtle);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l.paymentHistory)),
      body: _buildBody(l),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _items.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(l.errorOccurred),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _refresh, child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.receipt_long_outlined,
              size: 56,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(
              l.emptyList,
              style: const TextStyle(color: AppTheme.textSubtle, fontSize: 16),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppTheme.accent,
      child: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification is ScrollEndNotification &&
              notification.metrics.extentAfter < 200) {
            _loadMore();
          }
          return false;
        },
        child: ListView.separated(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 16),
          itemCount: _items.length + (_loadingMore ? 1 : 0),
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            if (index >= _items.length) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Center(
                  child: CircularProgressIndicator(
                    color: AppTheme.accent,
                    strokeWidth: 2,
                  ),
                ),
              );
            }

            final item = _items[index];
            final status = item['status']?.toString() ?? '';
            final statusColors = _statusColors(status);
            final amount = _formatMoney(
              item['amount'],
              item['currency']?.toString() ?? 'KGS',
            );

            final listingId = (item['listing_id'] as num?)?.toInt();
            final promotionId = (item['promotion_id'] as num?)?.toInt();
            final provider = item['payment_provider']?.toString() ?? 'mock';

            final createdAt = _formatDateTime(item['created_at']);
            final paidAt = _formatDateTime(item['paid_at']);

            return Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.bgSurface,
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          amount,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 9,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          color: statusColors.bg,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          _statusLabel(status, l),
                          style: TextStyle(
                            color: statusColors.fg,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    provider.toUpperCase(),
                    style: const TextStyle(
                      color: AppTheme.textSubtle,
                      fontSize: 13,
                    ),
                  ),
                  if (listingId != null || promotionId != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      '${l.listingDetail}: ${listingId ?? '-'} · ${l.promotions}: ${promotionId ?? '-'}',
                      style: const TextStyle(
                        color: AppTheme.textSubtle,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  if (createdAt.isNotEmpty || paidAt.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        if (createdAt.isNotEmpty) ...[
                          const Icon(
                            Icons.schedule,
                            size: 14,
                            color: AppTheme.textSubtle,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            createdAt,
                            style: const TextStyle(
                              color: AppTheme.textSubtle,
                              fontSize: 11,
                            ),
                          ),
                        ],
                        if (paidAt.isNotEmpty) ...[
                          const SizedBox(width: 10),
                          const Icon(
                            Icons.check_circle_outline,
                            size: 14,
                            color: AppTheme.textSubtle,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            paidAt,
                            style: const TextStyle(
                              color: AppTheme.textSubtle,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
