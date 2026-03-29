import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/listings_repository.dart';

class MyListingsScreen extends ConsumerStatefulWidget {
  const MyListingsScreen({super.key});

  @override
  ConsumerState<MyListingsScreen> createState() => _MyListingsScreenState();
}

class _MyListingsScreenState extends ConsumerState<MyListingsScreen> {
  final List<Map<String, dynamic>> _items = [];
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
    if (!append) {
      setState(() {
        _loading = true;
        _error = null;
      });
    } else {
      setState(() {
        _loadingMore = true;
      });
    }

    try {
      final repo = ref.read(listingsRepositoryProvider);
      final data = await repo.getMyListings(page: _page, pageSize: 20);
      final items = (data['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();

      setState(() {
        if (append) {
          _items.addAll(items);
        } else {
          _items
            ..clear()
            ..addAll(items);
        }
        _totalPages = data['total_pages'] as int;
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

  Future<void> _refresh() async {
    _page = 1;
    await _load();
  }

  void _loadMore() {
    if (_loadingMore || _loading || _page >= _totalPages) return;
    _page += 1;
    _load(append: true);
  }

  String _statusLabel(String status, S l) {
    switch (status) {
      case 'published':
        return l.published;
      case 'pending_review':
        return l.pendingReview;
      case 'rejected':
        return l.rejected;
      case 'archived':
        return l.archived;
      case 'draft':
        return l.draft;
      case 'inactive':
        return l.inactive;
      case 'sold':
        return l.sold;
      default:
        return status;
    }
  }

  ({Color bg, Color fg}) _statusColors(String status) {
    switch (status) {
      case 'published':
        return (bg: AppTheme.statusSuccessBg, fg: AppTheme.statusSuccess);
      case 'pending_review':
        return (bg: AppTheme.statusWarningBg, fg: const Color(0xFF8A6A00));
      case 'rejected':
        return (bg: AppTheme.statusErrorBg, fg: AppTheme.statusError);
      case 'sold':
        return (
          bg: AppTheme.accent.withValues(alpha: 0.12),
          fg: AppTheme.accent,
        );
      default:
        return (bg: AppTheme.bgMuted, fg: AppTheme.textSubtle);
    }
  }

  String _formatPrice(dynamic price, String currency) {
    final value = (price is String)
        ? double.parse(price)
        : (price as num).toDouble();
    final intPrice = value.toInt();
    final buffer = StringBuffer();
    final str = intPrice.toString();
    for (var i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) {
        buffer.write(' ');
      }
      buffer.write(str[i]);
    }
    return '$buffer $currency';
  }

  List<_ListingAction> _actionsForStatus(String status) {
    switch (status) {
      case 'published':
        return [
          _ListingAction.edit,
          _ListingAction.promote,
          _ListingAction.markSold,
          _ListingAction.deactivate,
          _ListingAction.archive,
        ];
      case 'inactive':
        return [
          _ListingAction.edit,
          _ListingAction.activate,
          _ListingAction.archive,
        ];
      case 'sold':
        return [_ListingAction.archive];
      case 'archived':
        return [_ListingAction.restore, _ListingAction.hardDelete];
      default:
        return [_ListingAction.edit, _ListingAction.archive];
    }
  }

  String _actionLabel(_ListingAction action, S l) {
    switch (action) {
      case _ListingAction.edit:
        return l.editListing;
      case _ListingAction.promote:
        return l.promote;
      case _ListingAction.markSold:
        return l.markAsSold;
      case _ListingAction.deactivate:
        return l.deactivate;
      case _ListingAction.activate:
      case _ListingAction.restore:
        return l.reactivate;
      case _ListingAction.archive:
        return l.archive;
      case _ListingAction.hardDelete:
        return l.delete;
    }
  }

  Future<void> _applyAction(
    _ListingAction action,
    Map<String, dynamic> listing,
  ) async {
    final repo = ref.read(listingsRepositoryProvider);
    final l = S.of(context)!;
    final listingId = listing['id'] as int;

    try {
      switch (action) {
        case _ListingAction.edit:
          final changed = await context.push<bool>(
            '/my-listings/$listingId/edit',
            extra: listing,
          );
          if (changed == true && mounted) {
            await _refresh();
          }
          return;
        case _ListingAction.promote:
          context.push('/promote/$listingId', extra: listing);
          return;
        case _ListingAction.markSold:
          await repo.updateListingStatus(listingId, 'mark_sold');
          break;
        case _ListingAction.deactivate:
          await repo.updateListingStatus(listingId, 'deactivate');
          break;
        case _ListingAction.activate:
          await repo.updateListingStatus(listingId, 'activate');
          break;
        case _ListingAction.archive:
          await repo.archiveListing(listingId);
          break;
        case _ListingAction.restore:
          await repo.restoreListing(listingId);
          break;
        case _ListingAction.hardDelete:
          final confirmed = await showDialog<bool>(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(l.delete),
              content: Text(l.deleteListingForever),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: Text(l.cancel),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: Text(l.delete),
                ),
              ],
            ),
          );
          if (confirmed == true) {
            await repo.hardDeleteListing(listingId);
          } else {
            return;
          }
          break;
      }

      if (!mounted) return;
      await _refresh();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l.myListings)),
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
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.inventory_2_outlined,
                size: 64,
                color: AppTheme.textSubtle,
              ),
              const SizedBox(height: 12),
              Text(
                l.youDontHaveListings,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppTheme.textSubtle),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppTheme.accent,
      child: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification is ScrollEndNotification &&
              notification.metrics.extentAfter < 240) {
            _loadMore();
          }
          return false;
        },
        child: ListView.separated(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 100),
          itemCount: _items.length + (_loadingMore ? 1 : 0),
          separatorBuilder: (_, index) => const SizedBox(height: 10),
          itemBuilder: (context, index) {
            if (index >= _items.length) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Center(
                  child: CircularProgressIndicator(color: AppTheme.accent),
                ),
              );
            }

            final item = _items[index];
            final status = (item['status'] as String?) ?? 'draft';
            final statusColors = _statusColors(status);
            final actions = _actionsForStatus(status);

            return InkWell(
              onTap: () => context.push('/listing/${item['id']}'),
              borderRadius: BorderRadius.circular(AppTheme.cardRadius),
              child: Container(
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
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            item['title'] as String? ?? '',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 8),
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
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: statusColors.fg,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _formatPrice(
                        item['price'],
                        (item['currency'] as String?) ?? 'KGS',
                      ),
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(
                          Icons.location_on_outlined,
                          size: 15,
                          color: AppTheme.textSubtle,
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            item['city'] as String? ?? '',
                            style: const TextStyle(color: AppTheme.textSubtle),
                          ),
                        ),
                        PopupMenuButton<_ListingAction>(
                          icon: const Icon(Icons.more_horiz),
                          onSelected: (action) => _applyAction(action, item),
                          itemBuilder: (context) => actions
                              .map(
                                (action) => PopupMenuItem<_ListingAction>(
                                  value: action,
                                  child: Text(_actionLabel(action, l)),
                                ),
                              )
                              .toList(),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

enum _ListingAction {
  edit,
  promote,
  markSold,
  deactivate,
  activate,
  archive,
  restore,
  hardDelete,
}
