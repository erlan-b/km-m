import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/promotions_repository.dart';

class MyPromotionsScreen extends ConsumerStatefulWidget {
  const MyPromotionsScreen({super.key});

  @override
  ConsumerState<MyPromotionsScreen> createState() => _MyPromotionsScreenState();
}

class _MyPromotionsScreenState extends ConsumerState<MyPromotionsScreen> {
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
          .read(promotionsRepositoryProvider)
          .listMyPromotions(page: _page, pageSize: 20);

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

  String _formatDateTime(dynamic raw, {bool withTime = false}) {
    final value = raw?.toString();
    if (value == null || value.isEmpty) {
      return '';
    }

    final date = DateTime.tryParse(value)?.toLocal();
    if (date == null) {
      return '';
    }

    if (withTime) {
      return DateFormat('dd.MM.yyyy HH:mm').format(date);
    }
    return DateFormat('dd.MM.yyyy').format(date);
  }

  String _statusLabel(String status, S l) {
    switch (status) {
      case 'active':
        return l.promotionActive;
      case 'pending':
        return l.promotionPending;
      case 'expired':
        return l.promotionExpired;
      default:
        return status;
    }
  }

  ({Color bg, Color fg}) _statusColors(String status) {
    switch (status) {
      case 'active':
        return (bg: AppTheme.statusSuccessBg, fg: AppTheme.statusSuccess);
      case 'pending':
        return (bg: AppTheme.statusWarningBg, fg: const Color(0xFF8A6A00));
      case 'expired':
        return (bg: AppTheme.bgMuted, fg: AppTheme.textSubtle);
      case 'cancelled':
        return (bg: AppTheme.statusErrorBg, fg: AppTheme.statusError);
      default:
        return (bg: AppTheme.bgMuted, fg: AppTheme.textSubtle);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l.promotions),
        actions: [
          IconButton(
            tooltip: l.paymentHistory,
            onPressed: () => context.push('/payments'),
            icon: const Icon(Icons.receipt_long_outlined),
          ),
        ],
      ),
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
              Icons.local_offer_outlined,
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
          separatorBuilder: (context, index) => const SizedBox(height: 8),
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
            final listingId = (item['listing_id'] as num?)?.toInt();
            final packageId = (item['promotion_package_id'] as num?)?.toInt();
            final status = item['status']?.toString() ?? '';
            final statusColors = _statusColors(status);
            final targetCity = item['target_city']?.toString();
            final targetCategoryId = (item['target_category_id'] as num?)
                ?.toInt();

            final startsAt = _formatDateTime(item['starts_at']);
            final endsAt = _formatDateTime(item['ends_at']);

            final amount = _formatMoney(
              item['purchased_price'],
              item['currency']?.toString() ?? 'KGS',
            );

            return Material(
              color: AppTheme.bgSurface,
              borderRadius: BorderRadius.circular(AppTheme.cardRadius),
              child: InkWell(
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                onTap: listingId == null
                    ? null
                    : () => context.push('/listing/$listingId'),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
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
                              listingId == null
                                  ? l.promotions
                                  : '${l.listingDetail} #$listingId',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 15,
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
                                fontWeight: FontWeight.w700,
                                fontSize: 12,
                                color: statusColors.fg,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        amount,
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        packageId == null
                            ? l.choosePackage
                            : '${l.choosePackage} #$packageId',
                        style: const TextStyle(
                          color: AppTheme.textSubtle,
                          fontSize: 13,
                        ),
                      ),
                      if ((targetCity != null &&
                              targetCity.trim().isNotEmpty) ||
                          targetCategoryId != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          '${l.targetCity}: ${targetCity?.trim().isEmpty == false ? targetCity : '-'}'
                          ' · ${l.targetCategory}: ${targetCategoryId ?? '-'}',
                          style: const TextStyle(
                            color: AppTheme.textSubtle,
                            fontSize: 12,
                          ),
                        ),
                      ],
                      if (startsAt.isNotEmpty || endsAt.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(
                          '$startsAt - $endsAt',
                          style: const TextStyle(
                            color: AppTheme.textSubtle,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
