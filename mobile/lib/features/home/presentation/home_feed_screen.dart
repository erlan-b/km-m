import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../favorites/data/favorites_repository.dart';
import '../../listings/data/listings_repository.dart';
import '../../listings/presentation/widgets/listing_card.dart';
import '../../notifications/data/notifications_repository.dart';

class HomeFeedScreen extends ConsumerStatefulWidget {
  const HomeFeedScreen({super.key});

  @override
  ConsumerState<HomeFeedScreen> createState() => _HomeFeedScreenState();
}

class _HomeFeedScreenState extends ConsumerState<HomeFeedScreen> {
  List<dynamic> _listings = [];
  final Set<int> _favoriteIds = <int>{};
  final Set<int> _favoriteBusyIds = <int>{};

  bool _loading = true;
  String? _error;
  int _page = 1;
  int _totalPages = 1;
  int _unreadNotifications = 0;

  @override
  void initState() {
    super.initState();
    _loadListings();
    _loadFavoriteIds();
    _loadUnreadCount();
  }

  Future<void> _loadListings({bool append = false}) async {
    if (!append) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final repo = ref.read(listingsRepositoryProvider);
      final data = await repo.getListings(
        page: _page,
        pageSize: 20,
        status: 'published',
        sortBy: 'newest',
      );
      final items = data['items'] as List<dynamic>;
      final totalPages = data['total_pages'] as int;

      setState(() {
        if (append) {
          _listings.addAll(items);
        } else {
          _listings = items;
        }
        _totalPages = totalPages;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _refresh() async {
    _page = 1;
    await Future.wait([
      _loadListings(),
      _loadFavoriteIds(),
      _loadUnreadCount(),
    ]);
  }

  void _loadMore() {
    if (_page < _totalPages) {
      _page++;
      _loadListings(append: true);
    }
  }

  Future<void> _loadFavoriteIds() async {
    try {
      final ids = await ref
          .read(favoritesRepositoryProvider)
          .fetchFavoriteIds();
      if (!mounted) {
        return;
      }
      setState(() {
        _favoriteIds
          ..clear()
          ..addAll(ids);
      });
    } catch (_) {}
  }

  Future<void> _loadUnreadCount() async {
    try {
      final data = await ref
          .read(notificationsRepositoryProvider)
          .getUnreadCount();
      final count = (data['unread_count'] as num?)?.toInt() ?? 0;
      if (!mounted) {
        return;
      }
      setState(() {
        _unreadNotifications = count;
      });
    } catch (_) {}
  }

  Future<void> _toggleFavorite(int listingId) async {
    if (_favoriteBusyIds.contains(listingId)) {
      return;
    }

    final wasFavorite = _favoriteIds.contains(listingId);
    setState(() {
      _favoriteBusyIds.add(listingId);
      if (wasFavorite) {
        _favoriteIds.remove(listingId);
      } else {
        _favoriteIds.add(listingId);
      }
    });

    try {
      final repo = ref.read(favoritesRepositoryProvider);
      if (wasFavorite) {
        await repo.removeFavorite(listingId);
      } else {
        await repo.addFavorite(listingId);
      }
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        if (wasFavorite) {
          _favoriteIds.add(listingId);
        } else {
          _favoriteIds.remove(listingId);
        }
      });
    } finally {
      if (mounted) {
        setState(() {
          _favoriteBusyIds.remove(listingId);
        });
      }
    }
  }

  String? _getThumbnailUrl(Map<String, dynamic> listing) {
    // The listing response doesn't include media directly.
    // We'll use a helper for primary thumbnail using listing ID.
    // For now, return null — Phase 3 will add media preloading.
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l.appTitle),
        actions: [
          IconButton(
            icon: const Icon(Icons.storefront_outlined),
            tooltip: l.myListings,
            onPressed: () => context.push('/my-listings'),
          ),
          IconButton(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_outlined),
                if (_unreadNotifications > 0)
                  Positioned(
                    right: -2,
                    top: -2,
                    child: Container(
                      constraints: const BoxConstraints(minWidth: 16),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 1,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.accent,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        _unreadNotifications > 99
                            ? '99+'
                            : '$_unreadNotifications',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            onPressed: () async {
              await context.push('/notifications');
              if (mounted) {
                _loadUnreadCount();
              }
            },
          ),
        ],
      ),
      body: _buildBody(l),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _listings.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _listings.isEmpty) {
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
            Text(
              l.errorOccurred,
              style: const TextStyle(color: AppTheme.textSubtle),
            ),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _refresh, child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_listings.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.home_outlined,
              size: 64,
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
      color: AppTheme.accent,
      onRefresh: _refresh,
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
            itemCount: _listings.length,
            itemBuilder: (context, index) {
              final listing = _listings[index] as Map<String, dynamic>;
              final listingId = listing['id'] as int;
              return ListingCard(
                id: listingId,
                title: listing['title'] as String,
                price: (listing['price'] is String)
                    ? double.parse(listing['price'] as String)
                    : (listing['price'] as num).toDouble(),
                currency: listing['currency'] as String,
                city: listing['city'] as String,
                transactionType: listing['transaction_type'] as String,
                thumbnailUrl: _getThumbnailUrl(listing),
                isFavorite: _favoriteIds.contains(listingId),
                onTap: () => context.push('/listing/$listingId'),
                onFavoriteTap: _favoriteBusyIds.contains(listingId)
                    ? null
                    : () => _toggleFavorite(listingId),
              );
            },
          ),
        ),
      ),
    );
  }
}
