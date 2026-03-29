import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/notifications_repository.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
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
          .read(notificationsRepositoryProvider)
          .listNotifications(page: _page, pageSize: 20);

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

  String _timeLabel(Map<String, dynamic> item) {
    final raw = item['created_at']?.toString();
    if (raw == null || raw.isEmpty) {
      return '';
    }

    final parsed = DateTime.tryParse(raw);
    if (parsed == null) {
      return '';
    }

    return DateFormat('dd.MM HH:mm').format(parsed.toLocal());
  }

  Future<void> _markAsRead(Map<String, dynamic> item) async {
    final id = (item['id'] as num?)?.toInt();
    if (id == null) {
      return;
    }

    if (item['is_read'] == true) {
      return;
    }

    try {
      final updated = await ref
          .read(notificationsRepositoryProvider)
          .markAsRead(id);
      if (!mounted) {
        return;
      }

      setState(() {
        _items = _items.map((current) {
          if (current['id'] == id) {
            return Map<String, dynamic>.from(updated);
          }
          return current;
        }).toList();
      });
    } catch (_) {}
  }

  Future<void> _openNotification(Map<String, dynamic> item) async {
    await _markAsRead(item);

    final entityType = item['related_entity_type']?.toString();
    final entityId = (item['related_entity_id'] as num?)?.toInt();
    if (entityId == null || !mounted) {
      return;
    }

    if (entityType == 'listing') {
      context.push('/listing/$entityId');
      return;
    }

    if (entityType == 'conversation') {
      context.push('/chat/$entityId');
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l.notifications)),
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
              Icons.notifications_none,
              size: 56,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(
              l.noNotifications,
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
            final isRead = item['is_read'] == true;

            return Material(
              color: AppTheme.bgSurface,
              borderRadius: BorderRadius.circular(AppTheme.cardRadius),
              child: InkWell(
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                onTap: () => _openNotification(item),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isRead
                              ? AppTheme.bgMuted
                              : AppTheme.accent.withValues(alpha: 0.15),
                        ),
                        child: Icon(
                          isRead
                              ? Icons.notifications_none
                              : Icons.notifications_active_outlined,
                          color: isRead ? AppTheme.textSubtle : AppTheme.accent,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    item['title']?.toString() ?? '-',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: isRead
                                          ? FontWeight.w600
                                          : FontWeight.w700,
                                    ),
                                  ),
                                ),
                                if (!isRead)
                                  Container(
                                    width: 8,
                                    height: 8,
                                    decoration: const BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: AppTheme.accent,
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 3),
                            Text(
                              item['body']?.toString() ?? '',
                              style: const TextStyle(
                                color: AppTheme.textSubtle,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  _timeLabel(item),
                                  style: const TextStyle(
                                    color: AppTheme.textSubtle,
                                    fontSize: 11,
                                  ),
                                ),
                                if (!isRead)
                                  TextButton(
                                    onPressed: () => _markAsRead(item),
                                    style: TextButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 0,
                                      ),
                                      minimumSize: Size.zero,
                                      tapTargetSize:
                                          MaterialTapTargetSize.shrinkWrap,
                                    ),
                                    child: Text(l.markAsRead),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
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
