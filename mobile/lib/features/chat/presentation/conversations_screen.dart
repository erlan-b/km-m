import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/chat_repository.dart';

class ConversationsScreen extends ConsumerStatefulWidget {
  const ConversationsScreen({super.key});

  @override
  ConsumerState<ConversationsScreen> createState() =>
      _ConversationsScreenState();
}

class _ConversationsScreenState extends ConsumerState<ConversationsScreen> {
  List<Map<String, dynamic>> _conversations = [];

  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  int _page = 1;
  int _totalPages = 1;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  Future<void> _loadConversations({bool append = false}) async {
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
      final repo = ref.read(chatRepositoryProvider);
      final data = await repo.listConversations(page: _page, pageSize: 20);
      final items = _toMapList(data['items']);
      final totalPages = (data['total_pages'] as num?)?.toInt() ?? 0;

      setState(() {
        if (append) {
          _conversations.addAll(items);
        } else {
          _conversations = items;
        }
        _totalPages = totalPages <= 0 ? 1 : totalPages;
        _loading = false;
        _loadingMore = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  List<Map<String, dynamic>> _toMapList(dynamic rawItems) {
    if (rawItems is! List) {
      return <Map<String, dynamic>>[];
    }
    return rawItems
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<void> _refresh() async {
    _page = 1;
    await _loadConversations();
  }

  void _loadMore() {
    if (_loading || _loadingMore || _page >= _totalPages) {
      return;
    }

    _page += 1;
    _loadConversations(append: true);
  }

  void _openConversation(Map<String, dynamic> conversation) {
    final conversationId = (conversation['id'] as num?)?.toInt();
    if (conversationId == null) {
      return;
    }

    context.push('/chat/$conversationId', extra: conversation);
  }

  String _previewLabel(Map<String, dynamic> conversation, S l) {
    final preview = conversation['last_message_preview']?.toString().trim();
    if (preview != null && preview.isNotEmpty) {
      return preview;
    }
    return l.newMessage;
  }

  String _timeLabel(Map<String, dynamic> conversation) {
    final raw = conversation['last_message_at'] ?? conversation['created_at'];
    final value = raw?.toString();
    if (value == null || value.isEmpty) {
      return '';
    }

    final date = DateTime.tryParse(value);
    if (date == null) {
      return '';
    }

    return DateFormat('dd.MM HH:mm').format(date.toLocal());
  }

  int _unreadCount(Map<String, dynamic> conversation) {
    return (conversation['unread_count'] as num?)?.toInt() ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l.conversations)),
      body: _buildBody(l),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _conversations.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _conversations.isEmpty) {
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

    if (_conversations.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.chat_bubble_outline,
              size: 56,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(
              l.noConversations,
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
          itemCount: _conversations.length + (_loadingMore ? 1 : 0),
          separatorBuilder: (context, index) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            if (index >= _conversations.length) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Center(
                  child: CircularProgressIndicator(
                    color: AppTheme.accent,
                    strokeWidth: 2.2,
                  ),
                ),
              );
            }

            final conversation = _conversations[index];
            final listingId =
                (conversation['listing_id'] as num?)?.toInt() ?? 0;
            final unreadCount = _unreadCount(conversation);

            return Material(
              color: AppTheme.bgSurface,
              borderRadius: BorderRadius.circular(AppTheme.cardRadius),
              child: InkWell(
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                onTap: () => _openConversation(conversation),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: AppTheme.accent.withValues(alpha: 0.12),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.chat_bubble_outline,
                          color: AppTheme.accent,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '#$listingId',
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              _previewLabel(conversation, l),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: AppTheme.textSubtle,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            _timeLabel(conversation),
                            style: const TextStyle(
                              color: AppTheme.textSubtle,
                              fontSize: 11,
                            ),
                          ),
                          const SizedBox(height: 6),
                          if (unreadCount > 0)
                            Container(
                              constraints: const BoxConstraints(minWidth: 22),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 7,
                                vertical: 3,
                              ),
                              decoration: BoxDecoration(
                                color: AppTheme.accent,
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                unreadCount > 99 ? '99+' : '$unreadCount',
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                        ],
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
