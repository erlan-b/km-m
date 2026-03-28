import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../listings/data/listings_repository.dart';
import '../../listings/presentation/widgets/listing_card.dart';

class HomeFeedScreen extends ConsumerStatefulWidget {
  const HomeFeedScreen({super.key});

  @override
  ConsumerState<HomeFeedScreen> createState() => _HomeFeedScreenState();
}

class _HomeFeedScreenState extends ConsumerState<HomeFeedScreen> {
  List<dynamic> _listings = [];

  bool _loading = true;
  String? _error;
  int _page = 1;
  int _totalPages = 1;

  @override
  void initState() {
    super.initState();
    _loadListings();
  }

  Future<void> _loadListings({bool append = false}) async {
    if (!append) setState(() { _loading = true; _error = null; });

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
    await _loadListings();
  }

  void _loadMore() {
    if (_page < _totalPages) {
      _page++;
      _loadListings(append: true);
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
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {/* TODO: notifications */},
          ),
        ],
      ),
      body: _buildBody(l),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _listings.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.accent));
    }

    if (_error != null && _listings.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AppTheme.textSubtle),
            const SizedBox(height: 12),
            Text(l.errorOccurred, style: const TextStyle(color: AppTheme.textSubtle)),
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
            const Icon(Icons.home_outlined, size: 64, color: AppTheme.textSubtle),
            const SizedBox(height: 12),
            Text(l.emptyList, style: const TextStyle(color: AppTheme.textSubtle, fontSize: 16)),
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
              return ListingCard(
                id: listing['id'] as int,
                title: listing['title'] as String,
                price: (listing['price'] is String)
                    ? double.parse(listing['price'] as String)
                    : (listing['price'] as num).toDouble(),
                currency: listing['currency'] as String,
                city: listing['city'] as String,
                transactionType: listing['transaction_type'] as String,
                thumbnailUrl: _getThumbnailUrl(listing),
                onTap: () => context.push('/listing/${listing['id']}'),
              );
            },
          ),
        ),
      ),
    );
  }
}
