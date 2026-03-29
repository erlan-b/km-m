import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../favorites/data/favorites_repository.dart';
import '../../listings/presentation/widgets/listing_card.dart';

class FavoritesScreen extends ConsumerStatefulWidget {
  const FavoritesScreen({super.key});

  @override
  ConsumerState<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends ConsumerState<FavoritesScreen> {
  List<Map<String, dynamic>> _items = [];
  final Set<int> _busyIds = <int>{};

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
          .read(favoritesRepositoryProvider)
          .listFavorites(page: _page, pageSize: 20);
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

  Future<void> _removeFavorite(Map<String, dynamic> listing) async {
    final listingId = (listing['id'] as num?)?.toInt();
    if (listingId == null || _busyIds.contains(listingId)) {
      return;
    }

    final l = S.of(context)!;

    setState(() {
      _busyIds.add(listingId);
      _items = _items.where((item) => item['id'] != listingId).toList();
    });

    try {
      await ref.read(favoritesRepositoryProvider).removeFavorite(listingId);
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _items = <Map<String, dynamic>>[listing, ..._items];
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    } finally {
      if (mounted) {
        setState(() {
          _busyIds.remove(listingId);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l.favorites)),
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
              Icons.bookmark_border,
              size: 56,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(
              l.noFavorites,
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
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: GridView.builder(
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 0.68,
            ),
            itemCount: _items.length + (_loadingMore ? 1 : 0),
            itemBuilder: (context, index) {
              if (index >= _items.length) {
                return const Center(
                  child: CircularProgressIndicator(
                    color: AppTheme.accent,
                    strokeWidth: 2,
                  ),
                );
              }

              final listing = _items[index];
              final listingId = (listing['id'] as num?)?.toInt() ?? 0;
              final priceRaw = listing['price'];

              return ListingCard(
                id: listingId,
                title: listing['title']?.toString() ?? '-',
                price: (priceRaw is String)
                    ? double.tryParse(priceRaw) ?? 0
                    : (priceRaw as num?)?.toDouble() ?? 0,
                currency: listing['currency']?.toString() ?? 'KGS',
                city: listing['city']?.toString() ?? '-',
                transactionType:
                    listing['transaction_type']?.toString() ?? 'sale',
                isPromoted: listing['is_subscription'] == true,
                isFavorite: true,
                onTap: () => context.push('/listing/$listingId'),
                onFavoriteTap: _busyIds.contains(listingId)
                    ? null
                    : () => _removeFavorite(listing),
              );
            },
          ),
        ),
      ),
    );
  }
}
